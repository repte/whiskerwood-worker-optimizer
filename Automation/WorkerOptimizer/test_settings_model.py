"""Focused native settings-model contracts; no player preference writes."""
from pathlib import Path
import sys

assert "unreal" in sys.modules or (Path(__file__).resolve().parents[2] / "Content/Mods/WorkerOptimizer/BP_SettingsModel.uasset").exists(), "Compact settings model has not been authored"
import unreal
import json
sys.path.insert(0, str(Path(__file__).parent))
from ui_test_fixture import inputs

ROOT = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, ROOT + name + "." + name + "_C")
put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    model, settings, catalog = (unreal.new_object(load(n)) for n in ("BP_SettingsModel", "BP_PrioritySettings", "BP_DefinitionCatalog"))
    assert not model.call_method("InitializeModel", args=(None, settings, catalog))
    table = unreal.new_object(unreal.DataTable)
    table.set_editor_property("ignore_missing_fields", True)
    source = unreal.load_asset("/Game/Data/GridactorDefs_Sync")
    rows = [{"Name": key, "toolbarGroup": category, "maxAgents_contextual": 1, "stringKey": key}
            for key,category in (("fishery","food_process"),("future_factory","industry_materials"),("odd_type","None"))]
    assert unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(table,json.dumps(rows),source.get_editor_property("row_struct"))
    assert catalog.call_method("BeginTable", args=(table,))
    for _ in range(10):
        if catalog.get_editor_property("CatalogDone"): break
        catalog.call_method("AdvanceCatalog")
    assert model.call_method("InitializeModel", args=(settings, settings, catalog))

    def finish(query=""):
        assert model.call_method("BeginFilter", args=(query,))
        for _ in range(100):
            if not model.get_editor_property("Filtering"):
                break
            model.call_method("AdvanceFilter")
        assert not model.get_editor_property("Filtering")

    finish()
    assert [str(x) for x in model.get_editor_property("CategoryKeys")] == ["food_process", "industry_materials", "uncategorized"]
    assert list(model.get_editor_property("RowIsCategory")) == [True, True, True], "Groups start collapsed"
    assert model.call_method("ToggleCategory", args=("food_process",))
    finish()
    assert list(model.get_editor_property("RowIndices"))[:2] == [0, 0]
    assert list(model.get_editor_property("RowIsCategory"))[:2] == [True, False]
    finish("fishery")
    assert len(model.get_editor_property("RowIndices")) == 2, "Search reveals matching type and native category"
    assert model.call_method("ValidateSetting", args=("WorkerOptimizer.reserve", "100"))
    for value in ("-1", "101", "1.5", "garbage"):
        assert not model.call_method("ValidateSetting", args=("WorkerOptimizer.reserve", value))
    for mode in ("off", "day_start", "minutes_5", "minutes_10", "minutes_15"):
        assert model.call_method("ValidateSetting", args=("WorkerOptimizer.auto_assignment", "WorkerOptimizer.ui.auto." + mode))
    assert not model.call_method("ValidateSetting", args=("unrelated.setting", "2"))
    inputs.call_method("Busy", args=(model, True))
    assert not model.call_method("WriteSetting", args=("WorkerOptimizer.reserve", "0"))
    assert not model.call_method("WriteSetting", args=("WorkerOptimizer.auto_assignment", "WorkerOptimizer.ui.auto.minutes_5"))
    assert model.call_method("CanWrite", args=("WorkerOptimizer.auto_assignment", "WorkerOptimizer.ui.auto.off")), "Off remains allowed while busy"
    assert not model.call_method("CanWrite", args=("WorkerOptimizer.type.fishery", "WorkerOptimizer.ui.priority.4"))
    assert str(settings.call_method("TypeOptionId", args=("fishery",))) == "WorkerOptimizer.type.fishery"
    assert str(settings.call_method("CategoryOptionId", args=("food_process",))) == "WorkerOptimizer.category.food_process"
    assert settings.call_method("ResolvePriority", args=("4", "inherit")) == 4
    assert settings.call_method("ResolvePriority", args=("4", "1")) == 1
    unreal.log("WO_SETTINGS_MODEL_TESTS_PASS: native membership, dynamic/uncategorized rows, collapsed/search groups, setting validation, busy guard and Off exception; native persistence remains a packaged check")


run()
