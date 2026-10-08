"""Offline experiment: enumerate reserve rows first without changing row IDs."""

from decimal import Decimal, localcontext
import hashlib
import itertools
import json

from test_solver_cached_trace import benchmark_matrices, solve


def exact_score(matrix, assignment):
    with localcontext() as context:
        context.prec = 100
        return sum((Decimal.from_float(matrix[row][column])
                    for row, column in enumerate(assignment)), Decimal(0))


def reserve_matrix(matrix, first, size, quality, coverage, column_bonus):
    required = [value < -0.00001 for value in first["v"][1:len(matrix[0]) + 1]]
    result, retained = [], 0
    for row, scores in enumerate(matrix):
        output = []
        for column, score in enumerate(scores):
            reduced = ((0.0 - score) - first["u"][row + 1]) - first["v"][column + 1]
            if score >= 0.0 and -0.00001 <= reduced <= 0.00001:
                retained += 1
                value = quality[column] if row >= size and column < size else 0.0
                if column < size and (row >= size or row % 2 == 0):
                    value = value + coverage
                if required[column]:
                    value = value + column_bonus
                output.append(value)
            else:
                output.append(-1e20)
        result.append(output)
    return result, retained


def objective(result, size, quality):
    productive = [worker if worker < size else -1 for worker in result["assignment"][:size]]
    chosen = {worker for worker in productive if worker >= 0}
    assert len(chosen) == sum(worker >= 0 for worker in productive) == size - 3
    assert all(productive[row] >= 0 for row in range(0, size, 2))
    assert all(worker == (row + 17) % size for row, worker in enumerate(productive) if worker >= 0)
    builder = sum(quality[worker] for worker in set(range(size)) - chosen)
    expected = sum(sorted(quality[(row + 17) % size] for row in range(1, size, 2))[-3:])
    assert builder == expected, (builder, expected)
    return dict(coverage=size // 2, count=len(chosen), quality=100.0 * len(chosen), builder=builder,
                assignment_sha256=hashlib.sha256(json.dumps(productive).encode("ascii")).hexdigest())


def trace(size=1000):
    matrix, quality, coverage, column_bonus = benchmark_matrices(size)
    order = list(range(size, len(matrix))) + list(range(size))
    reference_first = solve(matrix, False)
    candidate_first = solve(matrix, False, row_order=order)
    assert exact_score(matrix, reference_first["assignment"]) == exact_score(matrix, candidate_first["assignment"])
    reports = {}
    for name, first, second_order in (
            ("reference", reference_first, None),
            ("reserve_first_both", candidate_first, order),
            ("reserve_first_second_only", reference_first, order),
            ("reserve_first_first_only", candidate_first, None)):
        second_matrix, retained = reserve_matrix(matrix, first, size, quality, coverage, column_bonus)
        second = solve(second_matrix, False, row_order=second_order)
        assert all(second_matrix[row][column] >= 0.0 for row, column in enumerate(second["assignment"]))
        reports[name] = dict(first=first["counts"], second=second["counts"], retained_edges=retained,
                             first_score=str(exact_score(matrix, first["assignment"])),
                             second_score=str(exact_score(second_matrix, second["assignment"])),
                             objective=objective(second, size, quality))
    print("WO_SOLVER_ROW_ORDER_TRACE " + json.dumps(reports, sort_keys=True), flush=True)
    return reports


def numeric_orders():
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
    reports = []
    for fixture, matrix in enumerate(matrices):
        optimum = max(exact_score(matrix, assignment) for assignment in itertools.permutations(range(4)))
        baseline = solve(matrix, False)
        assert exact_score(matrix, baseline["assignment"]) == optimum
        failures = []
        for order in itertools.permutations(range(4)):
            result = solve(matrix, False, row_order=order)
            value = exact_score(matrix, result["assignment"])
            if value != optimum:
                failures.append(dict(order=order, assignment=result["assignment"], loss=str(optimum - value)))
        reports.append(dict(fixture=fixture, reference=baseline["assignment"], optimum=str(optimum),
                            failures=failures))
    print("WO_SOLVER_ROW_ORDER_NUMERIC " + json.dumps(reports, sort_keys=True), flush=True)
    return reports


if __name__ == "__main__":
    numeric_orders()
    trace()
