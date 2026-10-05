"""Exercise the real matrix at explicit native definition/score observation boundaries."""

import math
import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_ScoreMatrix")
    assert cls, "Production runtime score matrix does not exist"
    matrix = unreal.new_object(cls)
    layout = unreal.new_object(load("BP_ProblemLayout"))
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    scorer = unreal.new_object(load("BP_JobScorer"))
    settings = unreal.new_object(load("BP_PrioritySettings"))
    assert scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    def building(number, kind, occupants):
        actor = spawn("GridActor")
        for key, value in (("ID", number), ("isPlayerOwned", True), ("Health", 100)):
            put(actor, key, value)
        component = actor.call_method("AddComponentByClass", args=(native(kind), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        slots = list(wf.get_editor_property("m_workerSlots"))
        for slot, occupant in zip(slots, occupants):
            put(slot, "Agent", occupant)
        put(wf, "m_workerSlots", slots)
        put(component, "m_workers", wf)
        return actor, component

    def capture(buildings, workers, places):
        snapshot.call_method("ResetSnapshot")
        for actor in buildings:
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
        assert layout.get_editor_property("LayoutSucceeded")

    def begin(teachers):
        return matrix.call_method("BeginMatrix", args=(layout, scorer, settings, settings, teachers))[-1]

    def define(categories):
        for category in categories:
            assert matrix.call_method("RecordDefinition", args=(category, True))

    def finish(success=True):
        for _ in range(1000):
            if matrix.get_editor_property("MatrixDone"):
                break
            if matrix.get_editor_property("AwaitingScore"):
                column = matrix.get_editor_property("EdgeColumn")
                score = (2.0 if column == 1 else 1.0) if matrix.get_editor_property("SchoolEdge") else 100.0 + column
                assert matrix.call_method("RecordScore", args=(True, score))
            else:
                matrix.call_method("PrepareEdge")
        assert matrix.get_editor_property("MatrixDone")
        assert matrix.get_editor_property("MatrixSucceeded") == success, matrix.get_editor_property("FailureCode")
        return list(matrix.get_editor_property("Scores"))

    try:
        workers = [spawn("Prototype_Agent") for _ in range(4)]
        for index, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={2100 + index},guild="guild{index}")')
            put(worker, "m_characteristics", ch)
        industry, ic = building(2200, "Industry", [None, workers[3]])
        school, sc = building(2201, "School", [None, None])
        capture([industry, school], workers[:3], [None] * 3)
        before = [c.get_editor_property("m_workers").export_text() for c in (ic, sc)]
        assert begin([-1, 0])
        assert not begin([-1, 2]), "An active matrix cannot be restarted"
        define(["future.production", "future.education"])
        scores = finish()
        assert scores == [100, 101, 102, -1, -1, -1, -1, 0,
                          0, -1, -1, -1, -1, 200, 100, -1], scores
        assert list(matrix.get_editor_property("Priorities")) == [2, 2]
        assert list(matrix.get_editor_property("Minimum")) == [True, False, True, True]
        assert list(layout.get_editor_property("Minimum")) == [True, False, True, False], "Matrix constraints must not mutate the layout"
        assert matrix.get_editor_property("Strict")
        planner = unreal.new_object(load("BP_StaffingPlanner"))
        planner.call_method("StartPlan", args=(scores, list(layout.get_editor_property("RowBuildings")),
            list(matrix.get_editor_property("Minimum")), list(matrix.get_editor_property("Priorities")), 4, True))
        assert planner.call_method("RequireFixedSlots", args=(list(matrix.get_editor_property("FixedSlots")),))[-1]
        for _ in range(1000):
            if planner.get_editor_property("PlanDone"):
                break
            planner.call_method("AdvancePlan")
        assert planner.get_editor_property("PlanSucceeded")
        assert list(planner.get_editor_property("PlanAssignment")) == [2, 3, 0, 1]
        targets = [layout.get_editor_property("ColumnWorkers")[column] if column >= 0 else -1
                   for column in planner.get_editor_property("PlanAssignment")]
        actions = unreal.new_object(load("BP_ActionPlan"))
        assert actions.call_method("BeginBuild", args=(snapshot, targets))[-1]
        for _ in range(1000):
            if actions.get_editor_property("BuildDone"):
                break
            actions.call_method("AdvanceBuild")
        assert actions.get_editor_property("BuildSucceeded")
        assert list(actions.get_editor_property("ActionWorkers")) == [2, 0, 1]
        assert list(actions.get_editor_property("ActionFire")) == [False, False, False]
        assert before == [c.get_editor_property("m_workers").export_text() for c in (ic, sc)]
        assert not matrix.call_method("RecordScore", args=(True, 10.0)), "No unsolicited scores"
        assert not matrix.call_method("RecordDefinition", args=("late", True))

        # A different hypothetical teacher changes edges, not the live school.
        assert begin([-1, 2])
        define(["production", "education"])
        changed = finish()
        assert changed[8:12] == [-1, -1, 0, -1]
        assert changed[12:16] == [100, 200, -1, -1]
        assert begin([-1, -1])
        define(["production", "education"])
        assert finish()[8:] == [-1] * 8
        for bad in ([-1], [-1, 4], [-1, -2], [-1, 3]):
            assert not begin(bad), bad
        assert begin([-1, 0])
        assert not matrix.call_method("RecordDefinition", args=("production", False))
        assert str(matrix.get_editor_property("FailureCode")) == "definition_unavailable"
        for bad in (math.nan, math.inf, -1.0, 1000001.0):
            assert begin([-1, 0])
            define(["production", "education"])
            assert matrix.call_method("PrepareEdge")
            assert matrix.get_editor_property("AwaitingScore")
            assert not matrix.call_method("RecordScore", args=(True, bad))
            assert not matrix.get_editor_property("MatrixSucceeded")
            assert not list(matrix.get_editor_property("Scores"))
        # Real editor-native definition stubs report failure; never invent a score.
        assert begin([-1, 0])
        matrix.call_method("AdvanceMatrix")
        assert matrix.get_editor_property("MatrixDone") and not matrix.get_editor_property("MatrixSucceeded")

        assert begin([-1, 0])
        for bad in ([2], [-1, 2], [5, 2]):
            assert not matrix.call_method("UsePolicy", args=(bad, False))[-1]
        assert matrix.call_method("UsePolicy", args=([4, 0], False))[-1]
        assert matrix.call_method("RecordDefinition", args=("production", True))
        assert not matrix.call_method("UsePolicy", args=([0, 4], True))[-1], "Do not replace policy halfway through definition capture"
        assert matrix.call_method("RecordDefinition", args=("education", True))
        assert list(matrix.get_editor_property("Priorities")) == [4, 0]
        assert not matrix.get_editor_property("Strict")
        assert matrix.call_method("PrepareEdge")
        assert not matrix.call_method("UsePolicy", args=([0, 4], True))[-1], "Do not change policy while a score is pending"
        finish()

        fixed_school, _ = building(2202, "School", [workers[3], None])
        capture([fixed_school], workers[:3], [None] * 3)
        assert begin([3])
        define(["education"])
        assert finish() == [-1, -1, -1, 0, 100, 200, 100, -1]
        assert not begin([0]), "A protected teacher cannot be replaced"
        fixed_student, _ = building(2203, "School", [workers[0], workers[3]])
        capture([fixed_student], workers[:3], [fixed_student, None, None])
        assert begin([1])
        define(["education"])
        assert finish() == [-1, 0, -1, -1, -1, -1, -1, 100]
        assert list(matrix.get_editor_property("FixedSlots")) == [1, 3], "A protected student requires its selected teacher to remain assigned"
        assert list(layout.get_editor_property("FixedSlots")) == [-1, 3]
        # A higher-priority production row cannot steal this teacher afterward.
        planner.call_method("StartPlan", args=(list(matrix.get_editor_property("Scores")) + [-1.0, 999.0, -1.0, -1.0],
            [0, 0, 1], [True, True, True], [0, 4], 4, True))
        assert planner.call_method("RequireFixedSlots", args=(list(matrix.get_editor_property("FixedSlots")) + [-1],))[-1]
        for _ in range(1000):
            if planner.get_editor_property("PlanDone"):
                break
            planner.call_method("AdvancePlan")
        assert planner.get_editor_property("PlanSucceeded")
        assert list(planner.get_editor_property("PlanAssignment")) == [1, 3, -1]
        changed_ch = workers[1].get_editor_property("m_characteristics")
        assert changed_ch.import_text('(guild="guild3")')
        put(workers[1], "m_characteristics", changed_ch)
        capture([fixed_student], workers[:3], [fixed_student, None, None])
        assert begin([1])
        define(["education"])
        assert finish(False) == []
        assert str(matrix.get_editor_property("FailureCode")) == "incompatible_fixed_student"
        capture([], [], [])
        assert begin([])
        matrix.call_method("PrepareEdge")
        assert matrix.get_editor_property("MatrixSucceeded")
        unreal.log("WO_SCORE_MATRIX_TESTS_PASS: runtime layout/eligibility/priority/scorer wiring, hypothetical teachers, fixed columns, school minimum crews, planner integration, invalid observations/reuse and read-only behavior; native definition/score success is an explicit editor observation boundary")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
