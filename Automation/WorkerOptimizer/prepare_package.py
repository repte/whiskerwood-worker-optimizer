"""Create the modkit-standard editor-only chunk label, then validate it."""

from pathlib import Path
import json
import runpy

import unreal

BASE = "/Game/Mods/WorkerOptimizer"
NAME = "PAL_WorkerOptimizer"
registry = unreal.AssetRegistryHelpers.get_asset_registry()
labels = registry.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Engine", "PrimaryAssetLabel"))
used = {
    data.get_asset().get_editor_property("rules").get_editor_property("chunk_id")
    for data in labels if str(data.package_name) != BASE + "/" + NAME
}
if unreal.EditorAssetLibrary.does_asset_exist(BASE + "/" + NAME):
    label = unreal.load_asset(BASE + "/" + NAME)
    chunk = label.get_editor_property("rules").get_editor_property("chunk_id")
    assert 1 <= chunk <= 300 and chunk not in used, "Existing chunk conflicts; inspect before changing"
else:
    chunk = next(value for value in range(1, 301) if value not in used)
    factory = unreal.DataAssetFactory()
    factory.set_editor_property("data_asset_class", unreal.PrimaryAssetLabel)
    label = unreal.AssetToolsHelpers.get_asset_tools().create_asset(NAME, BASE, unreal.PrimaryAssetLabel, factory)
    assert label, "Failed to create chunk label"

rules = label.get_editor_property("rules")
rules.set_editor_property("chunk_id", chunk)
rules.set_editor_property("cook_rule", unreal.PrimaryAssetCookRule.ALWAYS_COOK)
label.set_editor_property("rules", rules)
label.set_editor_property("label_assets_in_my_directory", True)
label.set_editor_property("is_runtime_label", False)
assert unreal.EditorAssetLibrary.save_loaded_asset(label)
runpy.run_path(str(Path(__file__).with_name("test_package_setup.py")), run_name="__main__")
Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-PackageSetup.json").write_text(
    json.dumps({"mod": "WorkerOptimizer", "chunk": chunk}, indent=2), encoding="utf-8"
)
