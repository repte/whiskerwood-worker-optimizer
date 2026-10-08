"""Compiled admission, mask and reset regression for empty fixed configuration."""

import unreal


def accepted(value):
    return value[-1] if isinstance(value, (tuple, list)) else value


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    planner = unreal.new_object(cls)
    for limit in (1, 3, 64):
        # Reuse after a pinned plan and after rejected duplicate owners.
        for fixed, expected, succeed in (([1, -1], [1, 0], True),
                                         ([-1, -1], [0, 1], True),
                                         ([0, 0], None, False),
                                         ([-1, -1], [0, 1], True),
                                         ([-2, -1], None, False),
                                         ([-1, -1], [0, 1], True)):
            planner.set_editor_property("StepWorkLimit", limit)
            planner.call_method("StartPlan", args=([9.0, 2.0, 1.0, 8.0], [0, 1], [True, True], [2, 2], 2, True))
            assert accepted(planner.call_method("RequireFixedSlots", args=(fixed,)))
            assert not accepted(planner.call_method("RequireFixedSlots", args=(fixed,)))
            calls = 0
            while not planner.get_editor_property("PlanDone"):
                planner.call_method("AdvancePlan")
                assert 0 < planner.get_editor_property("LastStepWork") <= limit
                calls += 1
                assert calls < 10000
            assert planner.get_editor_property("PlanSucceeded") == succeed, fixed
            if succeed:
                assert list(planner.get_editor_property("PlanAssignment")) == expected, fixed
                expected_scores = [9.0, 2.0, 1.0, 8.0] if fixed[0] == -1 else [-1e20, 2.0, 1.0, -1e20]
                assert list(planner.get_editor_property("BaseScores")) == expected_scores, fixed
    unreal.log("WO_UNFIXED_VALIDATION_TESTS_PASS: fixed admission, masks, empty configuration, restart, malformed pins and budgets")


run()
