"""Exact grouped teacher search: brute-force correctness and candidate reduction."""

import itertools
import time
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    search, matrix, planner, layout, snapshot, scorer, settings = [unreal.new_object(load(name)) for name in
        ("BP_PlanSearch", "BP_ScoreMatrix", "BP_StaffingPlanner", "BP_ProblemLayout", "BP_WorkforceSnapshot", "BP_JobScorer", "BP_PrioritySettings")]
    assert scorer.call_method("Configure", args=(25.0, -10.0, 20.0, 15.0, 10.0))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    spawned = []

    def spawn(name):
        obj = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        return obj

    def fixture(worker_count, school_count):
        workers = [spawn("Prototype_Agent") for _ in range(worker_count)]
        for i, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            traits = '"teacher"' if i < 2 else '"inquisitive"' if i == 2 else ''
            assert ch.import_text(f'(ID={9900+i},guild=None,traits=({traits}))')
            put(worker, "m_characteristics", ch)
        buildings, components = [], []
        for i, kind in enumerate(["School"] * school_count + ["Industry"]):
            building = spawn("GridActor")
            for name, value in (("ID", 10100+i), ("isPlayerOwned", True), ("Health", 100)):
                put(building, name, value)
            component = building.call_method("AddComponentByClass", args=(native(kind), False, unreal.Transform(), False))
            wf = component.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True)" + (",()" if kind == "School" else "") + "))")
            put(component, "m_workers", wf)
            buildings.append(building)
            components.append(component)
        return workers, buildings, components

    def capture(workers, buildings):
        snapshot.call_method("ResetSnapshot")
        for building in buildings:
            assert snapshot.call_method("AddBuilding", args=(building,))
        snapshot.call_method("FinishBuildings")
        for worker in workers:
            assert snapshot.call_method("AddWorker", args=(worker, None))
        snapshot.call_method("AdvanceCapture")
        snapshot.call_method("AdvanceCapture")
        assert layout.call_method("BeginLayout", args=(snapshot,))
        for _ in range(2000):
            if layout.get_editor_property("LayoutDone"):
                break
            layout.call_method("AdvanceLayout")
        assert layout.get_editor_property("LayoutSucceeded")

    def production(column):
        return 10000 if column == 0 else 9000 if column == 1 else 100 + column

    def learning(teacher, pupil):
        return (3 if teacher < 2 else 1) * (2 if pupil == 2 else 1)

    def finish(workers, schools, strict):
        put(search, "StepWorkLimit", 1 if len(workers) <= 6 else 64)
        assert search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))
        assert not search.call_method("CoverageBelowBest"), "No bound before an incumbent exists"
        start = time.perf_counter()
        ordinary_observations = 0
        advances = 0
        states = set()
        saw_upper_gain = saw_upper_tie = False
        for _ in range(1000000):
            if search.get_editor_property("SearchDone"):
                break
            states.add(search.get_editor_property("State"))
            if search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                if matrix.get_editor_property("SetupActive"):
                    matrix.call_method("AdvanceMatrix")
                elif matrix.get_editor_property("Stage") == 0:
                    if matrix.get_editor_property("BuildingIndex") == 0 and search.get_editor_property("HasBest"):
                        priorities = list(search.get_editor_property("Priorities"))
                        order = sorted(range(len(priorities)), key=lambda b: (-priorities[b], b))
                        teachers = list(search.get_editor_property("Teachers"))
                        upper = tuple(b >= schools or teachers[b] >= 0 for b in order)
                        best = tuple(search.get_editor_property("BestCoverage")[b] for b in order)
                        assert upper >= best and not search.call_method("CoverageBelowBest")
                        saw_upper_gain |= upper > best
                        saw_upper_tie |= upper == best
                    assert matrix.call_method("RecordDefinition", args=("fixture", True))
                elif matrix.get_editor_property("AwaitingScore"):
                    column = matrix.get_editor_property("EdgeColumn")
                    if matrix.get_editor_property("SchoolEdge"):
                        teacher = workers.index(matrix.get_editor_property("EdgeTeacher"))
                        value = learning(teacher, column)
                    else:
                        ordinary_observations += 1
                        value = production(column)
                    assert matrix.call_method("RecordScore", args=(True, float(value)))
                else:
                    if matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("PolicyImported"):
                        assert matrix.call_method("UsePolicy", args=([4] * schools + [0], strict))[-1]
                    matrix.call_method("PrepareEdge")
            else:
                search.call_method("AdvanceSearch")
                advances += 1
                assert 0 <= search.get_editor_property("LastStepWork") <= search.get_editor_property("StepWorkLimit")
        assert search.get_editor_property("SearchDone"), "Grouped search did not terminate"
        assert search.get_editor_property("SearchSucceeded"), search.get_editor_property("FailureCode")
        assert {0, 1, 2, 3, 5, 6, 7, 9, 10, 13}.issubset(states), states
        assert ordinary_observations == len(snapshot.get_editor_property("Workers")), "Only the first successful candidate may call ordinary native scoring"
        result = list(search.get_editor_property("BestAssignment"))
        assert len(set(result)) == len(result) and -1 not in result, result
        assert list(search.get_editor_property("BestTeachers"))[:schools] == result[:2*schools:2], "Report actual teacher identities, not group representatives"
        if len(workers) == 40:
            assert saw_upper_gain and saw_upper_tie, "Exercise both potentially improving and equal-coverage branches"
        elapsed = time.perf_counter() - start
        rows = len(layout.get_editor_property("RowBuildings"))
        columns = len(layout.get_editor_property("ColumnActors"))
        protected = sum(w >= 0 for w in layout.get_editor_property("FixedSlots"))
        payload = 8 * sum(len(obj.get_editor_property(name)) for obj, name in (
            (matrix, "Scores"), (matrix, "CachedScores"), (search, "CachedScores"),
            (planner, "BaseScores"), (planner, "PassScores"), (planner, "Scores"),
            (planner, "ImplicitScores")))
        unreal.log(f"WO_GROUPED_SEARCH_TIMING rows={rows} workers={len(workers)} columns={columns} buildings={len(buildings)} schools={schools} protected_slots={protected} reserve=0 strict={strict} limit={search.get_editor_property('StepWorkLimit')} candidates={search.get_editor_property('CandidatesEvaluated')} search_calls={advances} finite_driver_bound=1000000 host_seconds={elapsed:.3f} selected_float_array_payload_bytes={payload}; editor observation fixture, not shipping frame data; payload excludes allocator/capacity/VM overhead")
        return result

    def key(assignment, schools, strict):
        school_value = sum(100 * learning(assignment[r], assignment[r+1]) for r in range(0, schools*2, 2))
        other = production(assignment[-1])
        return (school_value, other) if strict else 5 * school_value + other

    try:
        workers, buildings, components = fixture(6, 2)
        capture(workers, buildings)
        before = [component.get_editor_property("m_workers").export_text() for component in components]
        for strict in (True, False):
            result = finish(workers, 2, strict)
            optimum = max(key(p, 2, strict) for p in itertools.permutations(range(6), 5))
            assert key(result, 2, strict) == optimum, (strict, result, optimum)
            assert search.get_editor_property("CandidatesEvaluated") <= 9, "Two teaching profiles should not enumerate every individual teacher"
            assert before == [component.get_editor_property("m_workers").export_text() for component in components]
        # A fixed pupil keeps exact identity constraints for its school only.
        wf = components[0].get_editor_property("m_workers")
        slots = list(wf.get_editor_property("m_workerSlots"))
        put(slots[1], "Agent", workers[5])
        put(wf, "m_workerSlots", slots)
        put(components[0], "m_workers", wf)
        capture(workers[:5], buildings)
        for strict in (True, False):
            result = finish(workers, 2, strict)
            optimum = max(key(p, 2, strict) for p in itertools.permutations(range(6), 5) if p[1] == 5)
            assert result[1] == 5 and key(result, 2, strict) == optimum
            assert list(search.get_editor_property("TeacherGroups")) == [False, True, False]
        assert search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))
        for _ in range(100):
            if search.get_editor_property("State") == 1:
                break
            search.call_method("AdvanceSearch")
        assert search.get_editor_property("State") == 1
        assert search.call_method("AdvanceSelection"), "Select a nonempty profile in the last school"
        wf2 = components[1].get_editor_property("m_workers")
        put(wf2, "bDisabled", True)
        put(components[1], "m_workers", wf2)
        for _ in range(2000):
            if search.get_editor_property("SearchDone"):
                break
            search.call_method("AdvanceSearch")
        put(wf2, "bDisabled", False)
        put(components[1], "m_workers", wf2)
        assert search.get_editor_property("SearchDone") and not search.get_editor_property("SearchSucceeded")
        assert not matrix.get_editor_property("MatrixActive"), "Failure during profile setup must release the active matrix for retry"
        # More workers must not multiply equivalent teacher choices.
        workers, buildings, _ = fixture(40, 4)
        capture(workers, buildings)
        result = finish(workers, 4, True)
        assert key(result, 4, True) == (1100, 139), result
        assert search.get_editor_property("CandidatesEvaluated") <= 20, "Prune teacherless choices once their optimistic coverage loses"
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_GroupedCoverageInputs", unreal.Object.static_class())
        graph = BP.add_function_graph(fixture, "TeacherlessCandidate")
        BP.add_object_function_param(graph, "Search", load("BP_PlanSearch"), True)
        BP.compile_blueprint(fixture)
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, '''(fn TeacherlessCandidate (Search)
              (Utilities|Array|Clear (Class|BPPlanSearch|GetTeachers :self Search))
              (for b (range (Utilities|Array|Length (Class|BPPlanSearch|GetPriorities :self Search)))
                (Utilities|Array|Add (Class|BPPlanSearch|GetTeachers :self Search) -1))
              (Class|BPPlanSearch|SetCompareTier :self Search :CompareTier 4)
              (Class|BPPlanSearch|SetCompareIndex :self Search :CompareIndex 0)
              (Class|BPPlanSearch|SetCoverageReady :self Search :CoverageReady false))''')
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        unreal.new_object(fixture.generated_class()).call_method("TeacherlessCandidate", args=(search,))
        below = False
        for _ in range(5 * (len(buildings) + 1) + 1):
            below = search.call_method("CoverageBelowBest")
            if search.get_editor_property("CoverageReady"):
                break
        assert search.get_editor_property("CoverageReady") and below, "The final teacherless branch cannot beat full coverage"
        unreal.log("WO_GROUPED_SEARCH_TESTS_PASS: 720-permutation optimum in both modes, profile reuse with distinct workers, production opportunity costs, protected-pupil exact fallback and 40-worker/four-school candidate bound")
    finally:
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
