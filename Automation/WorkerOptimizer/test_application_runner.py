"""Exercise the actual serial runner with explicit native-action observations."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    cls = unreal.load_class(None, root + "BP_ApplicationRunner.BP_ApplicationRunner_C")
    assert cls, "Production application runner does not exist"
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

        call = lambda name, *args: runner.call_method(name, args=args)
        prop = lambda name: runner.get_editor_property(name)
        capture(worker)
        assert not start([True], b=[])
        assert prop("Done") and not prop("Succeeded")
        assert not start([True], slots=[1])
        assert not start([True], workers=[-1])
        assert not start([True], snap=None)
        assert not start([True], transport=None)
        for bad in (float("nan"), float("inf"), -1.0):
            assert not start([True], now=bad)
        assert start([])
        assert prop("Done") and prop("Succeeded") and prop("AppliedCount") == 0
        assert start([True, False])
        assert not start([True]), "Cannot replace an active run"
        assert call("RecordDispatch", True, 10.0)
        assert prop("Waiting") and prop("QueuedCount") == 1 and prop("AppliedCount") == 0
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
        assert not call("ObserveAction", building, 13.0), "Completed observation is idempotent"
        call("AdvanceApplication", 13.0)
        assert prop("QueuedCount") == 2

        capture(worker)
        assert start([True, False])
        assert call("RecordDispatch", True, 10.0)
        assert not call("ObserveAction", building, 21.0)
        assert prop("Done") and not prop("Succeeded") and prop("Waiting")
        assert str(prop("FailureCode")) == "action_timeout"
        assert not start([True]), "An unconfirmed native action must block overlapping runs"
        occupy(None)
        assert call("ObserveAction", None, 22.0), "Late result may resolve uncertainty, never resume the stopped queue"
        assert not prop("Waiting") and prop("Done") and not prop("Succeeded")
        assert not prop("Active") and prop("AppliedCount") == 1
        call("AdvanceApplication", 23.0)
        assert prop("QueuedCount") == 1

        capture(worker)
        assert start([True])
        assert not call("RecordDispatch", False, 10.0)
        assert prop("Done") and not prop("Waiting") and prop("QueuedCount") == 0
        assert str(prop("FailureCode")) == "action_rejected"
        assert start([True])
        call("AdvanceApplication", 10.0)
        assert prop("Done") and not prop("Succeeded"), "Native definition stub must reject dispatch"
        assert prop("QueuedCount") == 0 and bridge.get_editor_property("QueuedActions") == 0
        capture(worker)
        assert start([True])
        assert call("RecordDispatch", True, 10.0)
        put(wf, "bDisabled", True)
        put(component, "m_workers", wf)
        assert not call("ObserveAction", building, 10.5)
        assert prop("Done") and not prop("Succeeded") and prop("Waiting")
        assert str(prop("FailureCode")) == "world_changed"
        assert component.get_editor_property("m_workers").get_editor_property("m_workerSlots")[0].get_editor_property("Agent") == worker
        unreal.log("WO_APPLICATION_RUNNER_TESTS_PASS: one pending action, confirmed counts, ordered progression, timeout/late result, pause, rejection, invalid inputs and no native actions executed")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
