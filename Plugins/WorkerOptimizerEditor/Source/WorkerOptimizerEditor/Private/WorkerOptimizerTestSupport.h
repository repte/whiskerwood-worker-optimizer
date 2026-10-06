#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "WorkerOptimizerTestSupport.generated.h"

class UUserWidget;
class UWidget;
class UBlueprint;
class UListView;
class UTextBlock;

// Editor-only test bridge for Suzie delegates without generated Python proxies.
UCLASS()
class UWorkerOptimizerTestSupport final : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool BroadcastListItemEvent(UListView* List, FName EventName, UObject* Item, bool bIsSelected);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool RealizeWidgetArtifact(UUserWidget* Widget);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static float MeasureTextWidth(UTextBlock* TextBlock, const FString& Text);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool BroadcastLoadingFinished(UObject* ModAPI);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool RenderWidgetArtifact(UUserWidget* Widget, int32 Width, int32 Height, const FString& FileName);

    // Release after inspecting the last render, before destroying its UMG fixture.
    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static void ReleaseWidgetArtifact();

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static FVector4 MeasureWidgetArtifact(UWidget* Widget);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static float MeasureWidgetLayoutScale(UWidget* Widget);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool ImplementListEntry(UBlueprint* Blueprint);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool BindWidgetFunction(UBlueprint* Blueprint, FName WidgetName, FName PropertyName, FName FunctionName);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool HasOnlyEventBindings(UBlueprint* Blueprint);
};
