"""Dense planner phases preserve results and yield at bounded phase boundaries."""

import unreal
from planner_test_cost_probe import supports_implicit
from planner_refinement_test_support import implicit_refinement_work


SCORES = [100.0 if row == worker else 1.0
          for row in range(4) for worker in range(4)]
PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")


def start(limit):
    planner = unreal.new_object(PLANNER_CLASS)
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=(
        SCORES, [0, 0, 1, 1], [True, False, True, False], [4, 0], 4, True))
    return planner


def advance(planner, limit):
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, ("Planner exceeded work budget", limit, work)
    return work


def implicit_refine_work(planner):
    return implicit_refinement_work(planner)


def finish(planner, limit):
    calls = work = 0
    states = set()
    while not planner.get_editor_property("PlanDone"):
        assert calls < 10000, "Planner did not complete the four-worker fixture"
        states.add(planner.get_editor_property("State"))
        work += advance(planner, limit)
        calls += 1
    assert planner.get_editor_property("PlanSucceeded")
    assignment = list(planner.get_editor_property("PlanAssignment"))
    assert assignment == [0, 1, 2, 3], assignment
    assert sum(SCORES[row * 4 + worker] for row, worker in enumerate(assignment)) == 400.0
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    return assignment, calls, work, states


def verify_equivalent_budgets():
    small = finish(start(1), 1)
    normal = finish(start(64), 64)
    assert small[0] == normal[0]
    assert small[2] == normal[2], ("Work changed with batch size", small[2], normal[2])
    assert normal[1] < small[1], ("Normal budget did not batch work", small[1], normal[1])
    assert {4, 5, 6, 26}.issubset(small[3]), small[3]
    return small[1], normal[1]


def verify_phase_boundaries():
    planner = start(1)
    for _ in range(10000):
        if planner.get_editor_property("State") == 26:
            break
        advance(planner, 1)
    else:
        raise AssertionError("Planner never reached expanded-matrix construction")
    assert planner.get_editor_property("BuildIndex") == 0
    cells = planner.get_editor_property("SlotCount") * planner.get_editor_property("SolveColumns")
    assert 0 < cells < 64
    planner.set_editor_property("StepWorkLimit", 64)
    work = advance(planner, 64)
    assert planner.get_editor_property("State") == 28, (
        "Matrix preparation must yield before starting another phase",
        planner.get_editor_property("State"), work)
    assert work == 1
    assert planner.get_editor_property("BuildIndex") == 0

    for _ in range(10000):
        if planner.get_editor_property("State") == 4:
            break
        advance(planner, 64)
    else:
        raise AssertionError("Planner never reached pass-matrix construction")
    assert planner.get_editor_property("BuildIndex") == 0
    work = advance(planner, 64)
    assert planner.get_editor_property("State") == 5, (
        "Pass-matrix batch must yield after initializing the solver",
        planner.get_editor_property("State"), work)
    expected_build_work = planner.get_editor_property("SlotCount") + 1 if supports_implicit(PLANNER_CLASS) else cells + 1
    assert work == expected_build_work, (work, expected_build_work)
    assert planner.get_editor_property("SolverState") == 1
    assert not planner.get_editor_property("Done")

    for _ in range(10000):
        if planner.get_editor_property("State") == 6:
            break
        advance(planner, 64)
    else:
        raise AssertionError("Planner never reached exact dual refinement")
    assert planner.get_editor_property("BuildIndex") == 0
    expected_refine_work = implicit_refine_work(planner)
    work = advance(planner, 64)
    assert planner.get_editor_property("State") == 30, (
        "Refinement batch must yield before starting another phase",
        planner.get_editor_property("State"), work)
    assert work == expected_refine_work, (work, expected_refine_work)
    assert not list(planner.get_editor_property("PassScores"))
    assert planner.get_editor_property("RetainedReady")
    finish(planner, 64)


def verify_cancel_and_invalid_budget():
    planner = start(1)
    for _ in range(10000):
        if planner.get_editor_property("State") == 26:
            break
        advance(planner, 1)
    else:
        raise AssertionError("Planner never reached the cancellable matrix phase")
    advance(planner, 1)
    cursor = planner.get_editor_property("BuildIndex")
    planner.call_method("FailPlan")
    planner.set_editor_property("StepWorkLimit", 64)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    assert planner.get_editor_property("BuildIndex") == cursor
    assert not planner.get_editor_property("PlanSucceeded")

    invalid = start(0)
    invalid.call_method("AdvancePlan")
    assert invalid.get_editor_property("PlanDone")
    assert not invalid.get_editor_property("PlanSucceeded")
    assert invalid.get_editor_property("LastStepWork") == 0


counts = verify_equivalent_budgets()
verify_phase_boundaries()
verify_cancel_and_invalid_budget()
unreal.log("WO_PLANNER_BATCHING_TESTS_PASS: exact budget1/64 result, phase fences, cancellation; calls=" + str(counts))
