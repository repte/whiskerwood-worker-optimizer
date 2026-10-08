"""Actual production graphs: integer-U composed with dead labels and upper bounds."""

import copy
import math
from pathlib import Path
import random

from benchmark_native_relaxation import equal
from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import projected_v
from test_solver_integer_u_model import IntegerMachine
from test_solver_native_lifecycle_model import emitted
from test_solver_used_label_marker_model import initialize, reserve_matrix


class Machine(IntegerMachine):
    def evaluate(self, form):
        if isinstance(form, list) and form and str(form[0]).endswith('|Loge'):
            value = self.evaluate(form[2])
            return -math.inf if value == 0.0 else math.log(value)
        return super().evaluate(form)


def solve(machine, matrix, enabled, prefix, dummy=False, implicit=False):
    machine.eager_u = None
    machine.eager_v = None
    initialize(machine, matrix, False, prefix, dummy, implicit)
    assert not machine.state['IntegerUEnabled'] and not machine.state['IntegerUOffsets']
    machine.state['IntegerUEnabled'] = enabled
    if enabled:
        machine.invoke('EnableNativeDeadLabels')
    machine.eager_u = list(machine.state['U'])
    machine.eager_v = list(machine.state['V'])
    trace, epoch = [], 0
    calls = flushes = 0
    while not machine.state['Done']:
        before, row, j0 = (machine.state.get(k, 0) for k in ('SolverState', 'ActiveRow', 'J0'))
        flushes += machine.state['IntegerUFlushMode'] != 0
        machine.advance_checked('Advance')
        if before != 6 and machine.state['SolverState'] == 6:
            if before == 5 and j0 == 0:
                epoch = row
            live = ([(j, value) for j, value in enumerate(machine.state['MinV'][:machine.state['Width'] + 1])
                     if not machine.state['Used'][j]] if epoch == machine.state['ActiveRow'] else [])
            trace.append([*[machine.state[k] for k in ('ActiveRow', 'I0', 'J0', 'J1', 'Delta')], live])
        calls += 1
        assert calls < 100000
    assert equal(machine.state['U'], machine.eager_u)
    assert equal(machine.state['V'], machine.eager_v)
    return copy.deepcopy(machine.state), trace, calls, flushes


def compare(actual, expected):
    for name in ('Assignment', 'Succeeded', 'P', 'Way', 'U', 'V', 'Cur', 'Delta'):
        assert equal(actual[0].get(name, 0), expected[0].get(name, 0)), (name, actual, expected)
    assert equal(actual[1], expected[1]), ('selection/live-label trace', actual, expected)


def run(defer_v=True):
    graphs, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
                [[-0.0, 0.], [0., -0.0]], [[math.nan, 0.]], [[math.inf, 0.]],
                [[float(2**49) + .125, 1.], [float(2**49) - .125, 0.]]]
    rng = random.Random(57892)
    for _ in range(40):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = calls = flushes = 0
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        old, new = Machine(graphs, symbol, limit), Machine(graphs, symbol, limit, defer_v)
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected = solve(old, matrix, False, prefix, dummy)
                actual = solve(new, matrix, True, prefix, dummy)
                compare(actual, expected)
                comparisons += 1
                calls += actual[2]
                flushes += actual[3]
        for size in (6, 12, 24):
            matrix, quality, coverage, bonus = benchmark_matrices(size)
            expected = solve(old, matrix, False, size, implicit=True)
            actual = solve(new, matrix, True, size, implicit=True)
            compare(actual, expected)
            later = reserve_matrix(matrix, expected[0]['U'], expected[0]['V'], size, quality, coverage, bonus)
            expected = solve(old, later, False, size)
            actual = solve(new, later, True, size)
            compare(actual, expected)
            comparisons += 2
            calls += actual[2]
            flushes += actual[3]
    assert comparisons == 288 and flushes > 0
    print('WO_INTEGER_U_PRODUCTION_MODEL_PASS', comparisons, 'combined cases', calls, 'calls', flushes, 'flush calls')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--defer-v', action=argparse.BooleanOptionalAction, default=True,
                        help='Check current UV production; --no-defer-v is for historical U-only graphs.')
    run(parser.parse_args().defer_v)
