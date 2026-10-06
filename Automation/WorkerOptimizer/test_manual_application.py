"""Regress the compiled move order and finite native-action lifecycle."""
import unreal


def put(obj, key, value):
    obj.set_editor_property(key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


root = "/Game/Mods/WorkerOptimizer/"
load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
spawned = []
failures = []


def spawn(cls):
    actor = actors.spawn_actor_from_class(cls, unreal.Vector(0, 0, -100000))
    spawned.append(actor)
    return actor


def fixture(occupants, required):
    workers = [spawn(native("Prototype_Agent")) for _ in range(4)]
    for i, worker in enumerate(workers):
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text(f"(ID={9100 + i})")
        put(worker, "m_characteristics", ch)
    buildings = []
    workplaces = [None] * len(workers)
    for index, rows in enumerate(occupants):
        building = spawn(native("GridActor"))
        put(building, "ID", 9200 + index)
        put(building, "isPlayerOwned", True)
        put(building, "Health", 100)
        component = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=(" + ",".join("()" for _ in rows) + "))")
        slots = list(wf.get_editor_property("m_workerSlots"))
        for j, worker_index in enumerate(rows):
            put(slots[j], "bIsRequiredToRun", required[index][j])
            if worker_index >= 0:
                put(slots[j], "Agent", workers[worker_index])
                workplaces[worker_index] = building
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)
        buildings.append(building)
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    snapshot.call_method("ResetSnapshot")
    for building in buildings:
        assert snapshot.call_method("AddBuilding", args=(building,))
    snapshot.call_method("FinishBuildings")
    for worker, place in zip(workers, workplaces):
        assert snapshot.call_method("AddWorker", args=(worker, place))
    snapshot.call_method("AdvanceCapture")
    snapshot.call_method("AdvanceCapture")
    return snapshot, workers, buildings


def queue(snapshot, targets):
    plan = unreal.new_object(load("BP_ActionPlan"))
    assert plan.call_method("BeginBuild", args=(snapshot, targets))[-1]
    for _ in range(1000):
        if plan.get_editor_property("BuildDone"):
            break
        assert plan.call_method("AdvanceBuild")
    assert plan.get_editor_property("BuildSucceeded"), plan.get_editor_property("FailureCode")
    return list(zip(*(list(plan.get_editor_property(name)) for name in
                     ("ActionBuildings", "ActionSlots", "ActionWorkers", "ActionFire"))))


def dependency_moves():
    snapshot, _, _ = fixture([[0], [1], [2]], [[True], [True], [True]])
    actions = queue(snapshot, [1, 0, 3])
    assert actions[:3] == [(0, 0, 0, True), (1, 0, 1, True), (0, 0, 1, False)], actions
    assert actions[3:] == [(1, 0, 0, False), (2, 0, 2, True), (2, 0, 3, False)], actions


def flexible_minimum_first():
    snapshot, _, _ = fixture([[-1, -1], [-1, -1]], [[False, False], [False, False]])
    actions = queue(snapshot, [0, 1, 2, 3])
    assert actions == [(0, 0, 0, False), (1, 0, 2, False), (0, 1, 1, False), (1, 1, 3, False)], actions


def occupied_flexible_minimum():
    snapshot, _, _ = fixture([[-1, 0], [-1]], [[False, False], [False]])
    actions = queue(snapshot, [1, 0, 2])
    assert actions == [(1, 0, 2, False), (0, 0, 1, False)], actions


def required_fire_dependencies():
    snapshot, _, _ = fixture([[0, 1], [2]], [[True, False], [True]])
    actions = queue(snapshot, [3, 1, 2])
    assert actions == [(0, 1, 1, True), (0, 0, 0, True), (0, 0, 3, False), (0, 1, 1, False)], actions


def finite_terminal_state():
    snapshot, _, _ = fixture([[-1]], [[True]])
    bridge = spawn(load("BP_ActionBridge"))
    assert bridge.call_method("InitializeBridge", args=(unreal.new_object(load("WBP_ActionContext")),))
    runner = unreal.new_object(load("BP_ApplicationRunner"))

    def start():
        assert runner.call_method("StartApplication", args=(snapshot, bridge, [0], [0], [0], [False], 10.0))[-1]
        while runner.get_editor_property("ValidationActive"):
            assert runner.call_method("ValidateQueue")

    start()
    # The shipping boundary is synchronous. This deliberately missing effect is
    # failure evidence, never a command that can remain queued after it returned.
    assert runner.call_method("RecordDispatch", args=(True, 10.0))
    assert not runner.call_method("ObserveAction", args=(None, 21.0))
    assert runner.get_editor_property("Done") and not runner.get_editor_property("Succeeded")
    assert not runner.get_editor_property("Waiting"), "Terminal failure must not leave the icon locked"
    start()
    assert not runner.call_method("RecordDispatch", args=(False, 10.0))
    assert not runner.get_editor_property("Waiting")
    start()
    assert runner.call_method("RecordDispatch", args=(True, 10.0))
    snapshot.call_method("ResetSnapshot")
    assert not runner.call_method("AdvanceApplication", args=(11.0,))
    assert not runner.get_editor_property("Waiting"), "Destroyed observation data cannot retain a stale lock"


try:
    for test in (dependency_moves, flexible_minimum_first, occupied_flexible_minimum, required_fire_dependencies, finite_terminal_state):
        try:
            test()
        except Exception as error:
            failures.append((test.__name__, str(error)))
            unreal.log_warning("WO_MANUAL_APPLICATION_FAIL " + str(failures[-1]))
    assert not failures, failures
    unreal.log("WO_MANUAL_APPLICATION_TESTS_PASS")
finally:
    for actor in reversed(spawned):
        actors.destroy_actor(actor)
