#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "WorkerOptimizerTestSupport.generated.h"

class UUserWidget;

// Editor-only test bridge for Suzie delegates without generated Python proxies.
UCLASS()
class UWorkerOptimizerTestSupport final : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool BroadcastLoadingFinished(UObject* ModAPI);

    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Tests")
    static bool RenderWidgetArtifact(UUserWidget* Widget, int32 Width, int32 Height, const FString& FileName);
};
