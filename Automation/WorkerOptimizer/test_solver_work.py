"""Compiled solver throughput and restricted-dummy correctness regressions."""

import itertools
import math
import random
from decimal import Decimal, localcontext

import unreal


def execute(matrix, mask, limit=64, solver=None):
    rows, columns = len(matrix), len(matrix[0]) if matrix else 0
    if solver is None:
        cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
        solver = unreal.new_object(cls)
    solver.set_editor_property("StepWorkLimit", limit)
    solver.call_method("Initialize", args=([float(value) for row in matrix for value in row], rows, columns))
    solver.call_method("RestrictDummies", args=(mask,))
    bound = rows * columns + rows * (rows + 1) * (3 * (rows + columns) + 10) + 4 * (rows + columns) + 20
    work = 0
    for _ in range(bound + 1):
        if solver.get_editor_property("Done"):
            break
        solver.call_method("Advance")
        last = int(solver.get_editor_property("LastStepWork"))
        assert 0 < last <= limit, (last, limit)
        work += last
        assert work <= bound, "Solver exceeded the bounded primitive work"
    assert solver.get_editor_property("Done"), "Required rows must terminate even when the mask makes them impossible"
    return solver, list(solver.get_editor_property("Assignment")), work


def optimum(matrix, mask):
    best = None
    for assignment in itertools.product(range(-1, len(matrix[0])), repeat=len(matrix)):
        chosen = [column for column in assignment if column >= 0]
        if len(set(chosen)) != len(chosen) or any(column < 0 and not mask[row] for row, column in enumerate(assignment)):
            continue
        score = sum(matrix[row][column] for row, column in enumerate(assignment) if column >= 0)
        best = score if best is None else max(best, score)
    return best


def verify_large_labels(solver=None):
    # Summing large bonuses as floats hides the small, real assignment loss.
    # Decimal.from_float evaluates the exact values supplied to Blueprint.
    matrices = [
        [
            [199999999999999.97, -0.09, 99999999999999.92, 200000000000000.06],
            [-0.05, 200000000000000.06, 200000000000000.1, -0.05],
            [0.02, -0.05, -0.01, -0.06],
            [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97],
        ],
        [
            [100000000000000.02, 100000000000000.06, -0.06, 200000000000000.0],
            [100000000000000.0, 200000000000000.1, 199999999999999.9, 199999999999999.9],
            [99999999999999.92, -0.03, 0.0, 100000000000000.06],
            [100000000000000.02, 0.07, 0.1, 0.09],
        ],
    ]
    for fixture, matrix in enumerate(matrices):
        solver, assignment, _ = execute(matrix, [False] * 4, limit=1, solver=solver)
        assert solver.get_editor_property("Succeeded")

        def score(chosen):
            return sum((Decimal.from_float(matrix[row][column]) for row, column in enumerate(chosen)), Decimal(0))

        with localcontext() as context:
            context.prec = 80
            expected = max(score(chosen) for chosen in itertools.permutations(range(4)))
            actual = score(assignment)
        assert actual == expected, ("Large bonuses lost a small assignment improvement", fixture, assignment, str(expected - actual))
    return solver


def verify_zero_delta(solver=None):
    size = 80
    solver, assignment, work = execute([[0.0] * size for _ in range(size)], [False] * size, solver=solver)
    assert solver.get_editor_property("Succeeded") and sorted(assignment) == list(range(size))
    target = 2 * size * size + 60 * size
    assert work <= target, f"Zero-delta updates repeated identity operations: {work} primitive items > {target}"
    return solver


def verify_terminal_potentials(solver=None):
    size = 80
    matrix = [[-1.0 if column == (row + 17) % size else -100.0 for column in range(size)] for row in range(size)]
    solver, assignment, work = execute(matrix, [False] * size, solver=solver)
    assert solver.get_editor_property("Succeeded") and assignment == [(row + 17) % size for row in range(size)]
    assert list(solver.get_editor_property("U"))[1:] == [1.0] * size
    assert list(solver.get_editor_property("V"))[:size + 1] == [-float(size)] + [0.0] * size
    target = 2 * size * size + 60 * size
    assert work <= target, f"Final augmentations updated dead residual labels: {work} primitive items > {target}"
    return solver


def run():
    # Dense matching scans edges and residuals once per row; extra full-width
    # resets and forbidden dummy columns must not double that work.
    size = 80
    matrix = [[100.0 if column == (row + 17) % size else 1.0 for column in range(size)] for row in range(size)]
    solver, assignment, work = execute(matrix, [False] * size)
    assert solver.get_editor_property("Succeeded") and assignment == [(row + 17) % size for row in range(size)]
    target = 3 * size * size + 60 * size
    assert work <= target, f"Dense matching repeated avoidable width scans: {work} primitive items > {target}"
    solver = verify_large_labels(solver)
    solver = verify_zero_delta(solver)
    solver = verify_terminal_potentials(solver)

    rng = random.Random(80271)
    cases = 0
    for rows in range(1, 5):
        for columns in range(1, 5):
            for _ in range(8):
                matrix = [[rng.choice([-10.0, 0.0, 0.1, 0.125, 1.03, 1.5, 7.0]) for _ in range(columns)] for _ in range(rows)]
                mask = [rng.choice([False, True]) for _ in range(rows)]
                expected = optimum(matrix, mask)
                solver, assignment, _ = execute(matrix, mask, limit=1, solver=solver)
                assert bool(solver.get_editor_property("Succeeded")) == (expected is not None), (matrix, mask, assignment)
                if expected is None:
                    continue
                chosen = [column for column in assignment if column >= 0]
                assert len(chosen) == len(set(chosen))
                assert all(column >= 0 or mask[row] for row, column in enumerate(assignment))
                actual = sum(matrix[row][column] for row, column in enumerate(assignment) if column >= 0)
                assert abs(actual - expected) <= 0.000001, (matrix, mask, assignment, actual, expected)
                # The planner uses these duals to preserve higher-priority optima.
                u, v = list(solver.get_editor_property("U")), list(solver.get_editor_property("V"))
                for row in range(rows):
                    for column in range(columns):
                        reduced = -matrix[row][column] - u[row + 1] - v[column + 1]
                        assert reduced >= -0.000001, (matrix, assignment, row, column, reduced)
                        if assignment[row] == column:
                            assert abs(reduced) <= 0.000001, (matrix, assignment, reduced)
                cases += 1

    solver, assignment, _ = execute([[8.0, -1e20, 1.0], [-1e20, 7.0, 6.0], [3.0, 2.0, 9.0]], [False] * 3, solver=solver)
    assert solver.get_editor_property("Succeeded") and assignment == [0, 1, 2]
    solver, _, _ = execute([[1.0], [2.0], [3.0]], [False] * 3, solver=solver)
    assert not solver.get_editor_property("Succeeded"), "Not enough usable columns for mandatory rows"
    solver, assignment, _ = execute([[], []], [True, True], solver=solver)
    assert solver.get_editor_property("Succeeded") and assignment == [-1, -1]
    solver, _, _ = execute([[], []], [False, True], solver=solver)
    assert not solver.get_editor_property("Succeeded")
    unreal.log(f"WO_SOLVER_WORK_TESTS_PASS: dense80 work={work} target={target}; {cases} feasible oracle/dual cases, impossible masks, limit1 and reuse")


run()
