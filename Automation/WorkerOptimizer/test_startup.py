"""Verify compiled startup registration lifecycle; native API writes are editor stubs."""

import json
import unreal


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_Startup.BP_Startup_C")
    assert cls, "Production startup hook does not exist"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def make():
        actor = actors.spawn_actor_from_class(cls, unreal.Vector())
        spawned.append(actor)
        assert actor.call_method("Initialize", args=(actor,))
        assert actor.call_method("Initialize", args=(actor,))
        for name in ("Catalog", "Settings"):
            assert actor.get_editor_property(name).get_outer() == actor
        return actor

    def start_table(actor, table):
        catalog = actor.get_editor_property("Catalog")
        started = catalog.call_method("BeginTable", args=(table,))
        assert actor.call_method("AcceptCatalogStart", args=(started,)) == started
        for _ in range(1000):
            if actor.get_editor_property("Registering") or actor.get_editor_property("StartupDone"):
                break
            actor.call_method("AdvanceStartup")
        return catalog

    def drain(actor):
        requests = []
        while actor.get_editor_property("StartupActive"):
            assert actor.call_method("PrepareRegistration")
            if actor.get_editor_property("StartupDone"):
                break
            index = actor.get_editor_property("Cursor")
            kind = actor.get_editor_property("OptionKinds")[index]
            key = str(actor.get_editor_property("OptionKeys")[index])
            requests.append((kind, key))
            assert actor.call_method("RecordRegistration", args=(True,))
            assert not actor.call_method("RecordRegistration", args=(True,)), "No double confirmation"
        assert actor.get_editor_property("StartupSucceeded")
        assert actor.call_method("StartupStatus") == f"WorkerOptimizer: startup ready; options={len(requests)}"
        return requests

    try:
        actor = make()
        assert actor.call_method("StartupStatus") == "", "No premature success diagnostic"
        real = unreal.load_asset("/Game/Data/GridactorDefs_Sync")
        before = unreal.DataTableFunctionLibrary.export_data_table_to_json_string(real)
        catalog = start_table(actor, real)
        expected_types = [str(x) for x in catalog.get_editor_property("Types")]
        expected_categories = list(dict.fromkeys(str(x) for x in catalog.get_editor_property("Categories") if str(x) != "None"))
        assert list(actor.get_editor_property("OptionLabelKeys"))[1:1 + len(expected_categories)] == [
            "toolbar." + key for key in expected_categories
        ], "Category labels must resolve through the game's localization keys"
        requests = drain(actor)
        assert requests == [(0, "None")] + [(1, k) for k in expected_categories] + [(2, k) for k in expected_types]
        assert actor.get_editor_property("RegisteredCount") == len(requests)
        assert actor.call_method("BeginStartup", args=(actor,)), "Completed startup is idempotent"
        assert not actor.call_method("AdvanceStartup")
        assert len(requests) > 30
        assert before == unreal.DataTableFunctionLibrary.export_data_table_to_json_string(real)

        table = unreal.new_object(unreal.DataTable)
        table.set_editor_property("ignore_missing_fields", True)
        assert unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(table, json.dumps([
            {"Name": "future.first", "toolbarGroup": "future.category", "maxAgents_contextual": 1, "stringKey": "future.title"},
            {"Name": "future.second", "toolbarGroup": "future.category", "maxAgents_contextual": 2},
            {"Name": "future.uncategorized", "maxAgents_contextual": 1},
            {"Name": "future.decor", "maxAgents_contextual": 0},
        ]), real.get_editor_property("row_struct"))
        future = make()
        start_table(future, table)
        labels = list(future.get_editor_property("OptionLabelKeys"))
        assert labels[1] == "toolbar.future.category"
        assert labels[-3:] == ["future.title", "", ""]
        assert future.call_method("ResolveLabel", args=("future.first", "no.such.translation")) == "future.first"
        assert not future.call_method("Initialize", args=(actor,)), "Never swap startup context"
        assert drain(future) == [(0, "None"), (1, "future.category"), (2, "future.first"), (2, "future.second"), (2, "future.uncategorized")]

        failed = make()
        start_table(failed, table)
        assert failed.call_method("PrepareRegistration")
        assert not failed.call_method("RecordRegistration", args=(False,))
        assert failed.get_editor_property("StartupDone") and not failed.get_editor_property("StartupSucceeded")
        assert str(failed.get_editor_property("FailureCode")) == "option_registration_failed"
        assert failed.get_editor_property("RegisteredCount") == 0
        assert failed.call_method("StartupStatus") == "", "Failure must never report readiness"
        assert not failed.call_method("AdvanceStartup")
        assert not failed.call_method("RecordRegistration", args=(True,))

        empty = make()
        for name in unreal.DataTableFunctionLibrary.get_data_table_row_names(table):
            unreal.DataTableFunctionLibrary.remove_data_table_row(table, name)
        start_table(empty, table)
        assert drain(empty) == [(0, "None")]

        native_registration = make()
        start_table(native_registration, table)
        native_registration.call_method("ReceiveTick", args=(0.016,))
        assert native_registration.get_editor_property("StartupDone")
        assert str(native_registration.get_editor_property("FailureCode")) == "option_registration_failed"
        assert native_registration.get_editor_property("RegisteredCount") == 0

        interrupted = make()
        start_table(interrupted, table)
        interrupted.call_method("Shutdown")
        assert str(interrupted.get_editor_property("FailureCode")) == "world_ended"
        assert not interrupted.call_method("PrepareRegistration")

        invalid = make()
        start_table(invalid, None)
        assert invalid.get_editor_property("StartupDone") and not invalid.get_editor_property("StartupSucceeded")
        assert not invalid.get_editor_property("Registering")

        native = make()
        native.call_method("ReceiveBeginPlay")
        assert native.get_editor_property("StartupDone")
        assert str(native.get_editor_property("FailureCode")) == "catalog_unavailable"
        native.call_method("ReceiveTick", args=(0.016,))
        assert native.get_editor_property("RegisteredCount") == 0
        assert not native.get_editor_property("StartupSucceeded"), "Native editor stubs must not be treated as success"
        unreal.log("WO_STARTUP_TESTS_PASS: real/future/empty catalogs, deduplicated categories, inheritance IDs, label fallback, owned objects, loader BeginPlay/Tick, idempotence, native failure and one-shot confirmations; native successful registration remains shipping-only")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
