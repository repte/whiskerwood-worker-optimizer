"""Exhaustive physical-slot oracles for compiled flexible minimum crews."""
import itertools
import math
import random
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT = "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner"
synthetic_face_seen = False


def key(result, scores, buildings, minimum, priorities, flexible, strict, reserve, quality, movable):
    covered = []
    for b in sorted(range(len(priorities)), key=lambda b: (-priorities[b], b)):
        rows = [r for r, owner in enumerate(buildings) if owner == b]
        covered.append(any(result[r] >= 0 for r in rows) if flexible[b]
                       else all(result[r] >= 0 for r in rows if minimum[r]))
    counts = tuple((sum(w >= 0 and priorities[buildings[r]] == tier for r, w in enumerate(result)),
                    sum(scores[r][w] for r, w in enumerate(result) if w >= 0 and priorities[buildings[r]] == tier))
                   for tier in range(4, -1, -1))
    unused = [quality[w] for w in range(movable) if w not in result]
    builder = sum(sorted(unused, reverse=True)[:reserve])
    if strict:
        return tuple(covered), counts, builder
    return tuple(covered), sum(w >= 0 for w in result), sum(scores[r][w] * (priorities[buildings[r]] + 1)
                for r, w in enumerate(result) if w >= 0), builder


def oracle(scores, buildings, minimum, priorities, flexible, strict, fixed, reserve, quality, movable):
    best = None
    for result in itertools.product(range(-1, len(quality)), repeat=len(buildings)):
        used = [w for w in result if w >= 0]
        if len(set(used)) != len(used) or any(w >= 0 and scores[r][w] < 0 for r, w in enumerate(result)):
            continue
        if any(w >= 0 and result[r] != w for r, w in enumerate(fixed)):
            continue
        if sum(w not in used for w in range(movable)) < reserve:
            continue
        if any(not flexible[b] and any(result[r] >= 0 and fixed[r] < 0 for r, owner in enumerate(buildings) if owner == b)
               and not all(result[r] >= 0 for r, owner in enumerate(buildings) if owner == b and minimum[r])
               for b in range(len(priorities))):
            continue
        value = key(result, scores, buildings, minimum, priorities, flexible, strict, reserve, quality, movable)
        best = value if best is None or value > best else best
    return best


def check(scores, buildings, minimum, priorities, flexible, strict, fixed=None, reserve=0, quality=None, movable=None, limit=64):
    global synthetic_face_seen
    workers = len(scores[0])
    fixed = fixed or [-1] * len(buildings)
    quality = quality or [float(w + 1) for w in range(workers)]
    movable = workers if movable is None else movable
    kept = min(reserve, movable)
    planner = unreal.new_object(unreal.load_class(None, ROOT + ".BP_StaffingPlanner_C"))
    has_quota_columns = "SolveColumns" in BP.list_variables(unreal.load_asset(ROOT))
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=([float(v) for row in scores for v in row], buildings, minimum, priorities, workers, strict))
    if "RequireFlexibleMinimum" in {str(g.get_name()) for g in BP.list_graphs(unreal.load_asset(ROOT))}:
        assert planner.call_method("RequireFlexibleMinimum", args=(flexible,))[-1]
    assert planner.call_method("RequireFixedSlots", args=(fixed,))[-1]
    if reserve:
        assert planner.call_method("KeepUnassigned", args=(reserve, movable, quality))[-1]
    rows = len(buildings) + kept
    columns = workers + len(buildings)
    passes = 6 if strict else 2
    work_bound = 1000 + 100 * (rows + columns + len(priorities)) ** 2
    work_bound += passes * rows * (rows + 1) * (10 * (columns + rows) + 100)
    for _ in range(math.ceil(work_bound / limit) + 1):
        if planner.get_editor_property("PlanDone"):
            break
        planner.call_method("AdvancePlan")
        assert 0 <= planner.get_editor_property("LastStepWork") <= limit
        if strict and has_quota_columns:
            synthetic_face_seen |= any(list(planner.get_editor_property("RequiredWorker"))[workers:])
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded"), (
        "Flexible crew rejected", scores, buildings, minimum, flexible, planner.get_editor_property("State"))
    result = list(planner.get_editor_property("PlanAssignment"))
    assert len(result) == len(buildings)
    assert all(-1 <= w < workers for w in result), "Synthetic columns escaped the public assignment"
    used = [w for w in result if w >= 0]
    assert len(used) == len(set(used)), "Worker assigned twice"
    assert all(w < 0 or scores[r][w] >= 0 for r, w in enumerate(result)), "Ineligible assignment"
    assert all(w < 0 or result[r] == w for r, w in enumerate(fixed)), "Fixed occupant moved"
    assert sum(w not in used for w in range(movable)) >= kept, "Reserve violated"
    for b in range(len(priorities)):
        if not flexible[b] and any(result[r] >= 0 and fixed[r] < 0 for r, owner in enumerate(buildings) if owner == b):
            assert all(result[r] >= 0 for r, owner in enumerate(buildings) if owner == b and minimum[r]), "Incomplete native crew"
    expected = oracle(scores, buildings, minimum, priorities, flexible, strict, fixed, kept, quality, movable)
    actual = key(result, scores, buildings, minimum, priorities, flexible, strict, kept, quality, movable)
    assert actual == expected, (scores, buildings, priorities, strict, result, actual, expected)
    return result


def run():
    rng = random.Random(31005)
    for strict in (False, True):
        assert check([[-1], [10]], [0, 0], [False, False], [4], [True], strict, limit=1) == [-1, 0]
        assert check([[10, -1], [-1, 8], [7, -1]], [0, 0, 1], [False] * 3, [4, 2], [True, True], strict) == [-1, 1, 0]
        # The later native demand must rehome the earlier flexible demand too.
        assert check([[10, -1], [-1, 8], [7, -1]], [0, 0, 1], [False, False, True], [4, 2], [True, False], strict) == [-1, 1, 0]
        check([[1, 20], [10, -1]], [0, 0], [False] * 2, [4], [True], strict, limit=1)
        for reserve in (0, 1, 100):
            check([[9, 3, 1], [2, 12, 1], [5, 6, 7]], [0, 0, 1], [False, False, True], [4, 1], [True, False], strict, reserve=reserve)
        check([[1, -1, -1], [3, 4, 9], [7, 8, -1]], [0, 0, 1], [False, False, True], [4, 2], [True, False], strict, fixed=[-1, 2, -1], reserve=1, movable=2)
        for _ in range(100):
            scores = [[rng.choice((-1, 0, 1, 3, 8, 20)) for _ in range(3)] for _ in range(4)]
            check(scores, [0, 0, 1, 1], [False] * 4, [rng.randrange(5), rng.randrange(5)], [True, True], strict)
    assert synthetic_face_seen, "Fixtures must exercise negative-potential synthetic columns as required-used"
    native_pipeline()
    unreal.log("WO_FLEXIBLE_MINIMUM_TESTS_PASS: physical-slot exhaustive oracles, non-first eligibility, flexible/native rerouting, competing flexible demands, fixed/reserve, strict synthetic optimum faces, native education/layout/search/action-plan integration, both modes and limit-1")


def native_pipeline():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda name: unreal.load_class(None, root + name + "." + name + "_C")
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

    def spawn(name):
        actor = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(actor)
        return actor

    snapshot, layout, matrix, planner, search, scorer, settings, actions = (
        unreal.new_object(load(name)) for name in ("BP_WorkforceSnapshot", "BP_ProblemLayout", "BP_ScoreMatrix",
        "BP_StaffingPlanner", "BP_PlanSearch", "BP_JobScorer", "BP_PrioritySettings", "BP_ActionPlan"))
    assert scorer.call_method("Configure", args=(25., -10., 20., 15., 10.))
    try:
        workers = [spawn("Prototype_Agent") for _ in range(4)]
        for i, worker in enumerate(workers):
            ch = worker.get_editor_property("m_characteristics")
            assert ch.import_text(f'(ID={7300+i},education={"Apprentice" if i != 2 else "None"},guild="fixture{i}")')
            put(worker, "m_characteristics", ch)
        buildings, components = [], []
        for i, slots in enumerate((2, 1, 1)):
            building = spawn("GridActor")
            for name, value in (("ID", 7310+i), ("isPlayerOwned", True), ("Health", 100)):
                put(building, name, value)
            comp = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
            wf = comp.get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=(" + ",".join("(educationRequirement=Apprentice)" for _ in range(slots)) + "))")
            if i == 2:
                values = list(wf.get_editor_property("m_workerSlots"))
                put(values[0], "Agent", workers[3])
                put(wf, "m_workerSlots", values)
                put(wf, "bDisabled", True)
            put(comp, "m_workers", wf)
            buildings.append(building)
            components.append(comp)

        def solve(pool, priorities, strict, reserve=0, incumbent=False, nonfirst=False, protected=False):
            wf = components[0].get_editor_property("m_workers")
            assert wf.import_text("(m_workerSlots=((educationRequirement=" + ("Master" if nonfirst else "Apprentice") + "),(educationRequirement=Apprentice)))")
            if incumbent or protected:
                values = list(wf.get_editor_property("m_workerSlots"))
                put(values[1], "Agent", workers[1] if protected else workers[0])
                put(wf, "m_workerSlots", values)
            put(components[0], "m_workers", wf)
            before = [comp.get_editor_property("m_workers").export_text() for comp in components]
            snapshot.call_method("ResetSnapshot")
            for i, building in enumerate(buildings):
                assert snapshot.call_method("AddBuilding", args=(building,)) == (i != 2)
            snapshot.call_method("FinishBuildings")
            for worker in pool:
                assert snapshot.call_method("AddWorker", args=(worker, buildings[0] if incumbent and worker == workers[0] else None))
            assert not snapshot.call_method("AddWorker", args=(workers[3], buildings[2]))
            assert workers[3] in snapshot.get_editor_property("ProtectedWorkers")
            assert layout.call_method("BeginLayout", args=(snapshot,))
            assert not layout.get_editor_property("ColumnWorkers"), "Worker column initialization is incremental"
            for _ in range(1000):
                if layout.get_editor_property("LayoutDone"):
                    break
                layout.call_method("AdvanceLayout")
            assert layout.get_editor_property("LayoutSucceeded")
            assert list(layout.get_editor_property("FlexibleMinimumBuildings")) == [True, True]
            assert list(layout.get_editor_property("Minimum")) == [False] * 3
            assert search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))
            assert search.call_method("ConfigureReserve", args=(reserve, [float(i+1) for i in range(len(layout.get_editor_property("ColumnActors")))]))[-1]
            for _ in range(20000):
                if search.get_editor_property("SearchDone"):
                    break
                if search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                    if matrix.get_editor_property("SetupActive"):
                        matrix.call_method("AdvanceMatrix")
                    elif matrix.get_editor_property("Stage") == 0:
                        assert matrix.call_method("RecordDefinition", args=("fixture", True))
                    elif matrix.get_editor_property("AwaitingScore"):
                        assert matrix.call_method("RecordScore", args=(True, 1000. if matrix.get_editor_property("EdgeBuilding") == buildings[0] else 10.))
                    else:
                        if matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("PolicyImported"):
                            assert matrix.call_method("UsePolicy", args=(priorities, strict))[-1]
                        matrix.call_method("PrepareEdge")
                else:
                    search.call_method("AdvanceSearch")
            assert search.get_editor_property("SearchDone") and search.get_editor_property("SearchSucceeded"), search.get_editor_property("FailureCode")
            result = list(search.get_editor_property("BestAssignment"))
            assert list(search.get_editor_property("BestCoverage")) == [any(w >= 0 for w in result[:2]), result[2] >= 0], "Search comparison must use actual flexible crew coverage"
            targets = [layout.get_editor_property("ColumnWorkers")[w] if w >= 0 else -1 for w in result]
            assert actions.call_method("BeginBuild", args=(snapshot, targets))[-1]
            for _ in range(1000):
                if actions.get_editor_property("BuildDone"):
                    break
                actions.call_method("AdvanceBuild")
            assert actions.get_editor_property("BuildSucceeded")
            assert before == [comp.get_editor_property("m_workers").export_text() for comp in components]
            return result

        for strict in (False, True):
            # Fishery and stonecutting crew roles share the sole Apprentice.
            result = solve(workers[:1], [4, 2], strict)
            assert sum(w >= 0 for w in result[:2]) == 1 and result[2] == -1, result
            result = solve(workers[:1], [2, 4], strict, incumbent=True)
            assert result == [-1, -1, 0], result
            assert list(actions.get_editor_property("ActionFire")) == [True, False], "Qualified optional incumbent must be movable"
            result = solve(workers[:2], [4, 2], strict)
            assert sum(w >= 0 for w in result[:2]) == 1 and result[2] >= 0, "Coverage before extras"
            result = solve(workers[:1], [4, 2], strict, nonfirst=True)
            assert result == [-1, 0, -1], result
            result = solve(workers[:1], [2, 4], strict, protected=True)
            assert result == [-1, 1, 0], "Protected actor columns remain real crew occupants"
            result = solve(workers[:1], [2, 4], strict, protected=True, reserve=1)
            assert result == [-1, 1, -1], "Protected crew does not consume movable reserve"
            for reserve in (0, 1, 100):
                result = solve(workers[:3], [4, 2], strict, reserve=reserve)
                assert sum(w >= 0 for w in result) <= len(workers[:3]) - min(reserve, 3)
                if reserve <= 1:
                    assert result[2] >= 0 and any(w >= 0 for w in result[:2]), result

        school = spawn("GridActor")
        for name, value in (("ID", 7340), ("isPlayerOwned", True), ("Health", 100)):
            put(school, name, value)
        school_component = school.call_method("AddComponentByClass", args=(native("School"), False, unreal.Transform(), False))
        wf = school_component.get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((bIsRequiredToRun=True),()))")
        put(school_component, "m_workers", wf)
        wf = components[0].get_editor_property("m_workers")
        assert wf.import_text("(m_workerSlots=((educationRequirement=Apprentice),(educationRequirement=Apprentice)))")
        put(components[0], "m_workers", wf)
        ch = workers[1].get_editor_property("m_characteristics")
        assert ch.import_text("(education=None)")
        put(workers[1], "m_characteristics", ch)

        def mixed_key(result, priorities, strict):
            coverage = (any(w >= 0 for w in result[:2]), result[2] >= 0, all(w >= 0 for w in result[3:]))
            covered = tuple(coverage[b] for b in sorted(range(3), key=lambda b: (-priorities[b], b)))
            learning = 100. * (3 if result[3] == 0 else 1) * (2 if result[4] == 2 else 1) if coverage[2] else 0.
            scores = [1000. if result[r] >= 0 else 0. for r in range(2)] + [10. if result[2] >= 0 else 0., 0., learning]
            owners = [0, 0, 1, 2, 2]
            counts = tuple((sum(w >= 0 and priorities[owners[r]] == tier for r, w in enumerate(result)),
                            sum(scores[r] for r in range(5) if priorities[owners[r]] == tier)) for tier in range(4, -1, -1))
            return (covered, counts) if strict else (covered, sum(w >= 0 for w in result), sum(scores[r] * (priorities[owners[r]] + 1) for r in range(5)))

        for strict in (False, True):
            for priorities in ([2, 1, 4], [4, 1, 2], [2, 4, 1]):
                snapshot.call_method("ResetSnapshot")
                for building in buildings[:2] + [school]:
                    assert snapshot.call_method("AddBuilding", args=(building,))
                snapshot.call_method("FinishBuildings")
                for worker in workers[:3]:
                    assert snapshot.call_method("AddWorker", args=(worker, None))
                assert layout.call_method("BeginLayout", args=(snapshot,))
                for _ in range(1000):
                    if layout.get_editor_property("LayoutDone"):
                        break
                    layout.call_method("AdvanceLayout")
                assert layout.get_editor_property("LayoutSucceeded")
                assert list(layout.get_editor_property("FlexibleMinimumBuildings")) == [True, True, False]
                assert search.call_method("BeginSearch", args=(layout, matrix, planner, scorer, settings, settings))
                for _ in range(50000):
                    if search.get_editor_property("SearchDone"):
                        break
                    if search.get_editor_property("State") == 2 and matrix.get_editor_property("MatrixActive"):
                        if matrix.get_editor_property("SetupActive"):
                            matrix.call_method("AdvanceMatrix")
                        elif matrix.get_editor_property("Stage") == 0:
                            assert matrix.call_method("RecordDefinition", args=("fixture", True))
                        elif matrix.get_editor_property("AwaitingScore"):
                            if matrix.get_editor_property("SchoolEdge"):
                                teacher = list(layout.get_editor_property("ColumnActors")).index(matrix.get_editor_property("EdgeTeacher"))
                                value = (3. if teacher == 0 else 1.) * (2. if matrix.get_editor_property("EdgeColumn") == 2 else 1.)
                            else:
                                value = 1000. if matrix.get_editor_property("EdgeBuilding") == buildings[0] else 10.
                            assert matrix.call_method("RecordScore", args=(True, value))
                        else:
                            if matrix.get_editor_property("EdgeIndex") == 0 and not matrix.get_editor_property("PolicyImported"):
                                assert matrix.call_method("UsePolicy", args=(priorities, strict))[-1]
                            matrix.call_method("PrepareEdge")
                    else:
                        search.call_method("AdvanceSearch")
                assert search.get_editor_property("SearchDone") and search.get_editor_property("SearchSucceeded"), search.get_editor_property("FailureCode")
                result = list(search.get_editor_property("BestAssignment"))
                candidates = []
                for candidate in itertools.product(range(-1, 3), repeat=5):
                    used = [w for w in candidate if w >= 0]
                    if len(used) != len(set(used)) or any(w > 0 for w in candidate[:3]):
                        continue
                    if (candidate[3] >= 0) != (candidate[4] >= 0):
                        continue
                    candidates.append(mixed_key(candidate, priorities, strict))
                assert mixed_key(result, priorities, strict) == max(candidates), (strict, priorities, result)
                assert list(search.get_editor_property("BestCoverage")) == [any(w >= 0 for w in result[:2]), result[2] >= 0, all(w >= 0 for w in result[3:])]
    finally:
        for actor in reversed(spawned):
            actors.destroy_actor(actor)


run()
