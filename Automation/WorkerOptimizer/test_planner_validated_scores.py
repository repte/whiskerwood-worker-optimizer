"""Planner-generated costs need no second full input-validation traversal."""
import unreal
from test_planner_fused_matrix import expected_pass


def run():
    # Validated inputs and the slot-count cap bound every generated pass cost.
    capacity = 10001
    maximum = 1000000
    fill = ((maximum * 5) + 1) * capacity + 1
    coverage = (fill + maximum * 5 + 1) * capacity + 1
    column = (coverage + fill + maximum * 5 + 1) * capacity + 1
    assert fill + maximum * 5 + coverage + column < 1e20
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    solver_cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
    for strict in (False, True):
        planner = unreal.new_object(cls)
        planner.set_editor_property("StepWorkLimit", 1)
        planner.call_method("StartPlan", args=([1000000., -1e20, 0.125, 1000000.],
                                               [0, 1], [True, True], [4, 0], 2, strict))
        for _ in range(10000):
            if planner.get_editor_property("State") == 5:
                break
            planner.call_method("AdvancePlan")
        else:
            raise AssertionError("Planner did not start its first solver pass")
        assert planner.get_editor_property("SolverState") == 1, "Validated planner costs are scanned a second time"
        _, scores = expected_pass(planner, True)
        assert all(-1e20 <= value <= 1e20 for value in scores)
        solver = unreal.new_object(solver_cls)
        solver.set_editor_property("StepWorkLimit", 64)
        solver.call_method("Initialize", args=(scores, planner.get_editor_property("SlotCount"),
                                                planner.get_editor_property("SolveColumns")))
        solver.call_method("RestrictDummies", args=(list(planner.get_editor_property("AllowedEmpty")),))
        assert solver.get_editor_property("SolverState") == 0, "Direct solver callers must retain input validation"
        for candidate in (planner, solver):
            for _ in range(10000):
                if candidate.get_editor_property("Done"):
                    break
                candidate.call_method("Advance")
            assert candidate.get_editor_property("Done") and candidate.get_editor_property("Succeeded")
        for name in ("Assignment", "U", "V"):
            assert list(planner.get_editor_property(name)) == list(solver.get_editor_property(name)), name
    unreal.log("WO_PLANNER_VALIDATED_SCORES_PASS: bounded generated costs, unchanged assignments/duals, direct callers still validated")


run()
