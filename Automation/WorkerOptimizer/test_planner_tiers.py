"""Absent priority tiers must not trigger whole-matrix assignment passes."""

import unreal


def solve(priorities, reserve):
    workers = rows = 40
    scores = [float(100 if column == (row + 7) % workers else 1)
              for row in range(rows) for column in range(workers)]
    planner = unreal.new_object(unreal.load_class(
        None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C"))
    planner.set_editor_property("StepWorkLimit", 64)
    planner.call_method("StartPlan", args=(scores, [r // 2 for r in range(rows)],
                                          [r % 2 == 0 for r in range(rows)], priorities, workers, True))
    if reserve:
        assert planner.call_method("KeepUnassigned", args=(reserve, workers, [1.] * workers))[-1]
    passes = 0
    for _ in range(100000):
        if planner.get_editor_property("PlanDone"):
            break
        previous = planner.get_editor_property("State")
        planner.call_method("AdvancePlan")
        if previous != 5 and planner.get_editor_property("State") == 5:
            passes += 1
        assert 0 < planner.get_editor_property("LastStepWork") <= 64
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assignment = list(planner.get_editor_property("PlanAssignment"))
    chosen = [worker for worker in assignment if worker >= 0]
    assert len(chosen) == len(set(chosen)) == workers - reserve
    assert all(any(assignment[r] >= 0 for r in (2 * b, 2 * b + 1)) for b in range(20))
    assert sum(scores[r * workers + w] for r, w in enumerate(assignment) if w >= 0) == 100 * (workers - reserve)
    # Equal reserve qualities already attain the reserve objective's upper bound.
    assert passes == len(set(priorities[:20])), (
        "Empty priority levels repeated dense matching", priorities, reserve, passes)
    if reserve:
        assert planner.get_editor_property("BuilderTotal") == reserve
    return passes


for tier in range(5):
    for reserve in (0, 3):
        solve([tier] * 20, reserve)
for reserve in (0, 3):
    solve([0, 4] * 10, reserve)
    # Definitions without slots must not make their priority tier active.
    solve([2] * 20 + [0, 4], reserve)
unreal.log("WO_PLANNER_TIERS_TESTS_PASS: exact coverage/productivity/reserve, sparse tiers and zero-slot definitions")
