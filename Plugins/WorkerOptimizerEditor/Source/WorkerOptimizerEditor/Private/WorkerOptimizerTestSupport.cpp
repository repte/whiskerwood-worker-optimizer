#include "WorkerOptimizerTestSupport.h"
#include "UObject/UnrealType.h"
#include "Blueprint/UserWidget.h"
#include "Engine/TextureRenderTarget2D.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "RenderingThread.h"
#include "Slate/WidgetRenderer.h"
#include "Blueprint/IUserObjectListEntry.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "WidgetBlueprint.h"
#include "Widgets/SWidget.h"
#include "AssetCompilingManager.h"
#include "Components/ListView.h"
#include "Components/TextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "UObject/StructOnScope.h"

namespace
{
    // UWidget only weakly owns its Slate tree. Keep one render alive for geometry
    // and virtualized-entry inspection after FWidgetRenderer's window is gone.
    TSharedPtr<SWidget> RenderedArtifactRoot;
}

void UWorkerOptimizerTestSupport::ReleaseWidgetArtifact()
{
    RenderedArtifactRoot.Reset();
}

bool UWorkerOptimizerTestSupport::RealizeWidgetArtifact(UUserWidget* Widget)
{
    if (!IsValid(Widget)) return false;
    RenderedArtifactRoot = Widget->TakeWidget();
    return RenderedArtifactRoot.IsValid();
}

float UWorkerOptimizerTestSupport::MeasureTextWidth(UTextBlock* TextBlock, const FString& Text)
{
    if (!IsValid(TextBlock) || !FSlateApplication::IsInitialized()) return -1.0f;
    return FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, TextBlock->GetFont()).X;
}

bool UWorkerOptimizerTestSupport::BroadcastListItemEvent(UListView* List, FName EventName, UObject* Item, bool bIsSelected)
{
    if (!IsValid(List) || !IsValid(Item)
        || (EventName != TEXT("BP_OnItemClicked") && EventName != TEXT("BP_OnItemSelectionChanged"))) return false;
    const FMulticastDelegateProperty* Property = FindFProperty<FMulticastDelegateProperty>(List->GetClass(), EventName);
    if (!Property || !Property->SignatureFunction) return false;
    FStructOnScope Parameters(Property->SignatureFunction);
    FObjectPropertyBase* ItemParameter = FindFProperty<FObjectPropertyBase>(Property->SignatureFunction, TEXT("Item"));
    if (!ItemParameter) return false;
    ItemParameter->SetObjectPropertyValue_InContainer(Parameters.GetStructMemory(), Item);
    if (EventName == TEXT("BP_OnItemSelectionChanged"))
    {
        FBoolProperty* SelectedParameter = FindFProperty<FBoolProperty>(Property->SignatureFunction, TEXT("bIsSelected"));
        if (!SelectedParameter) return false;
        SelectedParameter->SetPropertyValue_InContainer(Parameters.GetStructMemory(), bIsSelected);
    }
    const FMulticastScriptDelegate* Delegate = Property->GetMulticastDelegate(Property->ContainerPtrToValuePtr<void>(List));
    if (!Delegate) return false;
    Delegate->ProcessDelegate<UObject>(Parameters.GetStructMemory());
    return true;
}

FVector4 UWorkerOptimizerTestSupport::MeasureWidgetArtifact(UWidget* Widget)
{
    if (!IsValid(Widget) || !RenderedArtifactRoot.IsValid()) return FVector4(0, 0, 0, 0);
    const TSharedPtr<SWidget> SlateWidget = Widget->GetCachedWidget();
    if (!SlateWidget.IsValid()) return FVector4(0, 0, 0, 0);
    const FGeometry& Geometry = SlateWidget->GetPaintSpaceGeometry();
    const FVector2D Top = Geometry.LocalToAbsolute(FVector2D::ZeroVector);
    const FVector2D Bottom = Geometry.LocalToAbsolute(Geometry.GetLocalSize());
    UE_LOG(LogTemp, Display, TEXT("WO_RENDER_GEOMETRY %s Slate=%s Local=%s Paint=%s"),
        *Widget->GetPathName(), *SlateWidget->GetTypeAsString(), *Geometry.GetLocalSize().ToString(), *(Bottom - Top).ToString());
    return FVector4(Top.X, Top.Y, Bottom.X - Top.X, Bottom.Y - Top.Y);
}

float UWorkerOptimizerTestSupport::MeasureWidgetLayoutScale(UWidget* Widget)
{
    if (!IsValid(Widget)) return 0;
    const TSharedPtr<SWidget> SlateWidget = Widget->GetCachedWidget();
    return SlateWidget.IsValid() ? SlateWidget->GetPaintSpaceGeometry().GetAccumulatedLayoutTransform().GetScale() : 0;
}

bool UWorkerOptimizerTestSupport::ImplementListEntry(UBlueprint* Blueprint)
{
    if (!IsValid(Blueprint)) return false;
    if (Blueprint->GeneratedClass && Blueprint->GeneratedClass->ImplementsInterface(UUserObjectListEntry::StaticClass())) return true;
    return FBlueprintEditorUtils::ImplementNewInterface(Blueprint, UUserObjectListEntry::StaticClass()->GetClassPathName());
}

bool UWorkerOptimizerTestSupport::BindWidgetFunction(UBlueprint* Blueprint, FName WidgetName, FName PropertyName, FName FunctionName)
{
    UWidgetBlueprint* Widget = Cast<UWidgetBlueprint>(Blueprint);
    if (!Widget || WidgetName.IsNone() || PropertyName.IsNone() || FunctionName.IsNone()) return false;
    Widget->Bindings.RemoveAll([&](const FDelegateEditorBinding& Binding)
    {
        return Binding.ObjectName == WidgetName.ToString() && Binding.PropertyName == PropertyName;
    });
    FDelegateEditorBinding Binding;
    Binding.ObjectName = WidgetName.ToString();
    Binding.PropertyName = PropertyName;
    Binding.FunctionName = FunctionName;
    Binding.Kind = EBindingKind::Function;
    Widget->Bindings.Add(Binding);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Widget);
    return true;
}

bool UWorkerOptimizerTestSupport::BroadcastLoadingFinished(UObject* ModAPI)
{
    if (!IsValid(ModAPI) || ModAPI->GetClass()->GetPathName() != TEXT("/Script/SystemCore.ModAPI"))
    {
        return false;
    }
    const FMulticastDelegateProperty* Property =
        FindFProperty<FMulticastDelegateProperty>(ModAPI->GetClass(), TEXT("onLoadingFinished"));
    if (!Property || !Property->SignatureFunction || Property->SignatureFunction->NumParms != 0)
    {
        return false;
    }
    const FMulticastScriptDelegate* Delegate =
        Property->GetMulticastDelegate(Property->ContainerPtrToValuePtr<void>(ModAPI));
    if (!Delegate)
    {
        return false;
    }
    Delegate->ProcessDelegate<UObject>(nullptr);
    return true;
}

bool UWorkerOptimizerTestSupport::HasOnlyEventBindings(UBlueprint* Blueprint)
{
    const UWidgetBlueprint* Widget = Cast<UWidgetBlueprint>(Blueprint);
    if (!Widget) return false;
    for (const FDelegateEditorBinding& Binding : Widget->Bindings)
    {
        if (Binding.Kind != EBindingKind::Function
            || (Binding.PropertyName != TEXT("BP_OnItemClicked")
                && Binding.PropertyName != TEXT("BP_OnItemSelectionChanged")
                && Binding.PropertyName != TEXT("BP_OnGetItemChildren"))) return false;
    }
    return true;
}

bool UWorkerOptimizerTestSupport::RenderWidgetArtifact(UUserWidget* Widget, int32 Width, int32 Height, const FString& FileName)
{
    if (!IsValid(Widget) || Width < 1 || Height < 1 || Width > 4096 || Height > 4096
        || FileName.IsEmpty() || FPaths::GetCleanFilename(FileName) != FileName
        || !FileName.EndsWith(TEXT(".png")) || FileName.Contains(TEXT("..")))
    {
        return false;
    }
    // Python can import textures and render without an intervening editor tick.
    // Finish their async builds and resource uploads before Slate reads brushes.
    FAssetCompilingManager::Get().FinishAllCompilation();
    FlushRenderingCommands();
    // Render the real Slate tree into a file; no desktop/window automation.
    RenderedArtifactRoot = Widget->TakeWidget();
    FWidgetRenderer Renderer(true, true);
    // Slate applies display gamma. A linear target avoids applying it again in
    // the render-target write; readback below must also keep those encoded bytes.
    const FVector2D DrawSize(Width, Height);
    UTextureRenderTarget2D* Target = FWidgetRenderer::CreateTargetFor(DrawSize, TF_Bilinear, false);
    if (!Target)
    {
        return false;
    }
    Renderer.DrawWidget(Target, RenderedArtifactRoot.ToSharedRef(), DrawSize, 0.0f, false);
    FlushRenderingCommands();
    TArray<FColor> Pixels;
    FTextureRenderTargetResource* Resource = Target->GameThread_GetRenderTargetResource();
    FReadSurfaceDataFlags ReadFlags(RCM_UNorm);
    ReadFlags.SetLinearToGamma(false);
    if (!Resource || !Resource->ReadPixels(Pixels, ReadFlags) || Pixels.Num() != Width * Height)
    {
        return false;
    }
    TArray64<uint8> Png;
    FImageUtils::PNGCompressImageArray(Width, Height, MakeArrayView(Pixels), Png);
    const FString Directory = FPaths::ProjectSavedDir() / TEXT("WorkerOptimizerUI");
    IFileManager::Get().MakeDirectory(*Directory, true);
    return FFileHelper::SaveArrayToFile(Png, *(Directory / FileName));
}
