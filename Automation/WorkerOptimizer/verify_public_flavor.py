"""Fail packaging when private instrumentation leaks into the public asset."""
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

blueprint = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_WorkerOptimizer")
graphs = {str(graph.get_name()) for graph in BP.list_graphs(blueprint)}
private_graphs = {"TraceDiagnostic", "DumpDiagnosticSnapshot", "DumpDiagnosticPlan", "DumpDiagnosticReport"}
assert not graphs.intersection(private_graphs), "Private tracing graphs leaked into the public controller"
variables = set(BP.list_variables(blueprint))
assert not any(str(name).startswith("Diagnostic") for name in variables), "Private fields leaked into the public controller"
controller = unreal.get_default_object(blueprint.generated_class())
assert not controller.get_editor_property("MeasurePerformance"), "Public profiling must default off"
unreal.log("WO_PUBLIC_FLAVOR_PASS")
