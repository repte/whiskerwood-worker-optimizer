"""Execute the shipped Blueprint solver, not a Python copy of the algorithm."""

import itertools
import math
import random
import time

import unreal


def solve(matrix, columns=None, max_steps=None, allowed_empty=None):
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
    assert cls is not None, "Production Blueprint solver does not exist"
    solver = unreal.new_object(cls)
    rows = len(matrix)
    cols = len(matrix[0]) if rows else (columns or 0)
    solver.call_method("Initialize", args=(list(itertools.chain.from_iterable(matrix)), rows, cols))
    if allowed_empty is not None:
        solver.call_method("RestrictDummies", args=(allowed_empty,))
    advances = 0
    primitive_work = 0
    width = rows + cols
    limit = solver.get_editor_property("StepWorkLimit")
    primitive_bound = rows * cols + rows * (rows + 1) * (3 * width + 10) + cols + 3 * rows + 20
    # A bounded phase may yield with a partially used budget.
    for _ in range(primitive_bound + 1):
        if solver.get_editor_property("Done"):
            break
        solver.call_method("Advance")
        assert 0 < solver.get_editor_property("LastStepWork") <= limit
        primitive_work += int(solver.get_editor_property("LastStepWork"))
        assert primitive_work <= primitive_bound, "Solver exceeded its primitive work bound"
        advances += 1
    assert solver.get_editor_property("Done"), "Solver failed to finish within bounded primitive steps"
    assert solver.get_editor_property("Succeeded"), "Solver rejected valid matrix"
    tie_bound = rows * cols + rows + (max_steps or 0) * (3 * width + 10) + cols + rows + 20
    assert max_steps is None or primitive_work <= tie_bound, f"Equal-score matching wasted width scans: {primitive_work} > {tie_bound}"
    result = list(solver.get_editor_property("Assignment"))
    assert len(result) == rows
    chosen = [col for col in result if col >= 0]
    assert len(chosen) == len(set(chosen)), "A worker was assigned twice"
    for row, col in enumerate(result):
        assert col < cols
        assert col < 0 or matrix[row][col] > -1e8, "Ineligible worker was assigned"
    return result


def objective(matrix, assignment):
    return sum(matrix[row][col] for row, col in enumerate(assignment) if col >= 0)


def brute_force(matrix):
    cols = len(matrix[0]) if matrix else 0
    best = 0
    for assignment in itertools.product(range(-1, cols), repeat=len(matrix)):
        used = [c for c in assignment if c >= 0]
        if len(used) != len(set(used)):
            continue
        best = max(best, objective(matrix, assignment))
    return best


def run():
    assert solve([[9, 8], [8, 1]]) == [1, 0], "Greedy selection stranded the second job"
    assert solve([[10, -1e9], [20, -1e9]]) == [-1, 0], "Scarce eligible worker went to the wrong job"
    assert solve([[-1e9, 5], [7, -1e9]]) == [1, 0]
    assert solve([[5], [9], [2]]) == [-1, 0, -1]
    assert solve([[4, 8, 6]]) == [1]
    assert solve([]) == []
    assert solve([[], []]) == [-1, -1]
    assert solve([[-1e9]]) == [-1]
    assert solve([[3, 3], [3, 3]]) == solve([[3, 3], [3, 3]]), "Unstable tie behavior"
    assert len(solve([[5] * 12 for _ in range(12)], max_steps=13)) == 12
    assert solve([[100], [99]], allowed_empty=[True, False]) == [-1, 0]
    rng = random.Random(701)
    for rows in range(1, 5):
        for cols in range(1, 5):
            for _ in range(6):
                matrix = [[rng.choice([-1e9, 1, 2, 3, 8, 13]) for _ in range(cols)] for _ in range(rows)]
                assert objective(matrix, solve(matrix)) == brute_force(matrix), matrix
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
    invalid = unreal.new_object(cls)
    invalid.call_method("Initialize", args=([1.0], 2, 3))
    assert invalid.get_editor_property("Done") and not invalid.get_editor_property("Succeeded")
    for value in (float("nan"), float("inf"), -float("inf"), 1e25):
        invalid.call_method("Initialize", args=([value], 1, 1))
        invalid.call_method("Advance")
        assert invalid.get_editor_property("Done") and not invalid.get_editor_property("Succeeded"), (
            f"Invalid score accepted: {value}; stored={list(invalid.get_editor_property('Scores'))}; "
            f"done={invalid.get_editor_property('Done')}; success={invalid.get_editor_property('Succeeded')}"
        )
    invalid.call_method("Initialize", args=([4.0, 9.0], 1, 2))
    for _ in range(10):
        if invalid.get_editor_property("Done"):
            break
        invalid.call_method("Advance")
    assert list(invalid.get_editor_property("Assignment")) == [1], "Reinitialization retained old state"
    invalid.call_method("Advance")
    assert list(invalid.get_editor_property("Assignment")) == [1], "Completed step changed result"
    start = time.perf_counter()
    size = 200
    dense = [[10 if col == (row + 17) % size else 1 for col in range(size)] for row in range(size)]
    assert solve(dense) == [(row + 17) % size for row in range(size)]
    unreal.log(f"WO_SOLVER_TESTS_PASS: fixtures, 96 exhaustive-oracle cases, validation/reuse; dense 200x200 {time.perf_counter()-start:.3f}s")


run()
