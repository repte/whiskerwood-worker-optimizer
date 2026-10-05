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

bool UWorkerOptimizerTestSupport::RenderWidgetArtifact(UUserWidget* Widget, int32 Width, int32 Height, const FString& FileName)
{
    if (!IsValid(Widget) || Width < 1 || Height < 1 || Width > 4096 || Height > 4096
        || FileName.IsEmpty() || FPaths::GetCleanFilename(FileName) != FileName
        || !FileName.EndsWith(TEXT(".png")) || FileName.Contains(TEXT("..")))
    {
        return false;
    }
    // Render the real Slate tree into a file; no desktop/window automation.
    FWidgetRenderer Renderer(true, true);
    UTextureRenderTarget2D* Target = Renderer.DrawWidget(Widget->TakeWidget(), FVector2D(Width, Height));
    if (!Target)
    {
        return false;
    }
    FlushRenderingCommands();
    TArray<FColor> Pixels;
    FTextureRenderTargetResource* Resource = Target->GameThread_GetRenderTargetResource();
    if (!Resource || !Resource->ReadPixels(Pixels) || Pixels.Num() != Width * Height)
    {
        return false;
    }
    TArray64<uint8> Png;
    FImageUtils::PNGCompressImageArray(Width, Height, MakeArrayView(Pixels), Png);
    const FString Directory = FPaths::ProjectSavedDir() / TEXT("WorkerOptimizerUI");
    IFileManager::Get().MakeDirectory(*Directory, true);
    return FFileHelper::SaveArrayToFile(Png, *(Directory / FileName));
}
