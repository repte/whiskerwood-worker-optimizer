"""Verify the native mod's chunk/descriptor setup before cooking."""

import json
import runpy
from pathlib import Path

import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
BASE = "/Game/Mods/WorkerOptimizer"
LABEL = BASE + "/PAL_WorkerOptimizer"

assert unreal.EditorAssetLibrary.does_asset_exist(LABEL), "Missing mod chunk label"
label = unreal.load_asset(LABEL)
assert isinstance(label, unreal.PrimaryAssetLabel)
rules = label.get_editor_property("rules")
chunk = rules.get_editor_property("chunk_id")
assert 1 <= chunk <= 300
assert rules.get_editor_property("cook_rule") == unreal.PrimaryAssetCookRule.ALWAYS_COOK
assert label.get_editor_property("label_assets_in_my_directory")
assert not label.get_editor_property("is_runtime_label")

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.scan_paths_synchronous([BASE], force_rescan=True)
registry.wait_for_completion()
labels = registry.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Engine", "PrimaryAssetLabel"))
for data in labels:
    other = data.get_asset()
    if other != label:
        assert other.get_editor_property("rules").get_editor_property("chunk_id") != chunk, str(data.package_name)

descriptor = json.loads((ROOT / "Content/Mods/WorkerOptimizer/WorkerOptimizer.uplugin").read_text())
assert descriptor["Name"] == "WorkerOptimizer"
assert descriptor["EngineVersion"] == "5.8"
assert descriptor["Version"] and descriptor["Description"] and descriptor["CreatedBy"]
assert not descriptor.get("Modules"), "Native mod must not require a DLL"
for name in ("BP_Startup", "BP_MapLoad", "BP_WorkerOptimizer", "WBP_WorkerOptimizer",
             "BP_UIListItem", "WBP_PrioritiesView", "WBP_HistoryRow", "WBP_HistoryDetailRow", "M_WorkerOptimizerBusy",
             "WBP_PriorityRow", "WBP_SettingsPanel", "WBP_LogbookView",
             "T_WorkerOptimizerFrame", "T_WorkerOptimizerShadow",
             "T_WorkerOptimizerStatusCompleted", "T_WorkerOptimizerStatusProblems",
             "T_WorkerOptimizerStatusError", "T_WorkerOptimizerStatusAborted",
             "T_WorkerOptimizerPriorityOwn", "T_WorkerOptimizerPriorityInherited"):
    assert unreal.EditorAssetLibrary.does_asset_exist(BASE + "/" + name), name
runpy.run_path(str(Path(__file__).with_name("generate_ui_frame.py")), run_name="worker_optimizer_frame_preflight")["validate_assets"]()

options = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True, include_hard_package_references=True,
    include_searchable_names=False, include_soft_management_references=False,
    include_hard_management_references=False,
)
assert registry.get_dependencies(BASE + "/__MissingDependencyBoundary", options) is None, "Failed lookups must remain distinguishable from empty dependency lists"
for data in registry.get_assets_by_path(BASE, recursive=True, include_only_on_disk_assets=True):
    dependencies = registry.get_dependencies(data.package_name, options)
    if str(data.package_name) != LABEL:
        # UE omits ubiquitous native script packages; native-only assets may have no edges.
        assert dependencies is not None, ("No dependency information", str(data.package_name))
    for dependency in dependencies or []:
        path = str(dependency)
        # Standard Blueprint macros are expanded at compile time, not runtime helpers.
        if path == "/Engine/EditorBlueprintResources/StandardMacros":
            continue
        assert not any(forbidden in path for forbidden in (
            "WorkerOptimizerEditor", "/Script/Suzie", "/Suzie/", "/Engine/Editor", "/Game/_EditorScripts",
        )), (str(data.package_name), path)
unreal.log(f"WO_PACKAGE_SETUP_TESTS_PASS: isolated chunk={chunk}, descriptor, entry points, no editor-helper package dependencies")
