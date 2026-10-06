"""Compiled failure attribution without weakening any existing validation outcome."""
import unreal

def put(obj, field, value):
    obj.set_editor_property(field, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    def spawn(cls):
        value = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
        spawned.append(value)
        return value
    try:
        controller = spawn(load("BP_WorkerOptimizer"))
        bridge = spawn(load("BP_ActionBridge"))
        assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
        assert controller.call_method("Initialize", args=(controller, bridge))
        snapshot = controller.get_editor_property("Snapshot")
        snapshot.call_method("ResetSnapshot")
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None", "Missing first-failure diagnostic/reset contract"
        building = spawn(unreal.load_class(None, "/Script/ProjectArco.GridActor"))
        for field, value in (("ID", 700), ("isPlayerOwned", True), ("Health", 100)): put(building, field, value)
        component = building.call_method("AddComponentByClass", args=(unreal.load_class(None, "/Script/ProjectArco.Industry"), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")
        put(component, "m_workers", workforce)
        worker = spawn(unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent"))
        characteristics = worker.get_editor_property("m_characteristics")
        assert characteristics.import_text("(ID=701)")
        put(worker, "m_characteristics", characteristics)
        state = worker.get_editor_property("m_state")
        put(state, "derived_productivity", 93.0)
        put(state, "derived_speedPercent", 100.0)
        put(worker, "m_state", state)
        slot = workforce.get_editor_property("m_workerSlots")[0]
        put(slot, "Agent", worker)
        put(workforce, "m_workerSlots", [slot])
        put(component, "m_workers", workforce)
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        assert snapshot.call_method("AddWorker", args=(worker, building))
        frozen = tuple(value.export_text() for value in snapshot.get_editor_property("States"))
        assert snapshot.call_method("BuildingUnchanged", args=(0,))
        assert snapshot.call_method("WorkerUnchanged", args=(0, building))
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None"
        assert not snapshot.call_method("ConfirmAction", args=(0, 0, 0, True, None)), "Unpropagated fire remains unconfirmed"
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None", "Expected confirmation probe must not poison terminal evidence"
        assert snapshot.get_editor_property("ValidationProbeDepth") == 0
        put(state, "derived_productivity", 103.0)
        put(worker, "m_state", state)
        assert snapshot.call_method("WorkerUnchanged", args=(0, building)), "Ordinary derived productivity progression93->103 is not an identity/placement change"
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None"
        original_characteristics = characteristics.export_text()
        assert characteristics.import_text("(education=Master)")
        put(worker, "m_characteristics", characteristics)
        assert not snapshot.call_method("WorkerUnchanged", args=(0, building)), "Education changes must still reject the captured plan"
        assert str(snapshot.get_editor_property("ValidationGuard")) == "worker.characteristics"
        assert characteristics.import_text(original_characteristics)
        put(worker, "m_characteristics", characteristics)
        snapshot.call_method("ResetValidationFailure")
        put(state, "derived_speedPercent", 120.0)
        put(worker, "m_state", state)
        assert snapshot.call_method("WorkerUnchanged", args=(0, building)), "Frozen soft quality must not reject normal speed progression"
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None"
        put(building, "ID", 702)
        assert not snapshot.call_method("BuildingUnchanged", args=(0,))
        assert str(snapshot.get_editor_property("ValidationGuard")) == "building.id"
        assert snapshot.get_editor_property("ValidationIndex") == 0
        assert snapshot.get_editor_property("ValidationCaptured") == "700" and snapshot.get_editor_property("ValidationLive") == "702"
        assert not snapshot.call_method("WorkerUnchanged", args=(0, None))
        assert str(snapshot.get_editor_property("ValidationGuard")) == "building.id", "Never replace first failing hard guard"
        assert tuple(value.export_text() for value in snapshot.get_editor_property("States")) == frozen, "Evidence must not rewrite captured values"
        put(building, "ID", 700)
        snapshot.call_method("ResetValidationFailure")
        put(worker, "m_state", state)
        put(building, "ID", 702)
        assert not snapshot.call_method("BuildingUnchanged", args=(0,))
        assert str(snapshot.get_editor_property("ValidationGuard")) == "building.id"
        phase = controller.get_editor_property("Phase")
        runner = controller.get_editor_property("Runner")
        counts = {label: runner.get_editor_property(field) for label, field in (("queued", "QueuedCount"), ("confirmed", "AppliedCount"), ("fires", "ConfirmedFires"), ("hires", "ConfirmedHires"))}
        assert not controller.call_method("FailRun", args=("world_changed",))
        assert controller.get_editor_property("RunDone") and not controller.get_editor_property("RunActive")
        assert str(controller.get_editor_property("FailureCode")) == "world_changed"
        message = controller.get_editor_property("LastFailureDiagnostic")
        for part in ("WorkerOptimizer stopped: world_changed", f"phase={phase}", "guard=building.id", "index=0", "captured=700", "live=702", *(f"{label}={value}" for label, value in counts.items())):
            assert part in message, (part, message)
        assert not controller.call_method("FailRun", args=("world_changed",))
        assert controller.get_editor_property("LastFailureDiagnostic") == message, "Repeated terminal pump must not emit/rebuild failure"
        snapshot.call_method("ResetSnapshot")
        assert str(snapshot.get_editor_property("ValidationGuard")) == "None" and snapshot.get_editor_property("ValidationIndex") == -1
        assert snapshot.get_editor_property("ValidationCaptured") == snapshot.get_editor_property("ValidationLive") == ""
        assert controller.call_method("BuildFailureDiagnostic", args=("cancelled",)) == "WorkerOptimizer stopped: cancelled"
        assert "phase_component_unattributed" in controller.call_method("BuildFailureDiagnostic", args=("world_changed",)), "Unknown component guard must remain explicitly unknown"
        assert not bridge.call_method("RejectAction", args=("bridge.hire_role_eligibility",))
        rejected = controller.call_method("BuildFailureDiagnostic", args=("action_rejected",))
        for part in ("WorkerOptimizer stopped: action_rejected", f"phase={phase}", "bridge=bridge.hire_role_eligibility", *(f"{label}={value}" for label, value in counts.items())):
            assert part in rejected, (part, rejected)
        snapshot.call_method("RecordValidationFailure", args=("building.id", 0, "700", "702"))
        rejected = controller.call_method("BuildFailureDiagnostic", args=("action_rejected",))
        assert "guard=building.id" in rejected and "captured=700" in rejected and "live=702" in rejected, "Action rejection must retain snapshot evidence too"
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        assert snapshot.call_method("AddWorker", args=(worker, building))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        assert runner.call_method("StartApplication", args=(snapshot, bridge, [0], [0], [0], [True], 10.0))[-1]
        assert runner.call_method("AdvanceApplication", args=(10.0,))
        assert runner.call_method("RecordDispatch", args=(True, 10.0))
        timed_out = controller.call_method("BuildFailureDiagnostic", args=("action_timeout",))
        for part in ("WorkerOptimizer stopped: action_timeout", "pending=fire", "worker_id=701", "building_id=702", "slot=0", "waiting=true", "occupant=", "workplace=", "confirmed=0"):
            assert part in timed_out, (part, timed_out)
        assert not controller.get_editor_property("MeasurePerformance"), "Detailed performance capture stays default-off"
        unreal.log("WO_FAILURE_DIAGNOSTICS_TESTS_PASS: soft quality progression accepted, hard guards retained, first guard, scalar evidence, phase/counts, reset and single terminal emission boundary")
    finally:
        for actor in reversed(spawned): actors.destroy_actor(actor)

run()
