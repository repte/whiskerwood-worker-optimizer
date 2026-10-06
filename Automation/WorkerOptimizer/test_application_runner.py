"""Exercise the actual serial runner with explicit native-action observations."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    cls = unreal.load_class(None, root + "BP_ApplicationRunner.BP_ApplicationRunner_C")
    assert cls, "Production application runner does not exist"
    bp = unreal.load_asset(root + "BP_ApplicationRunner")
    assert "ValidateQueue" in {str(g.get_name()) for g in BP.list_graphs(bp)}, "Application queue validation still runs synchronously during setup"
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")

    def spawn(cls):
        actor = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    try:
        runner = unreal.new_object(cls)
        snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
        bridge = spawn(load("BP_ActionBridge"))
        context = unreal.new_object(load("WBP_ActionContext"))
        assert bridge.call_method("InitializeBridge", args=(context,))
        worker = spawn(native("Prototype_Agent"))
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text("(ID=800)")
        put(worker, "m_characteristics", ch)
        building = spawn(native("GridActor"))
        put(building, "ID", 801)
        put(building, "isPlayerOwned", True)
        put(building, "Health", 100)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True)))")

        def occupy(person):
            slots = list(wf.get_editor_property("m_workerSlots"))
            put(slots[0], "Agent", person)
            put(wf, "m_workerSlots", slots)
            put(component, "m_workers", wf)

        def capture(person):
            occupy(person)
            snapshot.call_method("ResetSnapshot")
            assert snapshot.call_method("AddBuilding", args=(building,))
            snapshot.call_method("FinishBuildings")
            assert snapshot.call_method("AddWorker", args=(worker, building if person else None))
            snapshot.call_method("AdvanceCapture")
            snapshot.call_method("AdvanceCapture")

        def start(fires, b=None, slots=None, workers=None, now=10.0, snap=snapshot, transport=bridge):
            n = len(fires)
            result = runner.call_method("StartApplication", args=(snap, transport, [0] * n if b is None else b,
                [0] * n if slots is None else slots, [0] * n if workers is None else workers, fires, now))
            return result[-1]  # Non-const array inputs precede the actual return.

        def ready(now=10.0):
            for _ in range(20002):
                if not prop("ValidationActive"):
                    return
                call("AdvanceApplication", now)
                assert prop("LastStepWork") <= prop("StepWorkLimit")
                assert prop("QueuedCount") == 0 and not prop("Waiting")
            raise AssertionError("Queue validation exceeded its finite input bound")

        call = lambda name, *args: runner.call_method(name, args=args)
        prop = lambda name: runner.get_editor_property(name)
        capture(worker)
        assert not start([True], b=[])
        assert prop("Done") and not prop("Succeeded")
        for kwargs in ({"slots": [1]}, {"workers": [-1]}):
            assert start([True], **kwargs), "Structural setup accepts incremental value validation"
            ready()
            assert prop("Done") and not prop("Succeeded")
        put(runner, "StepWorkLimit", 3)
        assert start([True] * 20000, workers=[0] * 19999 + [-1])
        assert not call("RecordDispatch", True, 10.0), "Unvalidated queues cannot dispatch"
        assert bridge.get_editor_property("QueuedActions") == 0
        ready()
        assert prop("Done") and not prop("Succeeded") and prop("QueuedCount") == 0
        put(runner, "StepWorkLimit", 64)
        assert not start([True], snap=None)
        assert not start([True], transport=None)
        for bad in (float("nan"), float("inf"), -1.0):
            assert not start([True], now=bad)
        assert start([])
        assert prop("Done") and prop("Succeeded") and prop("AppliedCount") == 0
        assert start([True, False])
        assert not start([True]), "Cannot replace an active run"
        ready()
        assert call("RecordDispatch", True, 10.0)
        assert prop("Waiting") and prop("QueuedCount") == 1 and prop("AppliedCount") == 0
        assert not call("ResetConfirmedActions"), "Pending evidence cannot be discarded"
        assert prop("ConfirmedFires") == 0 and prop("ConfirmedHires") == 0
        assert not call("RecordDispatch", True, 10.0), "Repeated ticks cannot dispatch the same action twice"
        assert not call("ObserveAction", building, 10.5)
        assert prop("Waiting") and prop("ActionIndex") == 0
        occupy(None)
        assert call("ObserveAction", None, 11.0)
        assert not prop("Waiting") and prop("AppliedCount") == 1 and prop("ActionIndex") == 1
        assert not prop("Done")
        assert call("RecordDispatch", True, 11.0)
        assert not call("ObserveAction", None, 11.5)
        occupy(worker)
        assert call("ObserveAction", building, 12.0)
        assert prop("Done") and prop("Succeeded") and not prop("Active")
        assert prop("AppliedCount") == 2 and prop("QueuedCount") == 2
        assert prop("ConfirmedFires") == 1 and prop("ConfirmedHires") == 1
        assert not call("ObserveAction", building, 13.0), "Completed observation is idempotent"
        call("AdvanceApplication", 13.0)
        assert prop("QueuedCount") == 2

        capture(worker)
        assert start([True, False])
        ready()
        assert call("RecordDispatch", True, 10.0)
        assert not call("ObserveAction", building, 21.0)
        assert prop("Done") and not prop("Succeeded") and prop("Waiting")
        assert str(prop("FailureCode")) == "action_timeout"
        assert not start([True]), "An unconfirmed native action must block overlapping runs"
        occupy(None)
        assert call("ObserveAction", None, 22.0), "Late result may resolve uncertainty, never resume the stopped queue"
        assert not prop("Waiting") and prop("Done") and not prop("Succeeded")
        assert not prop("Active") and prop("AppliedCount") == 1
        assert prop("ConfirmedFires") == 1 and prop("ConfirmedHires") == 0
        call("AdvanceApplication", 23.0)
        assert prop("QueuedCount") == 1

        capture(worker)
        assert start([True])
        ready()
        assert not call("RecordDispatch", False, 10.0)
        assert prop("Done") and not prop("Waiting") and prop("QueuedCount") == 0
        assert str(prop("FailureCode")) == "action_rejected"
        assert start([True])
        ready()
        call("AdvanceApplication", 10.0)
        assert prop("Done") and not prop("Succeeded"), "Native definition stub must reject dispatch"
        assert prop("QueuedCount") == 0 and bridge.get_editor_property("QueuedActions") == 0
        capture(worker)
        assert start([True])
        ready()
        assert call("RecordDispatch", True, 10.0)
        put(wf, "bDisabled", True)
        put(component, "m_workers", wf)
        assert not call("ObserveAction", building, 10.5)
        assert prop("Done") and not prop("Succeeded") and prop("Waiting")
        assert str(prop("FailureCode")) == "world_changed"
        assert component.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == worker
        occupy(None)
        assert call("ObserveAction", None, 11.0), "Exact fire receipt must settle despite changed disabled state"
        assert not prop("Waiting") and prop("Done") and not prop("Succeeded") and not prop("Active")
        assert prop("ConfirmedFires") == 1 and prop("AppliedCount") == 1
        assert str(prop("FailureCode")) == "world_changed"
        assert not call("ObserveAction", None, 11.5), "Fallback confirmation counts once"
        call("AdvanceApplication", 12.0)
        assert prop("QueuedCount") == 1

        def pending(fire=True):
            nonlocal runner
            runner = unreal.new_object(cls)
            put(wf, "bDisabled", False)
            capture(worker if fire else None)
            assert start([fire, not fire])
            ready()
            assert call("RecordDispatch", True, 10.0)
            put(wf, "bDisabled", True)
            put(component, "m_workers", wf)

        pending(False)
        occupy(worker)
        assert not call("ObserveAction", None, 10.5), "Slot alone is not a hire receipt"
        assert prop("Waiting") and prop("AppliedCount") == 0
        assert call("ObserveAction", building, 11.0), "Exact hire receipt settles despite hard drift"
        assert not prop("Waiting") and prop("ConfirmedHires") == 1 and prop("ConfirmedFires") == 0
        assert prop("Done") and not prop("Succeeded") and not prop("Active")
        assert str(prop("FailureCode")) == "world_changed"
        call("AdvanceApplication", 12.0)
        assert prop("QueuedCount") == 1 and prop("ActionIndex") == 1
        assert snapshot.get_editor_property("Workforces")[0].get_editor_property("m_workerSlots")[0].get_editor_property("Agent") is None, "Fallback must not absorb changed world into old snapshot"

        pending()
        occupy(None)
        assert not call("ObserveAction", building, 11.0), "Slot alone is not a fire receipt"
        assert prop("Waiting") and prop("AppliedCount") == 0
        assert not call("ObserveAction", building, 25.0), "Deadline cannot release an unproven command"
        assert prop("Waiting") and not start([True])
        assert call("ObserveAction", None, 26.0)
        assert str(prop("FailureCode")) == "world_changed" and prop("ConfirmedFires") == 1

        pending()
        occupy(None)
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text("(ID=999)")
        put(worker, "m_characteristics", ch)
        assert not call("ObserveAction", None, 11.0), "Changed worker ID cannot confirm the original command"
        assert prop("Waiting") and prop("AppliedCount") == 0
        assert ch.import_text("(ID=800)")
        put(worker, "m_characteristics", ch)
        assert call("ObserveAction", None, 12.0)

        pending()
        ch = worker.get_editor_property("m_characteristics")
        previous_productivity = ch.get_editor_property("base_productivity")
        assert ch.import_text(f"(base_productivity={previous_productivity + 1})")
        put(worker, "m_characteristics", ch)
        occupy(None)
        assert call("ObserveAction", None, 11.0), "Changed worker characteristics cannot hide an exact completed receipt"
        assert str(prop("FailureCode")) == "world_changed" and prop("ConfirmedFires") == 1
        assert ch.import_text(f"(base_productivity={previous_productivity})")
        put(worker, "m_characteristics", ch)

        pending()
        put(wf, "m_workerSlots", [])
        put(component, "m_workers", wf)
        assert not call("ObserveAction", None, 11.0), "Missing target slot leaves command unresolved"
        assert prop("Waiting") and prop("AppliedCount") == 0
        assert not call("ObserveAction", None, 25.0)
        assert prop("Waiting") and prop("QueuedCount") == 1
        assert wf.import_text("(bDisabled=True,m_workerSlots=((bIsRequiredToRun=True)))")
        put(component, "m_workers", wf)
        assert call("ObserveAction", None, 26.0)

        pending(False)
        other = spawn(native("Prototype_Agent"))
        other_ch = other.get_editor_property("m_characteristics")
        assert other_ch.import_text("(ID=800)")
        put(other, "m_characteristics", other_ch)
        occupy(other)
        assert not call("ObserveAction", building, 11.0), "Same-ID other occupant cannot acknowledge the pending worker"
        assert prop("Waiting") and prop("AppliedCount") == 0
        occupy(worker)
        assert call("ObserveAction", building, 12.0)

        pending(False)
        occupy(worker)
        other_building = spawn(native("GridActor"))
        put(other_building, "ID", 801)
        assert not call("ObserveAction", other_building, 11.0), "Same-ID wrong reported workplace cannot acknowledge the original target"
        assert prop("Waiting") and prop("AppliedCount") == 0
        assert call("ObserveAction", building, 12.0)

        put(wf, "bDisabled", False)
        capture(worker)
        runner = unreal.new_object(cls)
        assert start([True, False])
        ready()
        assert call("RecordDispatch", True, 10.0)
        assert not call("ObserveAction", building, 21.0)
        assert str(prop("FailureCode")) == "action_timeout" and prop("Waiting")
        put(wf, "bDisabled", True)
        occupy(None)
        assert call("ObserveAction", None, 22.0), "Late drift receipt settles but does not convert timeout into success or retry"
        assert str(prop("FailureCode")) == "action_timeout"
        assert not prop("Waiting") and not prop("Active") and not prop("Succeeded")
        assert prop("ConfirmedFires") == 1 and prop("QueuedCount") == 1

        runner = unreal.new_object(cls)
        assert wf.import_text("(bDisabled=False,m_workerSlots=((educationRequirement=Master,bIsRequiredToRun=True)))")
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text("(education=None)")
        put(worker, "m_characteristics", ch)
        capture(None)
        assert start([False, True])
        ready()
        assert call("RecordDispatch", True, 10.0)
        occupy(worker)
        assert call("PendingStateSafe", building), "Fixture must leave the structural pending guard satisfied"
        assert not snapshot.call_method("ConfirmAction", args=(0, 0, 0, False, building)), "Strict role confirmation must reject the fixture"
        assert call("ObserveAction", building, 11.0), "Exact receipt must settle when strict role confirmation alone rejects"
        assert prop("Done") and not prop("Succeeded") and not prop("Active") and not prop("Waiting")
        assert str(prop("FailureCode")) == "world_changed"
        assert prop("ConfirmedHires") == 1 and prop("AppliedCount") == 1 and prop("QueuedCount") == 1
        call("AdvanceApplication", 12.0)
        assert prop("QueuedCount") == 1
        unreal.log("WO_APPLICATION_RUNNER_TESTS_PASS: exact drift receipts, unresolved lock, once-only counts, stopped remainder, timeout/late result, pause, rejection, invalid inputs and no native actions executed")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
