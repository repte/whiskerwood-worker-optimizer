"""Inspect native settings rendering and localization contract."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

graph = BP.get_graph(unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings"), "RegisterGeneral")
for node in BP.find_node_types(graph, "", []):
    if any(n in node for n in ("GetOptionManager", "SetValue", "AddNewStrings")):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_OPTION_NODE " + node + " " + str([(p.name, p.type_id) for p in pins.input_pins]))
for path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
    if any(t in path.lower() for t in ("options", "settings", "optionchoice", "locconfig")):
        unreal.log("WO_OPTION_ASSET " + path)
        unreal.load_asset(path)
for pattern in ("Option", "Settings"):
    unreal.SystemLibrary.execute_console_command(None, "DISASMSCRIPT " + pattern)
unreal.log("WO_OPTIONS_INSPECT_COMPLETE")
