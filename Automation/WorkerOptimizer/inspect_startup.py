"""Read native option/localization and loader signatures without editing assets."""

import json
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings")
graph = BP.get_graph(bp, "RegisterGeneral")
for node in BP.find_node_types(graph, "", []):
    if any(token in node.lower() for token in (
        "class|locmanager|", "getlocmanager", "getmloc", "getmtoolbar", "registermodoptions",
        "getmodapi", "onloadingfinished", "onoptionchanged", "wasinputkeyjustpressed")):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_STARTUP_NODE " + node + " in=" + str([(p.name, p.type_id) for p in pins.input_pins])
                   + " out=" + str([(p.name, p.type_id) for p in pins.output_pins]))
table = unreal.load_asset("/Game/Data/ToolbarDefinitions")
for row in json.loads(unreal.DataTableFunctionLibrary.export_data_table_to_json_string(table)):
    unreal.log("WO_TOOLBAR_ROW " + str({key: value for key, value in row.items() if key != "toolbarItems"}))
    unreal.log("WO_TOOLBAR_ITEMS " + str([(i["ItemType"], i["LocKey"], i["gridActorGroup"], i["categoryToOpen"]) for i in row["toolbarItems"]]))
unreal.log("WO_STARTUP_INSPECTION_COMPLETE")
