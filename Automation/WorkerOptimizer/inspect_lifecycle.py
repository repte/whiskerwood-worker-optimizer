"""Inspect world-load binding and runtime widget/actor creation without editing assets."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_Startup")
graph = BP.get_graph(bp, "BeginStartup")
for node in BP.find_node_types(graph, "", []):
    if any(token in node.lower() for token in (
        "createevent", "createwidget", "spawnactorfromclass", "getplayercontroller",
        "getallactorsofclass", "bindeventtoonloadingfinished", "unbindeventfromonloadingfinished",
        "destroyactor", "getowner")):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_LIFECYCLE_NODE " + node + " in=" + str([(p.name, p.type_id) for p in pins.input_pins])
                   + " out=" + str([(p.name, p.type_id) for p in pins.output_pins]))
api = unreal.new_object(unreal.load_class(None, "/Script/SystemCore.ModAPI"))
delegate = api.get_editor_property("onLoadingFinished")
unreal.log("WO_LOADING_DELEGATE " + str(type(delegate)) + " " + str(dir(delegate)))
for path in ("/Game/Mods/CopperSlides/BP_MapLoad", "/Game/Mods/ShortNight/BP_MapLoad"):
    asset = unreal.load_asset(path)
    if asset:
        unreal.log("WO_SAMPLE_GRAPH " + BP.read_graph_dsl(BP.get_graph(asset, "EventGraph")))
unreal.log("WO_LIFECYCLE_INSPECTION_COMPLETE")
