"""Verify grouped teacher rows retain individual opportunity costs and identity."""

import unreal


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    matrix = unreal.new_object(load("BP_ScoreMatrix"))
    layout = unreal.new_object(load("BP_ProblemLayout"))
    snapshot = unreal.new_object(load("BP_WorkforceSnapshot"))
    scorer = unreal.new_object(load("BP_JobScorer"))
    settings = unreal.new_object(load("BP_PrioritySettings"))
    scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    spawned = []
    put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

    def spawn(name):
        obj = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        return obj

    try:
        workers = [spawn("Prototype_Agent") for _ in range(3)]
        for i, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={9800+i},guild=None,traits=({"teacher" if i == 2 else ""}))')
            put(worker, "m_characteristics", ch)
        buildings, components = [], []
        for i, kind in enumerate(("School", "Industry")):
            building = spawn("GridActor")
            for name, value in (("ID", 9810+i), ("isPlayerOwned", True), ("Health", 100)):
                put(building, name, value)
            component = building.call_method("AddComponentByClass", args=(native(kind), False, unreal.Transform(), False))
            wf = component.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True)" + (",()" if kind == "School" else "") + "))")
            put(component, "m_workers", wf)
            buildings.append(building)
            components.append(component)

        def capture(pool):
            snapshot.call_method("ResetSnapshot")
            for building in buildings:
                assert snapshot.call_method("AddBuilding", args=(building,))
            snapshot.call_method("FinishBuildings")
            for worker in pool:
                assert snapshot.call_method("AddWorker", args=(worker, None))
            snapshot.call_method("AdvanceCapture")
            snapshot.call_method("AdvanceCapture")
            assert layout.call_method("BeginLayout", args=(snapshot,))
            for _ in range(100):
                if layout.get_editor_property("LayoutDone"):
                    break
                layout.call_method("AdvanceLayout")
            assert layout.get_editor_property("LayoutSucceeded")

        def begin(teacher=0):
            assert matrix.call_method("BeginMatrix", args=(layout, scorer, settings, settings, [teacher, -1]))[-1]

        def finish(cached=False, success=True):
            for _ in range(200):
                if matrix.get_editor_property("MatrixDone"):
                    break
                if matrix.get_editor_property("SetupActive"):
                    matrix.call_method("AdvanceMatrix")
                    assert matrix.get_editor_property("LastStepWork") <= matrix.get_editor_property("StepWorkLimit")
                elif matrix.get_editor_property("Stage") == 0:
                    assert matrix.call_method("RecordDefinition", args=("fixture", True))
                elif matrix.get_editor_property("AwaitingScore"):
                    worker = matrix.get_editor_property("EdgeColumn")
                    if matrix.get_editor_property("SchoolEdge"):
                        assert matrix.get_editor_property("EdgeTeacher") != matrix.get_editor_property("EdgeWorker")
                        value = 3.0 if matrix.get_editor_property("EdgeTeacher") == workers[2] else 1.0
                    else:
                        assert not cached, "Ordinary edges must reuse validated scores across teacher candidates"
                        value = 1000.0 if worker == 0 else 10.0
                    assert matrix.call_method("RecordScore", args=(True, value))
                else:
                    matrix.call_method("PrepareEdge")
            assert matrix.get_editor_property("MatrixSucceeded") == success, matrix.get_editor_property("FailureCode")
            return list(matrix.get_editor_property("Scores"))

        capture(workers)
        begin()
        matrix.call_method("AdvanceMatrix")
        assert not matrix.call_method("UseTeacherGroups", args=([True, False],))[-1], "Configure groups before incremental setup starts"
        matrix.call_method("FailMatrix", args=("fixture_restart",))
        begin()
        assert not matrix.call_method("UseTeacherGroups", args=([True],))[-1]
        assert matrix.call_method("UseTeacherGroups", args=([True, True],))[-1]
        assert finish(success=False) == [], "Ordinary buildings cannot become grouped schools"
        begin()
        assert matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        assert not matrix.call_method("UseTeacherGroups", args=([False, False],))[-1], "Cannot replace active group semantics"
        scores = finish()
        assert scores == [0, 0, -1, 100, 100, 100, 1000, 10, 10], scores
        planner = unreal.new_object(load("BP_StaffingPlanner"))
        planner.call_method("StartPlan", args=(scores, [0, 0, 1], [True, True, True], [2, 2], 3, True))
        for _ in range(2000):
            if planner.get_editor_property("PlanDone"):
                break
            planner.call_method("AdvancePlan")
        assert planner.get_editor_property("PlanSucceeded")
        assert list(planner.get_editor_property("PlanAssignment")) == [1, 2, 0], "The representative is not forced into teaching; preserve production opportunity cost"
        assert not matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        begin(2)
        assert matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        assert not matrix.call_method("UseOrdinaryScores", args=(None, scores))[-1]
        assert not matrix.call_method("UseOrdinaryScores", args=(layout, scores[:-1]))[-1]
        invalid = list(scores)
        invalid[-1] = float("nan")
        assert matrix.call_method("UseOrdinaryScores", args=(layout, invalid))[-1]
        assert finish(cached=True, success=False) == [], "Invalid cached values fail incrementally before a plan can run"
        assert str(matrix.get_editor_property("FailureCode")) == "invalid_score"
        begin(2)
        assert matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        assert matrix.call_method("UseOrdinaryScores", args=(layout, scores))[-1]
        assert not matrix.call_method("UseOrdinaryScores", args=(layout, scores))[-1]
        assert finish(cached=True) == [-1, -1, 0, 300, 300, -1, 1000, 10, 10], "Only ordinary rows are cached; changed teachers must change school scores"
        assert not matrix.call_method("UseOrdinaryScores", args=(layout, scores))[-1]
        for i, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(education={"Master" if i < 2 else "Apprentice"},guild="different{i}")')
            put(worker, "m_characteristics", ch)
        wf = components[0].get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((educationRequirement=Master,bIsRequiredToRun=True),()))")
        put(components[0], "m_workers", wf)
        capture(workers)
        begin()
        assert matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        assert finish() == [0, 0, -1, -1, -1, 100, 1000, 10, 10], "Education-school groups must ignore guild while retaining completed-education exclusion"
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        put(components[0], "m_workers", wf)
        # Protected students retain the existing exact-identity mechanism.
        wf = components[0].get_editor_property("m_workers")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[1], "Agent", workers[2])
        put(wf, "m_workerSlots", slots)
        put(components[0], "m_workers", wf)
        capture(workers[:2])
        begin()
        assert matrix.call_method("UseTeacherGroups", args=([True, False],))[-1]
        assert finish(success=False) == [], "Protected students forbid group semantics after incremental validation"
        begin()
        assert matrix.call_method("UseTeacherGroups", args=([False, False],))[-1]
        finish()
        unreal.log("WO_GROUPED_MATRIX_TESTS_PASS: equivalent teacher rows, distinct representative/pupil, original worker opportunity costs, input/late guards and protected-student fallback")
    finally:
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
