using UnrealBuildTool;

public class WorkerOptimizerEditor : ModuleRules
{
    public WorkerOptimizerEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "UMG", "Slate", "SlateCore", "RenderCore" });
    }
}
