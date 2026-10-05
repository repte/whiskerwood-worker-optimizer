"""Production planner reserve constraints, including exact assignment oracles."""

import itertools
import random
import runpy
from pathlib import Path

import unreal


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_StaffingPlanner")
    assert "KeepUnassigned" in {str(g.get_name()) for g in BP.list_graphs(bp)}, "Planner has no free-worker reserve constraint"
    # Loading the existing oracle also runs its regression suite.
    helpers = runpy.run_path(str(Path(__file__).with_name("test_planner.py")))
    key = helpers["policy_key"]

    def solve(scores, buildings, minimum, priorities, reserve, quality, strict, fixed=None, movable=None):
        p = unreal.new_object(cls)
        workers = len(quality)
        p.call_method("StartPlan", args=([float(v) for row in scores for v in row], buildings, minimum, priorities, workers, strict))
        fixed = fixed or [-1] * len(scores)
        if not p.get_editor_property("PlanDone"):
            assert p.call_method("RequireFixedSlots", args=(fixed,))
            assert p.call_method("KeepUnassigned", args=(reserve, workers if movable is None else movable, quality))[-1]
        for _ in range(40000):
            if p.get_editor_property("PlanDone"):
                break
            p.call_method("AdvancePlan")
        assert p.get_editor_property("PlanDone") and p.get_editor_property("PlanSucceeded"), (scores, reserve, strict, p.get_editor_property("State"))
        result = list(p.get_editor_property("PlanAssignment"))
        assert len(result) == len(scores), "Virtual reserve jobs leaked into real workplace assignments"
        return result

    for strict in (False, True):
        scores = [[100, 100, 100, 100]] * 5
        result = solve(scores, [0, 0, 1, 1, 2], [True, False, True, False, True], [4, 4, 0], 1, [1., 2., 3., 4.], strict)
        assert helpers["counts"](result, [0, 0, 1, 1, 2]) == [1, 1, 1], result
        assert 3 not in result, "Equal-production plans should leave the better builder free"
        assert solve([[100, 100]], [0], [True], [4], 9, [1., 2.], strict) == [-1]
        assert solve([[100, 1], [1, 100]], [0, 1], [True, True], [4, 0], 1, [100., 1.], strict) == [0, -1], "Builder preference must not sacrifice higher-priority production"
        assert solve([[100, 100, 0], [100, 1, -1]], [0, 1], [True, True], [0, 4], 2, [1., 2., 0.], strict, [2, -1], 2) == [2, -1], "Protected occupants are not free builders"

    rng = random.Random(812)
    for case in range(36):
        scores = [[rng.choice([-1, 0, 1, 7]) for _ in range(3)] for _ in range(4)]
        buildings, minimum = [0, 0, 1, 1], [True, False, True, False]
        priorities = [rng.randrange(5), rng.randrange(5)]
        reserve = rng.randrange(4)
        quality = [1., 3., 2.]
        for strict in (False, True):
            actual = solve(scores, buildings, minimum, priorities, reserve, quality, strict)
            candidates = []
            for assignment in itertools.product(range(-1, 3), repeat=4):
                used = [w for w in assignment if w >= 0]
                if len(used) != len(set(used)) or len(used) > 3 - reserve:
                    continue
                if any(w >= 0 and scores[r][w] < 0 for r, w in enumerate(assignment)):
                    continue
                if any(assignment[r + 1] >= 0 and assignment[r] < 0 for r in (0, 2)):
                    continue
                candidates.append((key(assignment, scores, buildings, minimum, priorities, strict), sum(sorted((quality[w] for w in range(3) if w not in used), reverse=True)[:reserve])))
            observed = (key(actual, scores, buildings, minimum, priorities, strict), sum(sorted((quality[w] for w in range(3) if w not in actual), reverse=True)[:reserve]))
            assert observed == max(candidates), (case, strict, reserve, scores, actual, observed, max(candidates))
    unreal.log("WO_RESERVE_TESTS_PASS: reserve limits, coverage, protected incumbents, production-first builder ties and 72 exhaustive-oracle cases")


run()
