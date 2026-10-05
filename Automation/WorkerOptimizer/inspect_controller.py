"""Inspect native object creation/time/tick signatures without changing assets."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PlanSearch")
graph = BP.get_graph(bp, "BeginSearch")
for node in BP.find_node_types(graph, "", []):
    if any(token in node.replace(" ", "").lower() for token in
           ("constructobject", "getrealtimeseconds", "getaccuraterealtime", "spawnactorfromclass", "eventtick", "getworlddelta")):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_CONTROLLER_NODE " + node + " in=" + str([(p.name, p.type_id) for p in pins.input_pins])
                   + " out=" + str([(p.name, p.type_id) for p in pins.output_pins]))
unreal.log("WO_CONTROLLER_INSPECTION_COMPLETE")
