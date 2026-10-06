"""Keep native required-slot fires from displacing protected optional workers."""

import unreal


def put(obj, key, value):
    obj.set_editor_property(key, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    layout = unreal.new_object(load("BP_ProblemLayout"))
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    spawned = []

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def building(number, component_name, occupants, required):
        assert component_name in ("Industry", "School"), "Keep this fixture within verified native writers"
        actor = spawn("GridActor")
        put(actor, "ID", number)
        put(actor, "isPlayerOwned", True)
        put(actor, "Health", 100)
        component = actor.call_method("AddComponentByClass", args=(native(component_name), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=(" + ",".join("()" for _ in occupants) + "))")
        slots = list(workforce.get_editor_property("m_workerSlots"))
        for index, person in enumerate(occupants):
            put(slots[index], "Agent", person)
            put(slots[index], "bIsRequiredToRun", required[index])
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        return actor, component

    try:
        workers = [spawn("Prototype_Agent") for _ in range(8)]
        protected = [spawn("Prototype_Agent") for _ in range(4)]
        for index, worker in enumerate(workers + protected):
            characteristics = worker.get_editor_property("m_characteristics")
            assert characteristics.import_text(f'(ID={5100 + index},guild="guild{index}")')
            put(worker, "m_characteristics", characteristics)

        industry, ic = building(5200, "Industry", [workers[0], workers[1], protected[0], None, workers[2]],
                                [True, True, False, True, False])
        school, sc = building(5201, "School", [workers[3], protected[1]], [True, False])
        required_only, rc = building(5202, "Industry", [protected[2], workers[4]], [True, True])
        empty_optional, ec = building(5203, "Industry", [workers[5], None], [True, False])
        optional_first, oc = building(5204, "Industry", [protected[3], workers[6]], [False, True])
        buildings = [industry, school, required_only, empty_optional, optional_first]
        components = [ic, sc, rc, ec, oc]
        workplaces = [industry, industry, industry, school, required_only, empty_optional, optional_first, None]
        before = [component.get_editor_property("m_workers").export_text() for component in components]

        snapshot.call_method("ResetSnapshot")
        for actor in buildings:
            assert snapshot.call_method("AddBuilding", args=(actor,))
        snapshot.call_method("FinishBuildings")
        for worker, workplace in zip(workers, workplaces):
            assert snapshot.call_method("AddWorker", args=(worker, workplace))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        assert layout.call_method("BeginLayout", args=(snapshot,))
        for _ in range(1000):
            if layout.get_editor_property("LayoutDone"):
                break
            layout.call_method("AdvanceLayout")
        assert layout.get_editor_property("LayoutDone")
        assert layout.get_editor_property("LayoutSucceeded"), layout.get_editor_property("FailureCode")

        fixed = list(layout.get_editor_property("FixedSlots"))
        assert fixed[:5] == [0, 1, 8, -1, -1], (
            "Protected optional workers require every occupied native-required incumbent to stay; "
            "empty required and movable optional slots must remain available", fixed)
        assert fixed[5:7] == [3, 9], "A protected student must also protect the required teacher"
        assert fixed[7:11] == [10, -1, -1, -1], "Protected required or empty optional slots do not pin unrelated workers"
        assert fixed[11:] == [11, 6], "Protection must not depend on required slots appearing first"
        assert list(layout.get_editor_property("RowBuildings")) == [0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
        assert list(layout.get_editor_property("RowSlots")) == [0, 1, 2, 3, 4, 0, 1, 0, 1, 0, 1, 0, 1]
        assert list(layout.get_editor_property("Incumbents")) == [0, 1, -2, -1, 2, 3, -2, -2, 4, 5, -1, -2, 6]
        assert list(layout.get_editor_property("Minimum")) == [True, True, False, True, False, True, False, True, True, True, False, False, True]
        assert list(layout.get_editor_property("ColumnWorkers")) == list(range(8)) + [-2] * 4
        assert list(layout.get_editor_property("ColumnActors")) == workers + protected
        assert list(snapshot.get_editor_property("Workers")) == workers, "Pinning must preserve the original worker pool and indices"
        assert list(snapshot.get_editor_property("WorkerWorkplaces")) == workplaces
        assert before == [component.get_editor_property("m_workers").export_text() for component in components], "Layout is read-only"
        unreal.log("WO_NATIVE_FIRE_DEPENDENCIES_TESTS_PASS")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
