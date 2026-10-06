"""Compiled storage contract and native serialization, not a Python history model."""
import uuid
import time
import os
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType

ROOT = "/Game/Mods/WorkerOptimizer/"
input_boundary = None

def put(obj, name, value):
    if str(obj.get_class().get_name()) == "BP_LogbookNativeBoundary_C" and name in ("Index", "IndexReady", "LoadedFlags"):
        obj.call_method("FixtureSet" + name, args=(value,))
        return
    try:
        obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    except Exception:
        if input_boundary is None: raise
        input_boundary.call_method("FixturePatch" + str(obj.get_class().get_name()).removesuffix("_C") + name, args=(obj, value))

def run():
    global input_boundary
    coordinator = unreal.load_asset(ROOT + "DA_LogbookIO")
    assert coordinator, "World-independent IO coordinator does not exist"
    cls = unreal.load_class(None, ROOT + "BP_Logbook.BP_Logbook_C")
    assert cls, "Production isolated history service does not exist"
    book = unreal.new_object(cls)
    assert not book.call_method("BeginLoad", args=("",))
    assert str(book.get_editor_property("StorageFailure")) == "identity_unavailable"
    assert book.get_editor_property("SessionOnly") and str(book.get_editor_property("PersistenceStatus")) == "session_only"
    assert not book.call_method("ValidStorageId", args=("../player",))
    assert not book.call_method("ValidStorageId", args=("WorkerOptimizer_History_v1_bad/path",))
    assert book.call_method("ValidStorageId", args=("WorkerOptimizer_History_v1_" + "a" * 32,))
    fixture = None
    graph = book = report = payload = loaded = None
    slots = []
    completions = []
    try:
        fixture = BP.create("/Game/WorkerOptimizerTests", "BP_LogbookNativeBoundary", cls)
        graph = BP.add_function_graph(fixture, "StartNativeRequest")
        BP.write_graph_dsl(graph, "(fn StartNativeRequest () (return true))")
        BP.compile_blueprint(fixture, warnings_as_errors=True)
        store_cls = unreal.load_class(None, ROOT + "BP_LogbookStore.BP_LogbookStore_C")
        index_cls = unreal.load_class(None, ROOT + "BP_LogbookIndex.BP_LogbookIndex_C")
        report_cls = unreal.load_class(None, ROOT + "BP_RunReport.BP_RunReport_C")
        for name, kind in (("Index", index_cls), ("IndexReady", "bool"), ("LoadedFlags", "bool[]")):
            graph = BP.add_function_graph(fixture, "FixtureSet" + name)
            if isinstance(kind, str): BP.add_function_param(graph, "Value", kind.removesuffix("[]"), True, container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
            else: BP.add_object_function_param(graph, "Value", kind, True)
            BP.write_graph_dsl(graph, f"(fn FixtureSet{name} (Value) (Variables|Default|Set{name} Value))")
        patches = [("BP_LogbookStore", store_cls, "SchemaVersion", "int"), ("BP_LogbookStore", store_cls, "AffectedBuildingIdsOffsets", "int[]")]
        patches += [("BP_RunReport", report_cls, name, kind) for name, kind in (("GroupReasons", "name[]"), ("GroupTypes", "name[]"), ("GroupCounts", "int[]"), ("GroupStarts", "int[]"), ("GroupIdCounts", "int[]"), ("AffectedBuildingIds", "int[]"), ("PolicyTypes", "name[]"), ("PolicyTypeValues", "int[]"))]
        for owner, owner_cls, name, kind in patches:
            method = "FixturePatch" + owner + name
            graph = BP.add_function_graph(fixture, method)
            BP.add_object_function_param(graph, "Owner", owner_cls, True)
            BP.add_function_param(graph, "Value", kind.removesuffix("[]"), True, container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
            BP.write_graph_dsl(graph, f"(fn {method} (Owner Value) (Class|{owner.replace('_', '')}|Set{name} :self Owner :{name} Value))")
        BP.compile_blueprint(fixture, warnings_as_errors=True)
        input_boundary = unreal.new_object(fixture.generated_class())
        def fresh():
            value = unreal.new_object(fixture.generated_class())
            put(value, "Index", unreal.new_object(index_cls))
            put(value, "IndexReady", True)
            return value
        def terminal(identity, number, large=False):
            value = unreal.new_object(report_cls)
            assert value.call_method("BeginReport", args=("run-" + str(number), "manual", identity, unreal.MathLibrary.utc_now(), 0))
            assert value.call_method("CloseUnavailable", args=("cancelled", "cancelled", None))
            if large:
                put(value, "GroupReasons", ["no_eligible_candidate"] * 20)
                put(value, "GroupTypes", ["fixture" + str(i) for i in range(20)])
                put(value, "GroupCounts", [50] * 20)
                put(value, "GroupStarts", [i * 50 for i in range(20)])
                put(value, "GroupIdCounts", [50] * 20)
                put(value, "AffectedBuildingIds", list(range(1000)))
                put(value, "PolicyTypes", ["type" + str(i) for i in range(100)])
                put(value, "PolicyTypeValues", [1] * 100)
            return value
        def acknowledge(value, success=True, replacement=None):
            assert value.get_editor_property("InFlight")
            obj = replacement if replacement is not None else value.get_editor_property("RequestObject")
            completions.append((str(value.get_editor_property("RequestKind")), str(value.get_editor_property("RequestSlot"))))
            result = value.call_method("CompleteRequest", args=(obj, success))
            assert result == success, (result, value.get_editor_property("StorageFailure"))
        def advance_until(value, predicate, bound=200000, callbacks=True):
            for step in range(bound):
                if predicate(): return step
                assert str(value.get_editor_property("StorageFailure")) in ("None", "identity_unavailable"), (value.get_editor_property("StorageFailure"), value.get_editor_property("RequestKind"), value.get_editor_property("RequestSlot"), [(s.get_editor_property("Identity"), s.get_editor_property("StorageId")) for s in value.get_editor_property("Stores")])
                value.call_method("AdvanceStorage")
                if callbacks and value.get_editor_property("InFlight"):
                    kind = str(value.get_editor_property("RequestKind"))
                    assert kind.startswith("save_"), "Tests never silently substitute a persisted payload load"
                    acknowledge(value)
            raise AssertionError("Finite storage completion bound exceeded")
        def failed_retention():
            def advance_failed(value, predicate, bound=5000):
                for _ in range(bound):
                    if predicate(): return
                    value.call_method("AdvanceStorage")
                    assert not value.get_editor_property("InFlight"), "Failure must gate disk IO only"
                raise AssertionError("Failed storage stopped bounded in-memory retention")
            failing = fresh()
            identity = "failed-write-" + uuid.uuid4().hex
            assert failing.call_method("BeginLoad", args=(identity,))
            advance_until(failing, lambda: failing.get_editor_property("Ready"))
            assert failing.call_method("AppendReport", args=(terminal(identity, 0),))
            advance_until(failing, lambda: failing.get_editor_property("InFlight"), callbacks=False)
            acknowledge(failing, False)
            assert failing.call_method("AppendReport", args=(terminal(identity, 1),))
            advance_failed(failing, lambda: failing.get_editor_property("Stage") > 0)
            staged = failing.get_editor_property("Report")
            for i in range(2, 57): assert failing.call_method("AppendReport", args=(terminal(identity, i),))
            pending = list(failing.get_editor_property("PendingReports"))
            assert pending[0] == staged and len(pending) == 51, "Keep staged plus newest50 accepted reports"
            advance_failed(failing, lambda: not failing.get_editor_property("PendingReports"))
            store = failing.get_editor_property("Stores")[0]
            assert list(store.get_editor_property("RunId")) == ["run-" + str(i) for i in range(7, 57)]
            assert failing.get_editor_property("Dirty") and str(failing.get_editor_property("StorageFailure")) == "history_storage_failed"
            assert failing.call_method("RetryStorage")
            advance_until(failing, lambda: not failing.get_editor_property("Dirty"))
            assert list(store.get_editor_property("RunId")) == ["run-" + str(i) for i in range(7, 57)]
            unloaded = fresh()
            raw = "Unloaded-" + uuid.uuid4().hex
            assert unloaded.call_method("BeginLoad", args=(raw,))
            advance_until(unloaded, lambda: unloaded.get_editor_property("Ready"))
            original = unloaded.get_editor_property("Stores")[0]
            slot = original.get_editor_property("StorageId")
            slots.append(slot)
            assert unreal.GameplayStatics.save_game_to_slot(original, slot, 0)
            put(unloaded, "LoadedFlags", [False])
            assert unloaded.call_method("BeginRequest", args=("load_payload", 0, None))
            acknowledge(unloaded, False)
            for raw_identity in (raw, raw.upper()):
                for i in range(55): assert unloaded.call_method("AppendReport", args=(terminal(raw_identity, i),))
            pending = list(unloaded.get_editor_property("PendingReports"))
            assert len(pending) == 100
            for raw_identity in (raw, raw.upper()):
                assert [r.get_editor_property("RunId") for r in pending if r.get_editor_property("SaveIdentity") == raw_identity] == ["run-" + str(i) for i in range(5, 55)]
            assert unloaded.call_method("AppendReport", args=(terminal("", 999),))
            advance_failed(unloaded, lambda: unloaded.get_editor_property("Stage") == 0 and len(unloaded.get_editor_property("PendingReports")) == 100 and unloaded.get_editor_property("SessionWorkspace") >= 0 and len(unloaded.get_editor_property("Stores")[unloaded.get_editor_property("SessionWorkspace")].get_editor_property("RunId")) == 1)
            assert len(unloaded.get_editor_property("PendingReports")) == 100, "Blocked identity must not starve session-only history"
            assert unloaded.call_method("BeginLoad", args=(raw.upper(),))
            assert unloaded.call_method("RetryStorage")
            for _ in range(20000):
                unloaded.call_method("AdvanceStorage")
                if unloaded.get_editor_property("InFlight"):
                    kind = str(unloaded.get_editor_property("RequestKind"))
                    if kind == "load_payload": acknowledge(unloaded, replacement=unreal.GameplayStatics.load_game_from_slot(unloaded.get_editor_property("RequestSlot"), 0))
                    else: acknowledge(unloaded)
                if not unloaded.get_editor_property("Dirty"): break
            else: raise AssertionError("Bounded failed-history retry did not complete")
            for value in unloaded.get_editor_property("Stores"):
                if value.get_editor_property("Identity") in (raw, raw.upper()):
                    assert list(value.get_editor_property("RunId")) == ["run-" + str(i) for i in range(5, 55)], (value.get_editor_property("Identity"), list(value.get_editor_property("RunId")), len(unloaded.get_editor_property("PendingReports")), unloaded.get_editor_property("Stage"))
            assert unloaded.get_editor_property("ActiveIdentity") == raw.upper()
            assert unloaded.get_editor_property("Stores")[unloaded.get_editor_property("SessionWorkspace")].get_editor_property("SaveIdentity") == [""]
            unreal.log("WO_LOGBOOK_FAILURE_RETENTION_PASS: failed-write loaded retention, staged protection, newest50 per exact unloaded identity, session-only nonstarvation, original identity and retry")
        if os.environ.get("WO_LOGBOOK_FAILURE_ONLY") == "1":
            failed_retention()
            return
        stem = uuid.uuid4().hex
        a, b = "a/b-" + stem, "a_b-" + stem
        session_book = unreal.new_object(fixture.generated_class())
        assert not session_book.call_method("BeginLoad", args=("",))
        before = len(completions)
        assert session_book.call_method("AppendReport", args=(terminal("", 0),))
        advance_until(session_book, lambda: not session_book.get_editor_property("Dirty"))
        assert session_book.call_method("GetRunCount") == 1
        assert len(completions) == before and not session_book.get_editor_property("InFlight")
        assert not session_book.get_editor_property("PersistenceRequested")
        assert session_book.get_editor_property("Index") is None and not session_book.get_editor_property("IndexReady")
        put(session_book, "Index", unreal.new_object(index_cls))
        put(session_book, "IndexReady", True)
        first_identity = "first-save-" + stem
        assert session_book.call_method("BeginLoad", args=(first_identity,))
        advance_until(session_book, lambda: session_book.get_editor_property("Ready"))
        assert session_book.call_method("GetRunCount") == 0
        assert session_book.call_method("AppendReport", args=(terminal("", 1),))
        advance_until(session_book, lambda: not session_book.get_editor_property("Dirty"))
        assert session_book.call_method("GetRunCount") == 0
        assert len(session_book.get_editor_property("Stores")[0].get_editor_property("RunId")) == 2
        new_world = fresh()
        assert not new_world.call_method("BeginLoad", args=("",))
        assert new_world.call_method("GetRunCount") == 0
        book = fresh()
        assert book.call_method("BeginLoad", args=(a,))
        advance_until(book, lambda: book.get_editor_property("Ready"))
        report = terminal(a, 0)
        assert book.call_method("AppendReport", args=(report,))
        assert book.call_method("AppendReport", args=(report,))
        advance_until(book, lambda: book.call_method("GetRunCount") == 1 and not book.get_editor_property("Dirty"))
        assert book.call_method("AppendReport", args=(terminal(a, 0),))
        advance_until(book, lambda: not book.get_editor_property("Dirty"))
        assert book.call_method("GetRunCount") == 1
        original = book.get_editor_property("Stores")[0]
        slot_a = original.get_editor_property("StorageId")
        slots.append(slot_a)
        assert unreal.GameplayStatics.save_game_to_slot(original, slot_a, 0)
        loaded = unreal.GameplayStatics.load_game_from_slot(slot_a, 0)
        assert book.call_method("ValidateStore", args=(loaded, a, slot_a))
        assert list(loaded.get_editor_property("RunId")) == ["run-0"]
        assert list(loaded.get_editor_property("SaveIdentity")) == [a]
        put(loaded, "SchemaVersion", 2)
        assert not book.call_method("ValidateStore", args=(loaded, a, slot_a))
        put(loaded, "SchemaVersion", 1)
        put(loaded, "AffectedBuildingIdsOffsets", [5])
        assert not book.call_method("ValidateStore", args=(loaded, a, slot_a))
        assert book.call_method("BeginLoad", args=(b,))
        advance_until(book, lambda: book.get_editor_property("Ready"))
        assert book.call_method("GetRunCount") == 0
        slot_b = book.get_editor_property("Stores")[1].get_editor_property("StorageId")
        assert slot_a != slot_b and book.call_method("ValidStorageId", args=(slot_b,))
        # A run begun in A is still attributed to A after the active identity changes.
        assert book.call_method("AppendReport", args=(terminal(a, 1),))
        advance_until(book, lambda: not book.get_editor_property("Dirty"))
        assert book.call_method("GetRunCount") == 0
        assert len(book.get_editor_property("Stores")[0].get_editor_property("RunId")) == 2
        assert str(book.get_editor_property("ActiveIdentity")) == b
        # Immutable old revision finishes after another identity and a newer append.
        assert book.call_method("AppendReport", args=(terminal(a, 2),))
        advance_until(book, lambda: book.get_editor_property("InFlight"), callbacks=False)
        captured_slot = book.get_editor_property("RequestSlot")
        captured_revision = book.get_editor_property("RequestRevision")
        snapshot = book.get_editor_property("RequestObject")
        assert book.call_method("BeginLoad", args=(a,))
        assert book.call_method("AppendReport", args=(terminal(a, 3),))
        advance_until(book, lambda: len(book.get_editor_property("Stores")[0].get_editor_property("RunId")) == 4 and book.get_editor_property("Stage") == 0, callbacks=False)
        assert book.get_editor_property("RequestSlot") == captured_slot
        assert len(snapshot.get_editor_property("RunId")) == 3
        acknowledge(book)
        assert book.get_editor_property("Dirty"), "Old save cannot clear a newer dirty revision"
        advance_until(book, lambda: book.get_editor_property("InFlight"), callbacks=False)
        assert book.get_editor_property("RequestRevision") > captured_revision
        acknowledge(book, False)
        assert book.get_editor_property("Dirty")
        assert str(book.get_editor_property("StorageFailure")) == "history_storage_failed"
        assert book.call_method("RetryStorage")
        advance_until(book, lambda: not book.get_editor_property("Dirty"))
        assert unreal.GameplayStatics.save_game_to_slot(original, slot_a, 0)
        registry_slot = "WorkerOptimizer_History_v1_" + uuid.uuid4().hex
        slots.append(registry_slot)
        assert unreal.GameplayStatics.save_game_to_slot(book.get_editor_property("Index"), registry_slot, 0)
        registry = unreal.GameplayStatics.load_game_from_slot(registry_slot, 0)
        assert book.call_method("ValidateIndex", args=(registry,))
        assert list(registry.get_editor_property("Identities")) == [a, b]
        assert list(registry.get_editor_property("StorageIds")) == [slot_a, slot_b]
        assert book.call_method("BeginLoad", args=(a.upper(),))
        advance_until(book, lambda: book.get_editor_property("Ready"))
        assert book.call_method("GetRunCount") == 0
        assert len(book.get_editor_property("Stores")) == 3, "Raw identity lookup must be case-sensitive"
        assert book.get_editor_property("Stores")[2].get_editor_property("StorageId") not in (slot_a, slot_b)
        # Existing sidecar wins over loading an older player snapshot of that slot.
        fresh_book = fresh()
        put(fresh_book, "Index", registry)
        assert fresh_book.call_method("BeginLoad", args=(a,))
        advance_until(fresh_book, lambda: fresh_book.get_editor_property("InFlight"), callbacks=False)
        assert str(fresh_book.get_editor_property("RequestKind")) == "load_payload"
        assert fresh_book.get_editor_property("RequestSlot") == slot_a
        assert not fresh_book.call_method("CompleteRequest", args=(unreal.new_object(index_cls), True))
        assert str(fresh_book.get_editor_property("StorageFailure")) == "invalid_history_file"
        assert fresh_book.call_method("RetryStorage")
        advance_until(fresh_book, lambda: fresh_book.get_editor_property("InFlight"), callbacks=False)
        loaded = unreal.GameplayStatics.load_game_from_slot(slot_a, 0)
        put(loaded, "SchemaVersion", 2)
        assert not fresh_book.call_method("CompleteRequest", args=(loaded, True))
        assert str(fresh_book.get_editor_property("StorageFailure")) == "invalid_history_file"
        assert fresh_book.call_method("RetryStorage")
        advance_until(fresh_book, lambda: fresh_book.get_editor_property("InFlight"), callbacks=False)
        put(loaded, "SchemaVersion", 1)
        assert fresh_book.call_method("BeginLoad", args=(b,))
        assert fresh_book.call_method("CompleteRequest", args=(loaded, True))
        assert str(fresh_book.get_editor_property("ActiveIdentity")) == b
        assert not fresh_book.get_editor_property("Ready"), "Stale load must not expose A as B"
        advance_until(fresh_book, lambda: fresh_book.get_editor_property("Ready"))
        assert fresh_book.call_method("GetRunCount") == 0
        assert fresh_book.call_method("BeginLoad", args=(a,))
        advance_until(fresh_book, lambda: fresh_book.get_editor_property("Ready"))
        assert fresh_book.call_method("GetRunCount") == 4, "Older player state cannot roll back the same-slot sidecar"
        # Required large-history fixture: 50 owned records, then oldest eviction.
        large_identity = "large-" + uuid.uuid4().hex
        large_book = fresh()
        assert large_book.call_method("BeginLoad", args=(large_identity,))
        advance_until(large_book, lambda: large_book.get_editor_property("Ready"))
        for i in range(51):
            assert large_book.call_method("AppendReport", args=(terminal(large_identity, i, True),))
        before_saves = sum(kind == "save_payload" for kind, slot in completions)
        steps = advance_until(large_book, lambda: not large_book.get_editor_property("Dirty"))
        assert sum(kind == "save_payload" for kind, slot in completions) - before_saves == 1, "Queued writes must coalesce"
        payload = large_book.get_editor_property("Stores")[0]
        assert large_book.call_method("GetRunCount") == 50
        assert payload.get_editor_property("RunId")[0] == "run-1"
        assert payload.get_editor_property("RunId")[-1] == "run-50"
        large_slot = payload.get_editor_property("StorageId")
        slots.append(large_slot)
        assert large_book.call_method("ValidateStore", args=(payload, large_identity, large_slot))
        start = time.perf_counter()
        assert unreal.GameplayStatics.save_game_to_slot(payload, large_slot, 0)
        save_ms = (time.perf_counter() - start) * 1000
        loaded = unreal.GameplayStatics.load_game_from_slot(large_slot, 0)
        assert large_book.call_method("ValidateStore", args=(loaded, large_identity, large_slot))
        assert len(loaded.get_editor_property("AffectedBuildingIds")) == 50000
        assert len(loaded.get_editor_property("PolicyTypeValues")) == 5000
        assert list(loaded.get_editor_property("RunId")) == list(payload.get_editor_property("RunId"))
        assert large_book.call_method("AppendReport", args=(terminal(large_identity, 52),))
        assert not large_book.call_method("CloseStorage")
        assert str(large_book.get_editor_property("StorageFailure")) == "history_unflushed"
        assert large_book.get_editor_property("Dirty")
        # Closed sessions cannot release a submitted write early; a new service
        # waits before loading either the registry or the same colony payload.
        old_service, next_service = fresh(), fresh()
        registry = old_service.get_editor_property("Index")
        assert old_service.call_method("BeginRequest", args=("save_index", -1, registry))
        request = old_service.get_editor_property("RequestContext")
        assert registry.get_editor_property("IOCoordinator") == coordinator
        assert coordinator.get_editor_property("CurrentRequest") == request
        assert not old_service.call_method("CloseStorage")
        put(next_service, "Index", None)
        put(next_service, "IndexReady", False)
        assert next_service.call_method("BeginLoad", args=(a,))
        assert not next_service.call_method("AdvanceStorage")
        assert not next_service.get_editor_property("InFlight") and next_service.get_editor_property("Index") is None
        assert not request.call_method("Complete", args=(registry, True))
        assert not coordinator.get_editor_property("Busy"), "Closed-owner completion must release the write gate"
        assert next_service.call_method("AdvanceStorage")
        if next_service.get_editor_property("InFlight"):
            abandoned = next_service.get_editor_property("RequestContext")
            next_service.call_method("CloseStorage")
            assert not coordinator.get_editor_property("Busy")
            survivor = fresh()
            assert survivor.call_method("BeginRequest", args=("save_index", -1, survivor.get_editor_property("Index")))
            assert not abandoned.call_method("Complete", args=(registry, True))
            assert coordinator.get_editor_property("Busy"), "Abandoned read must not unlock the later write"
            acknowledge(survivor)
        # Verify the compiled anchor chain. The internal native factory is not
        # exposed to Python; real unload callback delivery is a game test.
        anchor_service = fresh()
        registry = anchor_service.get_editor_property("Index")
        assert anchor_service.call_method("BeginRequest", args=("save_index", -1, registry))
        unreal.SystemLibrary.collect_garbage()
        assert registry.get_editor_property("IOCoordinator") == coordinator
        assert coordinator.get_editor_property("CurrentRequest") == anchor_service.get_editor_property("RequestContext")
        acknowledge(anchor_service)
        unreal.log(f"WO_LOGBOOK_SERIALIZATION records=50 groups=1000 ids=50000 policy_types=5000 save_to_slot_wall_ms={save_ms:.3f} bounded_steps={steps}; native serialization plus platform write, not pure serialization or shipping frame time")
        production = unreal.load_asset(ROOT + "BP_LogbookIORequest")
        async_nodes = [n for n in BP.get_node_infos(BP.find_nodes(BP.get_graph(production, "EventGraph"))) if 'Async' in n.type_id and 'Slot' in n.type_id]
        assert len(async_nodes) == 2
        assert all({"Completed", "SaveGame", "bSuccess"} <= {p.name for p in n.output_pins} for n in async_nodes)
        for slot in (slot_a, slot_b, large_slot):
            assert str(slot).startswith("WorkerOptimizer_History_v1_")
        assert all(slot == "WorkerOptimizer_HistoryIndex_v1" or slot.startswith("WorkerOptimizer_History_v1_") for kind, slot in completions)
        failed_retention()
        unreal.log("WO_LOGBOOK_TESTS_PASS: primitive native roundtrip; wrong class/schema/offsets; exact identity separation; original run identity; idempotence; coalescing; immutable outstanding save; newer dirty revision; retry; stale load; active-only payload; 51st oldest eviction; unload failure")
    finally:
        for slot in slots:
            if unreal.GameplayStatics.does_save_game_exist(slot, 0):
                assert unreal.GameplayStatics.delete_game_in_slot(slot, 0)
        had_fixture = fixture is not None
        book = fresh_book = large_book = session_book = new_world = old_service = next_service = anchor_service = survivor = request = abandoned = proxy = report = payload = loaded = original = snapshot = registry = graph = fixture = None
        put(coordinator, "Busy", False)
        put(coordinator, "CurrentRequest", None)
        assert unreal.EditorAssetLibrary.save_loaded_asset(coordinator)
        fresh = terminal = acknowledge = advance_until = None
        input_boundary = None
        unreal.SystemLibrary.collect_garbage()
        if had_fixture:
            assert unreal.EditorAssetLibrary.delete_asset("/Game/WorkerOptimizerTests/BP_LogbookNativeBoundary")

run()
