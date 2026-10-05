"""Behavior tests for the compiled staffing policy and its real solver."""

import itertools
import random
import time

import unreal


def plan(scores, buildings, minimum, priorities, strict=False, fixed=None):
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    assert cls is not None, "Production staffing planner does not exist"
    planner = unreal.new_object(cls)
    workers = len(scores[0]) if scores else 0
    planner.call_method("StartPlan", args=(
        [float(value) for row in scores for value in row], buildings, minimum,
        priorities, workers, strict,
    ))
    if fixed is not None:
        configured = planner.call_method("RequireFixedSlots", args=(fixed,))
        assert configured[-1] if isinstance(configured, tuple) else configured
    for _ in range(20000):
        if planner.get_editor_property("PlanDone"):
            break
        planner.call_method("AdvancePlan")
    assert planner.get_editor_property("PlanDone"), "Planner did not finish"
    assert planner.get_editor_property("PlanSucceeded"), (
        f"Planner rejected a valid input: state={planner.get_editor_property('State')}, "
        f"tier={planner.get_editor_property('Tier')}, scores={scores}, priorities={priorities}, "
        f"result={list(planner.get_editor_property('Assignment'))}"
    )
    result = list(planner.get_editor_property("PlanAssignment"))
    assigned = [worker for worker in result if worker >= 0]
    assert len(assigned) == len(set(assigned)), "Worker assigned more than once"
    for row, worker in enumerate(result):
        assert worker < 0 or scores[row][worker] >= 0, "Ineligible assignment"
    for building in range(len(priorities)):
        rows = [i for i, owner in enumerate(buildings) if owner == building]
        if any(result[i] >= 0 and (fixed is None or fixed[i] < 0) for i in rows):
            assert all(result[i] >= 0 for i in rows if minimum[i]), "Stranded partial minimum crew"
    if fixed is not None:
        assert all(w < 0 or result[r] == w for r, w in enumerate(fixed)), "Fixed incumbent displaced"
    return result


def counts(result, buildings):
    return [sum(worker >= 0 and owner == b for worker, owner in zip(result, buildings))
            for b in range(max(buildings, default=-1) + 1)]


def policy_key(result, scores, buildings, minimum, priorities, strict=False):
    order = sorted(range(len(priorities)), key=lambda b: (-priorities[b], b))
    covered = tuple(all(result[r] >= 0 for r, owner in enumerate(buildings) if owner == b and minimum[r])
                    for b in order)
    if strict:
        return (covered, tuple(
            (sum(w >= 0 and priorities[buildings[r]] == tier for r, w in enumerate(result)),
             sum(scores[r][w] for r, w in enumerate(result) if w >= 0 and priorities[buildings[r]] == tier))
            for tier in range(4, -1, -1)
        ))
    return (covered, sum(w >= 0 for w in result),
            sum(scores[r][w] * (priorities[buildings[r]] + 1) for r, w in enumerate(result) if w >= 0))


def oracle(scores, buildings, minimum, priorities, strict=False, fixed=None):
    best = None
    for result in itertools.product(range(-1, len(scores[0])), repeat=len(scores)):
        used = [w for w in result if w >= 0]
        if len(used) != len(set(used)) or any(w >= 0 and scores[r][w] < 0 for r, w in enumerate(result)):
            continue
        if fixed is not None and any(w >= 0 and result[r] != w for r, w in enumerate(fixed)):
            continue
        if any(any(result[r] >= 0 and (fixed is None or fixed[r] < 0) for r, owner in enumerate(buildings) if owner == b)
               and not all(result[r] >= 0 for r, owner in enumerate(buildings) if owner == b and minimum[r])
               for b in range(len(priorities))):
            continue
        key = policy_key(result, scores, buildings, minimum, priorities, strict)
        best = key if best is None or key > best else best
    return best


def run():
    for strict in (False, True):
        # An immovable optional incumbent survives even if its minimum crew is impossible.
        assert plan([[-1, -1], [7, 9], [5, 5]], [0, 0, 1], [True, False, True],
                    [4, 0], strict, [-1, 0, -1]) == [-1, 0, 1]
        # Locked required slots count toward coverage; remaining slots still participate.
        assert plan([[1, 100, 100], [100, 3, 4], [5, 9, 2]], [0, 0, 1],
                    [True, True, True], [4, 0], strict, [0, -1, -1]) == [0, 2, 1]
        # A fixed worker cannot be stolen by a higher-priority building.
        assert plan([[0], [100]], [0, 1], [True, True], [0, 4], strict, [0, -1]) == [0, -1]
    fixed_rng = random.Random(7201)
    for _ in range(30):
        buildings = [0, 0, 1, 1]
        minimum = [True, fixed_rng.choice([True, False]), True, False]
        priorities = [fixed_rng.randrange(5), fixed_rng.randrange(5)]
        scores = [[fixed_rng.choice([-1, 0, 1, 7]) for _ in range(3)] for _ in buildings]
        fixed = [-1] * 4
        locked_row = fixed_rng.randrange(4)
        fixed[locked_row] = 0
        scores[locked_row][0] = 0
        for strict in (False, True):
            result = plan(scores, buildings, minimum, priorities, strict, fixed)
            assert policy_key(result, scores, buildings, minimum, priorities, strict) == oracle(
                scores, buildings, minimum, priorities, strict, fixed), (scores, fixed, result)
    for strict in (False, True):
        # The user's shortage example: food must not absorb the logger's worker.
        b = [0, 0, 1, 1, 2]
        result = plan([[100] * 4 for _ in b], b, [True, False, True, False, True], [4, 4, 0], strict)
        staffing = counts(result, b)
        assert staffing[2] == 1 and sorted(staffing[:2]) == [1, 2], staffing
        # Two obligatory roles must both be viable before any optional slot.
        result = plan([[8, -1], [-1, 9], [100, 100], [5, 5]], [0, 0, 0, 1],
                      [True, True, False, True], [4, 0], strict)
        assert counts(result, [0, 0, 0, 1]) == [2, 0]
        # Individually eligible required slots compete for the same worker.
        result = plan([[9, -1], [8, -1], [4, 5]], [0, 0, 1], [True] * 3, [4, 0], strict)
        assert result[:2] == [-1, -1] and result[2] >= 0
        # Priority decides when not even one worker per building is possible.
        result = plan([[5, 5]] * 3, [0, 1, 2], [True] * 3, [0, 4, 2], strict)
        assert result[0] == -1 and result[1] >= 0 and result[2] >= 0
        # Empty inputs and no workers must finish without inventing assignments.
        assert plan([], [], [], [], strict) == []
        assert plan([[], []], [0, 1], [True, True], [2, 2], strict) == [-1, -1]
    # Same feasible minimum coverage, but deliberately conflicting productivity.
    assert plan([[10, 9], [100, 1]], [0, 1], [True, True], [4, 0], True) == [0, 1]
    assert plan([[10, 9], [100, 1]], [0, 1], [True, True], [4, 0], False) == [1, 0]
    # A tie in the higher tier must remain available to improve the lower tier.
    assert plan([[10, 10], [100, 1]], [0, 1], [True, True], [4, 0], True) == [1, 0]
    # A rectangular optimum also constrains columns with nonzero dual values.
    assert plan([[3, 0, 3, -1], [2, 1, 1, 0], [1, 2, 0, 1], [2, -1, 1, 0],
                 [1, 1, 1, 1], [1, 3, 1, 1]], [0, 0, 0, 1, 1, 2],
                [True, False, False, True, False, True], [4, 0, 3], True) == [2, 0, -1, 3, -1, 1]
    # Cardinality before productivity for additional slots.
    result = plan([[1, 1, 1], [-1, 100, 1], [-1, 1, -1]], [0, 0, 0],
                  [True, False, False], [2])
    assert all(worker >= 0 for worker in result), result
    rng = random.Random(5021)
    for _ in range(60):
        buildings = [0, 0, 1, 1, 2]
        minimum = [True, rng.choice([True, False]), True, rng.choice([True, False]), True]
        priorities = [rng.randrange(5) for _ in range(3)]
        scores = [[rng.choice([-1, 0, 1, 7, 25]) for _ in range(3)] for _ in buildings]
        for strict in (False, True):
            result = plan(scores, buildings, minimum, priorities, strict)
            assert policy_key(result, scores, buildings, minimum, priorities, strict) == oracle(scores, buildings, minimum, priorities, strict), (
                scores, minimum, priorities, strict, result,
            )
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    invalid = unreal.new_object(cls)
    for fixed in ([0], [0, 0], [-2, -1], [2, -1]):
        invalid.call_method("StartPlan", args=([1.0] * 4, [0, 1], [True, True], [2, 2], 2, False))
        assert not invalid.call_method("RequireFixedSlots", args=(fixed,))[-1]
        assert invalid.get_editor_property("PlanDone") and not invalid.get_editor_property("PlanSucceeded")
    invalid.call_method("StartPlan", args=([-1.0, 1.0], [0], [True], [2], 2, False))
    assert not invalid.call_method("RequireFixedSlots", args=([0],))[-1]
    assert not invalid.get_editor_property("PlanSucceeded")
    invalid.call_method("StartPlan", args=([1.0, 3.0, 3.0, 1.0], [0, 1], [True, True], [2, 2], 2, True))
    assert invalid.call_method("RequireFixedSlots", args=([0, -1],))[-1]
    assert not invalid.call_method("RequireFixedSlots", args=([-1, 0],))[-1], "Cannot replace constraints mid-run"
    while not invalid.get_editor_property("PlanDone"):
        invalid.call_method("AdvancePlan")
    assert invalid.get_editor_property("PlanSucceeded")
    assert list(invalid.get_editor_property("PlanAssignment")) == [0, 1]
    # Reusing the planner clears every fixed constraint.
    invalid.call_method("StartPlan", args=([1.0, 3.0, 3.0, 1.0], [0, 1], [True, True], [2, 2], 2, True))
    invalid.call_method("AdvancePlan")
    assert not invalid.call_method("RequireFixedSlots", args=([0, -1],))[-1]
    while not invalid.get_editor_property("PlanDone"):
        invalid.call_method("AdvancePlan")
    assert invalid.get_editor_property("PlanSucceeded")
    assert list(invalid.get_editor_property("PlanAssignment")) == [1, 0]
    for args in (([1.0], [0], [False], [2], 1, False),
                 ([1.0], [-1], [True], [2], 1, False),
                 ([1.0], [0], [True], [5], 1, False),
                 ([1.0], [0], [True], [2], 2, False)):
        invalid.call_method("StartPlan", args=args)
        assert invalid.get_editor_property("PlanDone") and not invalid.get_editor_property("PlanSucceeded")
    start = time.perf_counter()
    size = 200
    scores = [[100 if w == (r + 17) % size else 1 for w in range(size)] for r in range(size)]
    for strict in (False, True):
        result = plan(scores, [r // 2 for r in range(size)], [r % 2 == 0 for r in range(size)],
                      [b % 5 for b in range(size // 2)], strict)
        assert result == [(r + 17) % size for r in range(size)]
    unreal.log(f"WO_PLANNER_DENSE: both modes, 200 slots, 200 workers, {time.perf_counter()-start:.3f}s total editor time")
    unreal.log("WO_PLANNER_TESTS_PASS: coverage, complete crews, shortages, strict/weighted, 180 independent oracle cases including locked incumbents, invalid fixed constraints and reuse")


run()
