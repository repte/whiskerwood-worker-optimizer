"""Preserve unchanged incumbents without weakening admission of new assignments."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    layout = unreal.new_object(load("BP_ProblemLayout"))
    matrix = unreal.new_object(load("BP_ScoreMatrix"))
    plan = unreal.new_object(load("BP_ActionPlan"))
    scorer = unreal.new_object(load("BP_JobScorer"))
    settings = unreal.new_object(load("BP_PrioritySettings"))
    assert scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    spawned = []
    failures = []

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def building(number, kind, occupants):
        actor = spawn("GridActor")
        for key, value in (("ID", number), ("isPlayerOwned", True), ("Health", 100)):
            put(actor, key, value)
        component = actor.call_method("AddComponentByClass", args=(native(kind), False, unreal.Transform(), False))
        workforce = component.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=((bIsRequiredToRun=True,educationRequirement=Educated),()))")
        slots = list(workforce.get_editor_property("m_workerSlots"))
        for slot, occupant in zip(slots, occupants):
            put(slot, "Agent", occupant)
        put(workforce, "m_workerSlots", slots)
        put(component, "m_workers", workforce)
        return actor, component

    def capture(actor, workers, places):
        snapshot.call_method("ResetSnapshot")
        assert snapshot.call_method("AddBuilding", args=(actor,))
        snapshot.call_method("FinishBuildings")
        for worker, place in zip(workers, places):
            assert snapshot.call_method("AddWorker", args=(worker, place))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        assert layout.call_method("BeginLayout", args=(snapshot,))
        for _ in range(1000):
            if layout.get_editor_property("LayoutDone"):
                break
            layout.call_method("AdvanceLayout")
        assert layout.get_editor_property("LayoutSucceeded"), layout.get_editor_property("FailureCode")

    def build(targets):
        assert plan.call_method("BeginBuild", args=(snapshot, targets))[-1]
        for _ in range(1000):
            if plan.get_editor_property("BuildDone"):
                break
            plan.call_method("AdvanceBuild")
        assert plan.get_editor_property("BuildDone")
        return plan.get_editor_property("BuildSucceeded")

    try:
        workers = [spawn("Prototype_Agent") for _ in range(4)]
        protected = spawn("Prototype_Agent")
        for index, worker in enumerate(workers + [protected]):
            ch = worker.get_editor_property("m_characteristics")
            education = "Educated" if index in (1, 3) else "None"
            assert ch.import_text(f'(ID={6100 + index},education={education},guild="guild{index}")')
            put(worker, "m_characteristics", ch)

        school, sc = building(6200, "School", [workers[0], protected])
        capture(school, workers, [school, None, None, None])
        assert list(layout.get_editor_property("FixedSlots")) == [0, 4]
        assert not snapshot.call_method("CanFillSlot", args=(workers[0], school, 0, None)), "Fixture teacher must fail new-hire admission"
        before = sc.get_editor_property("m_workers").export_text()

        assert matrix.call_method("BeginMatrix", args=(layout, scorer, settings, settings, [0]))[-1]
        for _ in range(1000):
            if not matrix.get_editor_property("SetupActive"):
                break
            matrix.call_method("AdvanceMatrix")
        if not matrix.get_editor_property("MatrixActive"):
            failures.append("Pinned incumbent teacher rejected during matrix setup: " + str(matrix.get_editor_property("FailureCode")))
        else:
            assert matrix.call_method("RecordDefinition", args=("education", True))
            for _ in range(1000):
                if matrix.get_editor_property("MatrixDone"):
                    break
                if matrix.get_editor_property("AwaitingScore"):
                    assert matrix.call_method("RecordScore", args=(True, 1.0))
                else:
                    matrix.call_method("PrepareEdge")
            assert matrix.get_editor_property("MatrixSucceeded"), matrix.get_editor_property("FailureCode")
            assert list(matrix.get_editor_property("Scores")) == [0, -1, -1, -1, -1, -1, -1, -1, -1, 100]

        if not build([0, -2]):
            failures.append("Unchanged teacher rejected by action plan: " + str(plan.get_editor_property("FailureCode")))
        else:
            assert not list(plan.get_editor_property("ActionWorkers")), "Preservation must be a no-op"
        assert not build([2, -2])
        assert str(plan.get_editor_property("FailureCode")) == "ineligible_assignment", "A new teacher still needs native admission"
        assert before == sc.get_editor_property("m_workers").export_text()

        # A movable pupil must still qualify when its teacher changes.
        changing_school, cc = building(6201, "School", [workers[0], workers[3]])
        capture(changing_school, workers, [changing_school, None, None, changing_school])
        assert not build([1, 3]), "Keeping the pupil with a different teacher must recheck learning eligibility"
        assert str(plan.get_editor_property("FailureCode")) == "ineligible_assignment"

        ordinary, oc = building(6202, "Industry", [None, None])
        capture(ordinary, workers, [None] * len(workers))
        assert not build([2, -1]), "New ordinary hires still require native admission"
        assert str(plan.get_editor_property("FailureCode")) == "ineligible_assignment"
        assert build([1, -1]), plan.get_editor_property("FailureCode")
        assert list(plan.get_editor_property("ActionWorkers")) == [1]
        assert list(plan.get_editor_property("ActionFire")) == [False]

        # A required-worker change forces native optional-slot fires and rehires.
        collateral, co = building(6203, "Industry", [workers[1], workers[0]])
        workforce = co.get_editor_property("m_workers")
        slots = list(workforce.get_editor_property("m_workerSlots"))
        assert slots[1].import_text("(educationRequirement=Educated)")
        put(workforce, "m_workerSlots", slots)
        put(co, "m_workers", workforce)
        capture(collateral, workers, [collateral, collateral, None, None])
        assert not build([3, 0]), "An optional incumbent that must be rehired still needs native admission"
        assert str(plan.get_editor_property("FailureCode")) == "ineligible_assignment"
        assert not failures, "; ".join(failures)
        unreal.log("WO_PINNED_INCUMBENTS_TESTS_PASS")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
