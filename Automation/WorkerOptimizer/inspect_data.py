"""Read cooked lookup tables without saving or changing game assets."""

import json
from pathlib import Path

import unreal

output = {}
for path in (
    "/Game/Data/AssetLookups/WhiskerGuildsLookup",
    "/Game/Data/AgentModifiers_New",
    "/Game/Data/SystemTunes",
):
    table = unreal.load_asset(path)
    assert table is not None, path
    value = unreal.DataTableFunctionLibrary.export_data_table_to_json_string(table)
    assert value, path
    output[path] = json.loads(value)
Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-game-data.json").write_text(
    json.dumps(output, indent=2), encoding="utf-8"
)
unreal.log("WO_DATA_INSPECTION_COMPLETE")
