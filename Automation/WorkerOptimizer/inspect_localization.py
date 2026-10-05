"""Read native option localization and text metadata without modifying game assets."""

import json
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

graph = BP.get_graph(unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings"), "RegisterGeneral")
for node in BP.find_node_types(graph, "", []):
    if any(n in node for n in ("LocManager|", "GetLocManager", "GetActiveLanguage", "AddNewStrings", "RegisterModOptions", "GetSpeedModifiers", "GetCarry", "GetAgentModifiers")):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log("WO_LANG_NODE " + node + " " + str([(p.name, p.type_id) for p in pins.input_pins]) + " -> " + str([(p.name, p.type_id) for p in pins.output_pins]))
for path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
    if any(t in path.lower() for t in ("language", "localization", "toolbar", "locconfig", "modoption")):
        unreal.log("WO_LANG_ASSET " + path)
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.DataTable):
            raw = unreal.DataTableFunctionLibrary.export_data_table_to_json_string(asset)
            Path(unreal.Paths.project_saved_dir(), "WO-Lang-" + asset.get_name() + ".json").write_text(raw, encoding="utf-8")
unreal.log("WO_LANG_INSPECTION_COMPLETE")
