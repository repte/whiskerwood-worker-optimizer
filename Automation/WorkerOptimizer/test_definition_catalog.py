"""Read actual cooked and transient definition tables with production Blueprint."""

import json
import unreal


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_DefinitionCatalog.BP_DefinitionCatalog_C")
    assert cls, "Production definition catalog does not exist"
    catalog = unreal.new_object(cls)

    def capture(table, expected=True):
        started = catalog.call_method("BeginTable", args=(table,))
        if started:
            for _ in range(1000):
                if catalog.get_editor_property("CatalogDone"):
                    break
                catalog.call_method("AdvanceCatalog")
        assert catalog.get_editor_property("CatalogDone")
        assert catalog.get_editor_property("CatalogSucceeded") == expected
        return dict(zip((str(x) for x in catalog.get_editor_property("Types")),
                        (str(x) for x in catalog.get_editor_property("Categories"))))

    real = unreal.load_asset("/Game/Data/GridactorDefs_Sync")
    assert real
    before = unreal.DataTableFunctionLibrary.export_data_table_to_json_string(real)
    result = capture(real)
    assert result["farm"] == "farming"
    assert result["woodcutter"] == "camps"
    assert result["fishery"] == "food_process"
    assert "stairs" not in result and "flowerbed" not in result
    assert before == unreal.DataTableFunctionLibrary.export_data_table_to_json_string(real), "Catalog must not change game data"
    assert len(catalog.get_editor_property("StringKeys")) == len(result)
    catalog.call_method("AdvanceCatalog")
    assert catalog.get_editor_property("CatalogSucceeded")

    table = unreal.new_object(unreal.DataTable)
    table.set_editor_property("ignore_missing_fields", True)
    rows = [
        {"Name": "future.workplace", "toolbarGroup": "future.category", "maxAgents_contextual": 4, "stringKey": "future.title"},
        {"Name": "future.house", "toolbarGroup": "housing", "maxAgents_contextual": 5, "asHouseTier": 2},
        {"Name": "future.decor", "toolbarGroup": "decor", "maxAgents_contextual": 0},
    ]
    assert unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
        table, json.dumps(rows), real.get_editor_property("row_struct"))
    assert capture(table) == {"future.workplace": "future.category"}
    assert list(catalog.get_editor_property("StringKeys")) == ["future.title"]
    assert not capture(None, False)
    assert not capture(unreal.load_asset("/Game/Data/SystemTunes"), False)
    for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(table):
        unreal.DataTableFunctionLibrary.remove_data_table_row(table, name)
    assert capture(table) == {}
    assert not catalog.call_method("BeginFromContext", args=(None,))
    unreal.log("WO_DEFINITION_CATALOG_TESTS_PASS: actual cooked table read, future type/category discovery, housing/decor omission, label keys, read-only operation, empty/wrong/null tables and reuse")


run()
