"""Read-only discovery of runtime definition-table access and category metadata."""

import json
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_PrioritySettings")
assert bp
graph = BP.get_graph(bp, "ReadPriority")
nodes = BP.find_node_types(graph, "", [])
for node in nodes:
    if any(token in node for token in ("GetMGridActorLookup", "GetMToolbarDefs", "GetDataTableRow", "GetGameInstance")):
        unreal.log("WO_CATALOG_NODE " + node)
        if node in ("Utilities|GetDataTableRow", "DataTable|GetDataTableRowNames", "Game|GetGameInstance", "DataTable|GetDataTableRowStruct"):
            pins = BP.get_node_type_pins(graph, node)
            unreal.log("WO_CATALOG_PINS " + node + " in=" + str([(p.name, p.type_id) for p in pins.input_pins]) + " out=" + str([(p.name, p.type_id) for p in pins.output_pins]))
for path in unreal.EditorAssetLibrary.list_assets("/Game/Data", recursive=True, include_folder=False):
    if any(token in path.lower() for token in ("gridactor", "toolbar", "building")):
        unreal.log("WO_CATALOG_ASSET " + path)
        table = unreal.load_asset(path)
        if isinstance(table, unreal.DataTable):
            rows = unreal.DataTableFunctionLibrary.get_data_table_row_names(table)
            unreal.log("WO_CATALOG_ROWS " + str(rows[:8]) + " count=" + str(len(rows)))
            unreal.log("WO_CATALOG_ROWSTRUCT " + str(table.get_editor_property("row_struct")))
            if "GridactorDefs" in path:
                data = json.loads(unreal.DataTableFunctionLibrary.export_data_table_to_json_string(table))
                for row in data:
                    unreal.log("WO_CATALOG_DEFINITION " + str({key: row.get(key) for key in
                        ("Name", "toolbarGroup", "maxAgents_contextual", "asHouseTier", "guildSpecialty", "structureType")}))
unreal.log("WO_CATALOG_INSPECTION_COMPLETE")
