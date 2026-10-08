"""Compiled production marker opt-in against the unchanged default solver."""

import math
import random

import unreal

from test_solver_used_label_marker import (bits, fixture_class, create_instance,
    initialize, result, solve)
from test_solver_used_label_marker_model import reserve_matrix


def run():
    cls = fixture_class(production=True)
    baseline, candidate = create_instance(cls), create_instance(cls)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
        [[math.nan, 0.0]], [[math.inf, 0.0]], [[-math.inf, 0.0]],
        [[-0.0, 0.0, 0.0], [0.0, -0.0, 0.0]],
        [[199999999999999.97, -.09, 99999999999999.92, 200000000000000.06],
         [-.05, 200000000000000.06, 200000000000000.1, -.05],
         [.02, -.05, -.01, -.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]]]
    rng = random.Random(918523)
    for _ in range(40):
        rows, cols = rng.randint(1, 6), rng.randint(1, 9)
        matrices.append([[rng.choice([-1e20, -.09, -0.0, 0.0, .125, 1.03, 7., 1e14+.06])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = removed_masks = 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected = solve(baseline, matrix, False, limit, prefix, dummy)
                actual = solve(candidate, matrix, True, limit, prefix, dummy)
                assert expected[:2] == actual[:2], (limit, dummy, index, 'production result/trace')
                assert actual[3] == 0
                assert not baseline.get_editor_property('NativeDeadLabels')
                assert math.isinf(candidate.get_editor_property('NativeDeadInfinity'))
                comparisons += 1
                removed_masks += expected[3]
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix, quality, coverage, bonus = benchmark_matrices(size)
            expected = solve(baseline, matrix, False, limit, size, implicit=True)
            actual = solve(candidate, matrix, True, limit, size, implicit=True)
            assert expected[:2] == actual[:2] and actual[3] == 0
            removed_masks += expected[3]
            later = reserve_matrix(matrix, list(baseline.get_editor_property('U')),
                list(baseline.get_editor_property('V')), size, quality, coverage, bonus)
            expected = solve(baseline, later, False, limit, size)
            actual = solve(candidate, later, True, limit, size)
            assert expected[:2] == actual[:2] and actual[3] == 0
            removed_masks += expected[3]
            comparisons += 2
    # Inspect direct production marking, including zero and normalized prefixes.
    visits = cancellations = 0
    for prefix in (0, 1, 2, 3, 4):
        initialize(candidate, matrices[0], True, 1, prefix)
        while not candidate.get_editor_property('Done'):
            candidate.call_method('Advance')
            state = candidate.get_editor_property('SolverState')
            if state in (5, 6, 11):
                columns = list(candidate.get_editor_property('UsedColumns'))
                labels = list(candidate.get_editor_property('MinV'))
                width = candidate.get_editor_property('NativeDeadPrefixWidth')
                assert width == (prefix if 0 < prefix <= 3 else 0)
                assert all(math.isinf(labels[j]) and labels[j] > 0 for j in columns)
                assert candidate.get_editor_property('NativeDeadPrefixUsed') == sum(j <= width for j in columns)
                visits += 1
    for phase in (0, 1, 4, 5):
        initialize(candidate, matrices[0], True, 1, 2)
        while not candidate.get_editor_property('Done'):
            if candidate.get_editor_property('SolverState') == 11 and candidate.get_editor_property('NativePhase') == phase:
                break
            candidate.call_method('Advance')
        assert not candidate.get_editor_property('Done'), ('missing cancel phase', phase)
        candidate.call_method('StopMarker')
        before = result(candidate), [bits(v) for v in candidate.get_editor_property('MinV')]
        candidate.call_method('Advance')
        assert before == (result(candidate), [bits(v) for v in candidate.get_editor_property('MinV')])
        assert candidate.get_editor_property('LastStepWork') == 0
        cancellations += 1
    # Reset a previously marked object to the public default, including Infinity.
    candidate.call_method('Initialize', args=([1.0], 1, 1))
    assert not candidate.get_editor_property('NativeDeadLabels')
    assert candidate.get_editor_property('NativeDeadInfinity') == 0.0
    assert candidate.get_editor_property('NativeDeadPrefixUsed') == 0
    assert comparisons == 294 and removed_masks > 0 and visits > 0
    unreal.log(f'WO_DEAD_LABELS_TESTS_PASS comparisons={comparisons} removed_masks={removed_masks} '
               f'marker_checks={visits} cancellations={cancellations}')


if __name__ == '__main__':
    run()
