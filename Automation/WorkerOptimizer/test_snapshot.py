"""Execute the production read-only snapshot against transient game actors."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C")
    assert cls is not None, "Production workforce snapshot does not exist"
    snapshot = unreal.new_object(cls)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []

    def actor(name):
        result = subsystem.spawn_actor_from_class(unreal.load_class(None, "/Script/ProjectArco." + name), unreal.Vector(0, 0, -100000))
        assert result is not None
        spawned.append(result)
        return result

    def worker(number):
        result = actor("Prototype_Agent")
        characteristics = result.get_editor_property("m_characteristics")
        # ID is EditConst; initialize the owned test struct through UE's parser.
        assert characteristics.import_text(f"(ID={number})")
        assert characteristics.get_editor_property("ID") == number
        put(result, "m_characteristics", characteristics)
        return result

    def workplace(number, assigned=None, paused=False, owned=True, component_name="Industry"):
        result = actor("GridActor")
        put(result, "ID", number)
        put(result, "Health", 100)
        put(result, "isPlayerOwned", owned)
        component = None
        if component_name:
            component = result.call_method("AddComponentByClass", args=(unreal.load_class(None, "/Script/ProjectArco." + component_name), False, unreal.Transform(), False))
            data = component.get_editor_property("m_workers")
            assert data.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
            slot = data.get_editor_property("m_workerSlots")[0]
            put(slot, "Agent", assigned)
            put(slot, "bIsRequiredToRun", True)
            put(data, "m_workerSlots", [slot])
            put(data, "bDisabled", paused)
            put(component, "m_workers", data)
        return result, component

    try:
        available, paused_worker, foreign_worker, unknown_worker, free_worker = [worker(i) for i in range(5)]
        active, active_component = workplace(10, available)
        paused, _ = workplace(11, paused_worker, paused=True)
        foreign, _ = workplace(12, foreign_worker, owned=False)
        unknown, _ = workplace(13, component_name=None)
        snapshot.call_method("ResetSnapshot")
        assert not snapshot.call_method("AddBuilding", args=(None,))
        assert snapshot.call_method("AddBuilding", args=(active,))
        assert not snapshot.call_method("AddBuilding", args=(active,)), "Duplicate building admitted"
        for building in (paused, foreign, unknown):
            assert not snapshot.call_method("AddBuilding", args=(building,))
        assert list(snapshot.get_editor_property("Buildings")) == [active]
        assert not snapshot.call_method("AddWorker", args=(available, active)), "Worker phase opened too soon"
        snapshot.call_method("FinishBuildings")
        assert not snapshot.call_method("AddBuilding", args=(unknown,)), "Buildings admitted after phase transition"
        assert snapshot.call_method("AddWorker", args=(available, active))
        assert snapshot.call_method("AddWorker", args=(free_worker, None))
        assert not snapshot.call_method("AddWorker", args=(free_worker, None)), "Duplicate worker admitted"
        for person, reported in ((paused_worker, paused), (foreign_worker, foreign), (unknown_worker, unknown)):
            assert not snapshot.call_method("AddWorker", args=(person, reported)), "Protected workplace worker admitted"
        assert not snapshot.call_method("AddWorker", args=(paused_worker, None)), "Slot evidence must protect even with inconsistent workplace report"
        assert not snapshot.call_method("AddWorker", args=(None, None))
        for field in ("isDummy", "isInNautical", "isBeingManhandled", "pendingRemoval"):
            person = worker(100 + len(spawned))
            state = person.get_editor_property("m_state")
            put(state, field, True)
            put(person, "m_state", state)
            assert not snapshot.call_method("AddWorker", args=(person, None)), field
            assert person in snapshot.get_editor_property("ProtectedWorkers"), field
        assert list(snapshot.get_editor_property("Workers")) == [available, free_worker]
        assert snapshot.call_method("BuildingUnchanged", args=(0,))
        assert not snapshot.call_method("BuildingUnchanged", args=(-1,))
        assert not snapshot.call_method("BuildingUnchanged", args=(1,))
        assert snapshot.call_method("WorkerUnchanged", args=(0, active))
        assert not snapshot.call_method("WorkerUnchanged", args=(0, paused))
        assert snapshot.call_method("WorkerUnchanged", args=(1, None))
        assert not snapshot.call_method("WorkerUnchanged", args=(-1, None))
        assert not snapshot.call_method("WorkerUnchanged", args=(2, None))
        original_workforce = active_component.get_editor_property("m_workers").export_text()
        for field in ("bOvertime", "bDisabled"):
            changed = active_component.get_editor_property("m_workers")
            put(changed, field, True)
            put(active_component, "m_workers", changed)
            assert not snapshot.call_method("BuildingUnchanged", args=(0,)), field
            assert changed.import_text(original_workforce)
            put(active_component, "m_workers", changed)
            assert snapshot.call_method("BuildingUnchanged", args=(0,)), field
        for field in ("bIsRequiredToRun", "bGivesBonus"):
            changed = active_component.get_editor_property("m_workers")
            slots = list(changed.get_editor_property("m_workerSlots"))
            put(slots[0], field, not slots[0].get_editor_property(field))
            put(changed, "m_workerSlots", slots)
            put(active_component, "m_workers", changed)
            assert not snapshot.call_method("BuildingUnchanged", args=(0,)), field
            assert changed.import_text(original_workforce)
            put(active_component, "m_workers", changed)
        characteristics = available.get_editor_property("m_characteristics")
        original_characteristics = characteristics.export_text()
        assert characteristics.import_text("(guild=snapshot_test_changed)")
        put(available, "m_characteristics", characteristics)
        assert not snapshot.call_method("WorkerUnchanged", args=(0, active)), "Guild change missed"
        assert characteristics.import_text(original_characteristics)
        put(available, "m_characteristics", characteristics)
        assert snapshot.call_method("WorkerUnchanged", args=(0, active))
        assert characteristics.import_text('(traits=("scientist"))')
        put(available, "m_characteristics", characteristics)
        assert not snapshot.call_method("WorkerUnchanged", args=(0, active)), "Future-job trait changes must invalidate the plan even if current productivity is unchanged"
        assert characteristics.import_text(original_characteristics)
        put(available, "m_characteristics", characteristics)
        prefab = active.get_editor_property("PrefabInfo")
        original_prefab = prefab.export_text()
        assert prefab.import_text("(prefabKey=snapshot_test_changed_type)")
        put(active, "PrefabInfo", prefab)
        assert not snapshot.call_method("BuildingUnchanged", args=(0,)), "Building type change missed"
        assert prefab.import_text(original_prefab)
        put(active, "PrefabInfo", prefab)
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        snapshot.call_method("BeginCapture", args=(world,))
        for _ in range(1000):
            if snapshot.get_editor_property("CaptureDone"):
                break
            snapshot.call_method("AdvanceCapture")
        assert snapshot.get_editor_property("CaptureDone"), "Capture did not terminate"
        assert snapshot.get_editor_property("SnapshotValid")
        assert active in snapshot.get_editor_property("Buildings")
        assert paused not in snapshot.get_editor_property("Buildings")
        assert paused_worker not in snapshot.get_editor_property("Workers")
        assert foreign_worker not in snapshot.get_editor_property("Workers")
        # GetWorkplace is native/stubbed in the editor. Its paused/unknown return
        # values are tested explicitly through AddWorker above, not inferred here.
        original_counts = (len(snapshot.get_editor_property("Buildings")), len(snapshot.get_editor_property("Workers")))
        snapshot.call_method("AdvanceCapture")
        assert original_counts == (len(snapshot.get_editor_property("Buildings")), len(snapshot.get_editor_property("Workers")))
        active_index = list(snapshot.get_editor_property("Buildings")).index(active)
        before = active_component.get_editor_property("m_workers")
        put(before, "bDisabled", True)
        put(active_component, "m_workers", before)
        assert not snapshot.call_method("BuildingUnchanged", args=(active_index,)), "Pause changed during planning was missed"
        put(before, "bDisabled", False)
        slots = list(before.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", free_worker)
        put(before, "m_workerSlots", slots)
        put(active_component, "m_workers", before)
        assert not snapshot.call_method("BuildingUnchanged", args=(active_index,)), "Assignment changed during planning was missed"
        state = free_worker.get_editor_property("m_state")
        put(state, "pendingRemoval", True)
        put(free_worker, "m_state", state)
        free_index = list(snapshot.get_editor_property("Workers")).index(free_worker)
        assert not snapshot.call_method("WorkerUnchanged", args=(free_index, None))
        snapshot.call_method("ResetSnapshot")
        for field in ("Buildings", "Workforces", "Workers", "WorkerWorkplaces", "ProtectedWorkers", "Characteristics", "States"):
            assert len(snapshot.get_editor_property(field)) == 0, field
        assert snapshot.get_editor_property("SnapshotValid")
        assert active_component.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == free_worker
        collision_a, _ = workplace(50)
        collision_b, _ = workplace(50)
        assert snapshot.call_method("AddBuilding", args=(collision_a,))
        assert not snapshot.call_method("AddBuilding", args=(collision_b,))
        assert not snapshot.get_editor_property("SnapshotValid"), "Ambiguous building ID did not invalidate snapshot"
        snapshot.call_method("ResetSnapshot")
        snapshot.call_method("FinishBuildings")
        collision_worker_a, collision_worker_b = worker(1000), worker(1000)
        assert snapshot.call_method("AddWorker", args=(collision_worker_a, None))
        assert not snapshot.call_method("AddWorker", args=(collision_worker_b, None))
        assert not snapshot.get_editor_property("SnapshotValid"), "Ambiguous worker ID did not invalidate snapshot"
        snapshot.call_method("ResetSnapshot")
        snapshot.call_method("FinishBuildings")
        ch = collision_worker_a.get_editor_property("m_characteristics")
        assert ch.import_text('(traits=("scientist","monarchist"))')
        put(collision_worker_a, "m_characteristics", ch)
        assert snapshot.call_method("AddWorker", args=(collision_worker_a, None))
        assert ch.import_text('(traits=("monarchist","scientist"))')
        put(collision_worker_a, "m_characteristics", ch)
        assert snapshot.call_method("WorkerUnchanged", args=(0, None)), "Trait set ordering is irrelevant"
        assert ch.import_text('(traits=("monarchist","teacher"))')
        put(collision_worker_a, "m_characteristics", ch)
        assert not snapshot.call_method("WorkerUnchanged", args=(0, None)), "Equal-sized trait replacement must invalidate the plan"
        snapshot.call_method("BeginCapture", args=(None,))
        assert snapshot.get_editor_property("CaptureDone") and not snapshot.get_editor_property("SnapshotValid")
        unreal.log("WO_SNAPSHOT_TESTS_PASS: incremental discovery, phases, duplicate references/IDs, paused/unknown/foreign protection, unavailable workers, stale type/roles/guild/assignments, reset")
    finally:
        for spawned_actor in reversed(spawned):
            subsystem.destroy_actor(spawned_actor)


run()
