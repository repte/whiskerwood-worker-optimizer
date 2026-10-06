#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "WorkerOptimizerUIAuthoring.generated.h"

class UBlueprint;
class UWidgetAnimation;

// Creates native UMG assets in the editor; generated widgets do not call this class.
UCLASS()
class UWorkerOptimizerUIAuthoring final : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "WorkerOptimizer Editor Authoring")
    static UWidgetAnimation* CreatePulseAnimation(UBlueprint* WidgetBP, FName Name, float Seconds);
};
