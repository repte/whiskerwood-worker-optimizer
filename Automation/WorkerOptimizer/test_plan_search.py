"""Compare actual global teacher search with an independent exhaustive assignment oracle."""

import itertools
import time
import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    cls = load("BP_PlanSearch")
    assert cls, "Production global teacher-plan search does not exist"
    search = unreal.new_object(cls)
    matrix = unreal.new_object(load("BP_ScoreMatrix"))
    planner = unreal.new_object(load("BP_StaffingPlanner"))
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

    def capture(buildings, workers):
        snapshot.call_method("ResetSnapshot")
        for building in buildings:
            assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        for worker in workers:
            assert snapshot.call_method("AddWorker", args=(worker, None))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        assert layout.call_method("BeginLayout", args=(snapshot,))
        for _ in range(1000):
            if layout.get_editor_property("LayoutDone"):
                break
            layout.call_method("AdvanceLayout")
        assert layout.get_editor_property("LayoutSucceeded")

    def begin():
        return search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))

    def native_observations(strict):
        # Native definitions, saved options and productivity functions are editor
        # stubs. Only these boundaries are supplied; actual search and planning run.
        if matrix.get_editor_property("SetupActive"):
            matrix.call_method("AdvanceMatrix")
        elif matrix.get_editor_property("Stage") == 0:
            if matrix.get_editor_property("BuildingIndex") == 0 and search.get_editor_property("CandidatesEvaluated") > 0:
                assert matrix.get_editor_property("PolicyImported"), "Subsequent candidates must use the captured policy"
                assert list(matrix.get_editor_property("PolicyValues")) == list(search.get_editor_property("Priorities"))
            assert matrix.call_method("RecordDefinition", args=("fixture", True))
        elif matrix.get_editor_property("AwaitingScore"):
            column = matrix.get_editor_property("EdgeColumn")
            if matrix.get_editor_property("SchoolEdge"):
                teacher = list(layout.get_editor_property("ColumnActors")).index(matrix.get_editor_property("EdgeTeacher"))
                value = (3.0 if teacher == 1 else 1.0) * (2.0 if column == 2 else 1.0)
            else:
                value = 10000.0 if column == 1 else 1000.0 if column == 0 else 10.0
            assert matrix.call_method("RecordScore", args=(True, value))
        else:
            if matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("PolicyImported"):
                priorities = [4, 4, 0] if len(snapshot.get_editor_property("Buildings")) == 3 else [2] * len(snapshot.get_editor_property("Buildings"))
                assert matrix.call_method("UsePolicy", args=(priorities, strict))[-1]
            matrix.call_method("PrepareEdge")

    def finish(strict=True):
        for _ in range(100000):
            if search.get_editor_property("SearchDone"):
                break
            if search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                native_observations(strict)
            else:
                search.call_method("AdvanceSearch")
        assert search.get_editor_property("SearchDone"), "Search did not terminate"
        assert search.get_editor_property("SearchSucceeded"), search.get_editor_property("FailureCode")
        return list(search.get_editor_property("BestAssignment"))

    def key(assignment, strict):
        learning = sum((3 if assignment[r] == 1 else 1) * (2 if assignment[r + 1] == 2 else 1) * 100 for r in (0, 2))
        production = 10000 if assignment[4] == 1 else 1000 if assignment[4] == 0 else 10
        return (learning, production) if strict else 5 * learning + production

    try:
        workers = [spawn("Prototype_Agent") for _ in range(5)]
        for index, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={3100 + index},guild="guild{index}")')
            put(worker, "m_characteristics", ch)
        buildings, components = [], []
        for index, kind in enumerate(("School", "School", "Industry")):
            building = spawn("GridActor")
            for name, value in (("ID", 3200 + index), ("isPlayerOwned", True), ("Health", 100)):
                put(building, name, value)
            component = building.call_method("AddComponentByClass", args=(native(kind), False, unreal.Transform(), False))
            wf = component.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True)" + (",()" if kind == "School" else "") + "))")
            put(component, "m_workers", wf)
            buildings.append(building)
            components.append(component)
        capture(buildings, workers)
        before = [c.get_editor_property("m_workers").export_text() for c in components]
        for strict in (True, False):
            started = time.perf_counter()
            assert begin()
            assert not begin(), "Active searches cannot be restarted"
            result = finish(strict)
            assert len(result) == 5 and sorted(result) == list(range(5)), result
            expected = max(key(p, strict) for p in itertools.permutations(range(5)))
            assert key(result, strict) == expected, (strict, result, expected)
            assert search.get_editor_property("CandidatesEvaluated") > 1
            unreal.log(f"WO_PLAN_SEARCH_TIMING: strict={strict}, candidates={search.get_editor_property('CandidatesEvaluated')}, seconds={time.perf_counter() - started:.3f}; five-worker editor fixture only")
            assert before == [c.get_editor_property("m_workers").export_text() for c in components]
        capture(buildings, workers[:3])
        for strict in (True, False):
            assert begin()
            scarce = finish(strict)
            assert all(worker >= 0 for worker in scarce[:2]) and scarce[2:4] == [-1, -1] and scarce[4] >= 0, scarce
            assert len({worker for worker in scarce if worker >= 0}) == 3
        from editor_toolset.toolsets.blueprint import BlueprintTools as BP
        assert "ConfigureReserve" in {str(g.get_name()) for g in BP.list_graphs(unreal.load_asset(root + "BP_PlanSearch"))}, "School search does not enforce the builder reserve"
        for strict in (True, False):
            assert begin()
            assert search.call_method("ConfigureReserve", args=(2, [1., 2., 3.]))[-1]
            reserved = finish(strict)
            assert len({worker for worker in reserved if worker >= 0}) == 1, reserved
            assert reserved[:4] == [-1] * 4 and reserved[4] >= 0, ("A school needs teacher and student; with one worker left, cover industry", reserved)
        for locked_slot in (0, 1):
            wf = components[0].get_editor_property("m_workers")
            slots = list(wf.get_editor_property("m_workerSlots"))
            put(slots[locked_slot], "Agent", workers[4])
            put(wf, "m_workerSlots", slots)
            put(components[0], "m_workers", wf)
            capture(buildings, workers[:4])
            for strict in (True, False):
                assert begin()
                fixed_result = finish(strict)
                assert fixed_result[locked_slot] == 4 and sorted(fixed_result) == list(range(5)), fixed_result
                assert components[0].get_editor_property("m_workers").get_editor_property("m_workerSlots")[locked_slot].get_editor_property("Agent") == workers[4]
            put(slots[locked_slot], "Agent", None)
            put(wf, "m_workerSlots", slots)
            put(components[0], "m_workers", wf)
        capture(buildings, workers)
        assert begin()
        for _ in range(100):
            search.call_method("AdvanceSearch")
            if search.get_editor_property("State") == 2:
                break
        assert search.call_method("CancelSearch")
        assert search.get_editor_property("SearchDone") and not search.get_editor_property("SearchSucceeded")
        assert not list(search.get_editor_property("BestAssignment"))
        assert not matrix.get_editor_property("MatrixActive")
        # A native data failure is not a rejected candidate to skip silently.
        assert begin()
        for _ in range(100):
            search.call_method("AdvanceSearch")
            if search.get_editor_property("SearchDone"):
                break
        assert search.get_editor_property("SearchDone") and not search.get_editor_property("SearchSucceeded")
        assert str(search.get_editor_property("FailureCode")) == "definition_unavailable"
        assert begin()
        changed_policy = False
        for _ in range(10000):
            if search.get_editor_property("SearchDone"):
                break
            if search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                if (not changed_policy and search.get_editor_property("CandidatesEvaluated") > 0
                        and not matrix.get_editor_property("SetupActive") and matrix.get_editor_property("Stage") == 1
                        and matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("AwaitingScore")):
                    assert matrix.call_method("UsePolicy", args=(list(search.get_editor_property("Priorities")), False))[-1]
                    changed_policy = True
                native_observations(search.get_editor_property("CandidatesEvaluated") == 0)
            else:
                search.call_method("AdvanceSearch")
        assert changed_policy and search.get_editor_property("SearchDone") and not search.get_editor_property("SearchSucceeded")
        assert str(search.get_editor_property("FailureCode")) == "settings_changed"
        assert not list(search.get_editor_property("BestAssignment"))
        capture([buildings[2]], workers)
        assert begin()
        assert finish() == [1]
        assert search.get_editor_property("CandidatesEvaluated") == 1
        capture([], [])
        assert begin()
        assert finish() == []
        unreal.log("WO_PLAN_SEARCH_TESTS_PASS: global two-school/production tradeoffs against 120-permutation oracle in both modes, duplicate-teacher pruning, read-only operation, cancellation/reuse, no-school and empty cases; explicit editor-native observations")
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
