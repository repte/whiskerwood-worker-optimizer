"""Verify a native action call can compile without any runtime helper reference."""

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

parent = unreal.load_class(None, "/Script/ProjectArco.SelectTool")
assert parent
bp = BP.create("/Game/Mods/WorkerOptimizer", "BP_NativeBridgeProbe", parent)
graph = BP.add_function_graph(bp, "ProbeNativeAction")
BP.add_struct_function_param(graph, "action", unreal.load_object(None, "/Script/ProjectArco.HudAction"), True)
nodes = BP.find_node_types(graph, "ReceiveHudAction", [])
native_node = next((n for n in nodes if n == "WorkerOptimizerNativeBridge|ReceiveHudAction"), None)
assert native_node is not None, f"Native SelectTool action receiver is not authorable: {nodes}"
with toolset_registry.tool_raising_exceptions():
    BP.write_graph_dsl(graph, f"(fn ProbeNativeAction (action) ({native_node} :self self :HudAction action))")
    BP.compile_blueprint(bp, warnings_as_errors=True)
unreal.log("WO_NATIVE_BRIDGE_AUTHORING_PASS: compiled direct native SelectTool receiver call; no game action executed, no probe asset saved")
