"""Skip reserve optimization only when the current reserve reaches its upper bound."""

import unreal


def solve(scores, quality, reserve, expected_passes, expected_builder, expected_productivity,
          strict=True, fixed=None, movable=None, planner=None, success=True, limit=1):
    workers = len(quality)
    rows = len(scores)
    if planner is None:
        planner = unreal.new_object(unreal.load_class(
            None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C"))
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=(
        [float(value) for row in scores for value in row], list(range(rows)), [True] * rows,
        [2] * rows, workers, strict))
    if fixed is not None:
        assert planner.call_method("RequireFixedSlots", args=(fixed,))[-1]
    assert planner.call_method("KeepUnassigned", args=(reserve, workers if movable is None else movable, quality))[-1]
    passes = 0
    for _ in range(100000):
        if planner.get_editor_property("PlanDone"):
            break
        before = int(planner.get_editor_property("State"))
        planner.call_method("AdvancePlan")
        if before != 5 and planner.get_editor_property("State") == 5:
            passes += 1
        assert 0 < planner.get_editor_property("LastStepWork") <= limit
    assert planner.get_editor_property("PlanDone"), "Reserve certificate did not terminate within the work bound"
    assert bool(planner.get_editor_property("PlanSucceeded")) == success
    if not success:
        return planner
    assignment = list(planner.get_editor_property("PlanAssignment"))
    chosen = [worker for worker in assignment if worker >= 0]
    assert len(chosen) == len(set(chosen))
    assert len(chosen) <= workers - min(reserve, workers if movable is None else movable)
    assert all(worker < 0 or scores[row][worker] >= 0 for row, worker in enumerate(assignment))
    if fixed is not None:
        assert all(worker < 0 or assignment[row] == worker for row, worker in enumerate(fixed))
    productivity = sum(scores[row][worker] for row, worker in enumerate(assignment) if worker >= 0)
    assert productivity == expected_productivity, (assignment, productivity, expected_productivity)
    assert planner.get_editor_property("BuilderTotal") == expected_builder
    assert passes == expected_passes, (
        "A certified top-quality reserve repeated a full assignment pass", passes, expected_passes,
        quality, assignment, planner.get_editor_property("BuilderTotal"))
    return planner


def run():
    for strict in (False, True):
        # Equal qualities make the builder objective constant for every feasible plan.
        planner = solve([[10, 10, 10], [10, 10, 10]], [1.25] * 3, 1, 1, 1.25, 20, strict)
        # A non-uniform selected set can attain the global top-R bound as well.
        planner = solve([[10, -1, -1, -1], [-1, 10, -1, -1]],
                        [5., 0., 5., 9.], 2, 1, 14, 20, strict, planner=planner)
        # A more productive worker remains part of the optimistic builder bound.
        planner = solve([[100, 1]], [100., 1.], 1, 2, 1, 100, strict, planner=planner)
        # An uncertified reserve still receives its exact quality-improving pass.
        planner = solve([[10, 10, 10]], [1., 2., 9.], 1, 2, 9, 10, strict, planner=planner)
        # A small positive difference is not an equality certificate.
        planner = solve([[10, 10, 10]], [1., 1.03, 1.0300001], 1, 2, 1.0300001, 10,
                        strict, planner=planner)
        # Fixed owners and non-movable columns are not eligible reserve workers.
        planner = solve([[10, 0, 0], [0, 10, 0]], [100., 1., 1.], 1, 1, 1, 20,
                        strict, fixed=[0, -1], planner=planner)
        planner = solve([[0, 0, 10]], [1., 1., 100.], 1, 1, 1, 10,
                        strict, movable=2, planner=planner)
        planner = solve([[9, 1]], [10., 1.], 0, 1, 0, 9, strict, planner=planner)
        planner = solve([[9, 1]], [10., 1.], 1, 1, 0, 9,
                        strict, movable=0, planner=planner)
        planner = solve([], [5., 5.], 1, 1, 5, 0, strict, planner=planner)
        planner = solve([], [5., 5.], 0, 0, 0, 0, strict, planner=planner)
        solve([[10, 0], [0, 10]], [5., 5.], 1, 0, 0, 0,
              strict, fixed=[0, 1], planner=planner, success=False)
    unreal.log("WO_RESERVE_BOUND_TESTS_PASS: constant and attained top-R certificates, exact fallback, fixed/movable eligibility, empty inputs, limit1 and reuse")


run()
