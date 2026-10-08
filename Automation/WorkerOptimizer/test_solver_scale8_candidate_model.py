"""Unwired scale-eight certificate experiment over actual emitted solver graphs.

Only local guard ASTs change. Scores, labels, potentials and arithmetic stay in
original units. No Unreal import, production edit, or planner opt-in is used.
"""

import argparse
from collections import Counter
import copy
import math
from pathlib import Path
import random

from benchmark_native_relaxation import equal
from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import projected_v
from test_solver_integer_minv_production_model import (
    Machine as BaseMachine, compare, label_projection, semantic_snapshot,
)
from test_solver_native_lifecycle_model import emitted
from test_solver_native_relaxation_model import check_structure
from test_solver_used_label_marker_model import initialize, reserve_matrix


MODE = 'ScaleEightCandidate'
LIMIT = float(2 ** 48)


def candidate_graphs(original, symbol):
    result = copy.deepcopy(original)
    replacements = Counter()
    guards = {}

    def get(name):
        return [symbol('Variables|Default|Get' + name)]

    def transform(value, graph):
        if not isinstance(value, list):
            return value
        for probe, check in (('IntegerUProbe', 'IntegerUCertified'),
                             ('IntegerMinProbe', 'IntegerMinCheck')):
            condition = [symbol('and'), [symbol('>='), get(probe), -float(2 ** 50)],
                         [symbol('<='), get(probe), float(2 ** 50)]]
            if len(value) == 3 and str(value[0]) == 'if' and value[1] == condition:
                setter = value[2]
                assert str(setter[0]) == 'Variables|Default|Set' + check
                assert str(setter[1][0]) == '==' and setter[1][1] == get(probe)
                floor = setter[1][2]
                assert str(floor[0]).endswith('|FloortoInteger64') and floor[2] == get(probe)
                scaled = [symbol('*'), get(probe), 8.0]
                guarded = [symbol('if'),
                    [symbol('and'), [symbol('>='), get(probe), -LIMIT],
                     [symbol('<='), get(probe), LIMIT]],
                    [setter[0], [symbol('=='), scaled, [floor[0], floor[1], scaled]]]]
                replacements[(graph, probe)] += 1
                guards[probe] = copy.deepcopy(value)
                return [symbol('if'), get(MODE), guarded, [symbol('else'), value]]
        return [transform(item, graph) for item in value]

    for name in result:
        result[name] = transform(result[name], name)
    assert sum(count for (_, probe), count in replacements.items() if probe == 'IntegerUProbe') == 1
    assert sum(count for (_, probe), count in replacements.items() if probe == 'IntegerMinProbe') >= 3

    def false_arm(value):
        if not isinstance(value, list):
            return value
        if len(value) == 4 and str(value[0]) == 'if' and value[1] == get(MODE):
            return value[3][1]
        return [false_arm(item) for item in value]

    assert {name: false_arm(value) for name, value in result.items()} == original, 'False arm changed original AST'
    result['IntegerUReset'][0].append([symbol('Variables|Default|Set' + MODE), False])
    check = [symbol('Variables|Default|SetIntegerMinCheck'), False]
    body = transform(guards['IntegerMinProbe'], 'ScaleEightCheckMin')
    result['ScaleEightCheckMin'] = [[symbol('fn'), symbol('ScaleEightCheckMin'), [], check, body]]
    check_structure(result)
    return result, replacements


class Machine(BaseMachine):
    def evaluate(self, form):
        if isinstance(form, list) and form and str(form[0]).endswith('|FloortoInteger64'):
            value = self.evaluate(form[2])
            assert math.isfinite(value) and abs(value) <= 2 ** 51
            return math.floor(value)
        return super().evaluate(form)

    def advance_checked(self, method='Advance'):
        before = self.state.get(MODE, False)
        super().advance_checked(method)
        assert self.state.get(MODE, False) is before, 'Mode changed during a solve'


def guard_cases(graphs, symbol, baseline=False):
    machine = Machine(graphs, symbol, 1)
    values = (-math.inf, math.nan, math.inf, -0.0, 0.0, .125, -.125, .375,
              .0625, .1, -.1, LIMIT, -LIMIT, LIMIT - .125, -LIMIT + .125,
              math.nextafter(LIMIT, math.inf), math.nextafter(-LIMIT, -math.inf),
              math.nextafter(LIMIT, 0.0), float(2 ** 49), float(2 ** 50), float(2 ** 50 + 1))
    count = 0
    for mode in (False, True):
        for value in values:
            expected = (math.isfinite(value) and abs(value) <= (LIMIT if mode else 2 ** 50)
                        and (value * (8.0 if mode else 1.0)).is_integer())
            machine.state[MODE] = mode
            machine.state['IntegerUProbe'] = value
            machine.invoke('IntegerUCheckValue')
            assert machine.state['IntegerUCertified'] is expected, ('U/V guard', mode, value, expected)
            if not baseline:
                machine.state['IntegerMinProbe'] = value
                machine.invoke('ScaleEightCheckMin')
                assert machine.state['IntegerMinCheck'] is expected, ('MinV guard', mode, value, expected)
            count += 1
    return count


def start(machine, matrix, prefix, enabled, mode, dummy=False, implicit=False, negative_zero=False):
    machine.audit.reset()
    machine.pending_seed = None
    initialize(machine, matrix, False, prefix, dummy, implicit)
    assert machine.state.get(MODE, False) is False, 'Initialize must reset the candidate mode'
    assert not machine.state['IntegerMinActive'] and not machine.state['IntegerUActive']
    machine.state.update(IntegerUEnabled=enabled, IntegerMinEnabled=enabled)
    machine.invoke('EnableNativeDeadLabels')
    machine.state[MODE] = mode
    if negative_zero:
        machine.state['U'] = [-0.0] * len(machine.state['U'])
        machine.state['V'] = [-0.0] * len(machine.state['V'])
    machine.eager_u = list(machine.state['U'])
    machine.eager_v = list(machine.state['V'])


def solve(machine, matrix, prefix, enabled, mode, dummy=False, implicit=False, cancel=False, negative_zero=False):
    start(machine, matrix, prefix, enabled, mode, dummy, implicit, negative_zero)
    while not machine.state['Done']:
        if cancel and (machine.state.get('IntegerMinEpoch', 0) or machine.state.get('IntegerUEpoch', 0)):
            machine.check_cancel()
        machine.advance_checked()
        assert machine.stats['work'] < 1000000
    assert not machine.state['IntegerMinActive']
    assert equal(machine.state['U'], machine.eager_u) and equal(machine.state['V'], machine.eager_v)
    return copy.deepcopy(machine.state), copy.deepcopy(machine.events), dict(machine.stats)


def false_arm_calls(original, candidate, symbol):
    count = 0
    matrix = [[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]]
    for limit in (1, 3, 64):
        pair = [Machine(graphs, symbol, limit) for graphs in (original, candidate)]
        for machine in pair:
            start(machine, matrix, 2, True, False, negative_zero=True)
        while not pair[0].state['Done']:
            for machine in pair:
                machine.advance_checked()
            names = (pair[0].state.keys() | pair[1].state.keys()) - {MODE}
            assert all(equal(pair[0].state.get(name, 0), pair[1].state.get(name, 0)) for name in names), 'Default-off state changed'
            count += 1
    return count


def fractional_matrix(size):
    rows, cols = size + 3, size + size // 2
    quality = [0.0] * size
    for row in range(size):
        quality[(row + 17) % size] = float(10000 + row if row % 2 == 0 else row // 2 + 1) + .125
    maximum = max(100.125, max(quality))
    capacity = rows + 1
    fill = (((maximum * 5.0) + 1.0) * capacity) + 1.0
    coverage = (((fill + (maximum * 5.0)) + 1.0) * capacity) + 1.0
    bonus = ((((coverage + fill) + (maximum * 5.0)) + 1.0) * capacity) + 1.0
    matrix = []
    for row in range(rows):
        values = [-1e20] * cols
        for worker in range(size):
            value = (100.125 if worker == (row + 17) % size else 10.125) + fill if row < size else 0.0
            if row >= size or row % 2 == 0:
                value = value + coverage
            values[worker] = value
        if row < size and row % 2:
            values[size + row // 2] = 0.0
        matrix.append(values)
    return matrix, quality, coverage, bonus


def pending_phases(graphs, symbol, seed, limit):
    assert seed is not None, 'No genuine fractional pending MinV phase'
    changes = ({}, {'Delta': 0.0}, {'Delta': -0.0}, {'Delta': .125}, {'Delta': -.125},
               {'Delta': .1}, {'Delta': .0625}, {'Delta': math.nextafter(LIMIT, math.inf)},
               {'Delta': LIMIT}, {'Delta': -LIMIT}, {'FirstFreeColumn': 1},
               {'IntegerMinRawUpper': seed['IntegerMinDummyBound']})
    results_count = cancel_count = 0
    for changed in changes:
        results = []
        for enabled in (False, True):
            machine = Machine(graphs, symbol, limit)
            machine.state = copy.deepcopy(seed)
            machine.state.update(changed)
            labels = label_projection(machine.state)
            u, v = projected_u(machine.state), projected_v(machine.state)
            if not enabled:
                machine.state.update(U=u, V=v, MinV=labels, IntegerUEnabled=False, IntegerUActive=False,
                    IntegerUPhasePrepared=False, IntegerUFlushMode=0, IntegerMinEnabled=False,
                    IntegerMinActive=False, IntegerMinGathering=False, IntegerMinFlushCursor=0)
            machine.eager_u, machine.eager_v = list(u), list(v)
            machine.audit.label_epoch = machine.state['ActiveRow']
            machine.audit.label_shadow = list(labels)
            while machine.state['SolverState'] == 6:
                machine.check_cancel()
                machine.advance_checked()
                assert machine.stats['calls'] < 1000
            if enabled and (changed.get('Delta') in (.1, .0625, math.nextafter(LIMIT, math.inf))
                            or 'FirstFreeColumn' in changed or 'IntegerMinRawUpper' in changed):
                assert not machine.state['IntegerMinActive'], ('Guard did not flush', changed)
            results.append(semantic_snapshot(machine.state, label_projection(machine.state), True))
            cancel_count += len(machine.cancel_states)
        assert equal(results[0], results[1]), ('Pending scale-eight phase', limit, changed, results)
        results_count += 1
    return results_count, cancel_count


def run(baseline=False, random_cases=16):
    original, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    if baseline:
        guard_cases(original, symbol, True)
        raise AssertionError('Expected missing scale-eight guard RED')
    graphs, replacements = candidate_graphs(original, symbol)
    guards = guard_cases(graphs, symbol)
    default_calls = false_arm_calls(original, graphs, symbol)
    matrices = [
        [[10.125, 9.125, 0.], [10.125, 8.125, 0.], [10.125, 7.125, 0.]],
        [[-0.0, 0.0], [0.0, -0.0]], [[math.nan, 0.]], [[math.inf, 0.]], [[-math.inf, 0.]],
        [[LIMIT, LIMIT - .125, 0.], [-LIMIT, .125, 0.]],
        [[float(2 ** 49), .125, 0.], [float(2 ** 49) - .125, .1, 0.]],
        [[math.nextafter(LIMIT, math.inf), .0625], [.1, -0.0]],
    ]
    rng = random.Random(800148)
    for _ in range(random_cases):
        rows, cols = rng.randint(1, 5), rng.randint(1, 7)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., .125, .375, .0625, .1,
                                     7., LIMIT, LIMIT - .125, float(2 ** 49)])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = calls = phases = cancellations = 0
    work_pairs = []
    for limit in (1, 3, 64):
        old, new = Machine(graphs, symbol, limit), Machine(graphs, symbol, limit)
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                for mode in (False, True):
                    expected = solve(old, matrix, prefix, False, False, dummy, negative_zero=index % 3 == 0)
                    actual = solve(new, matrix, prefix, True, mode, dummy, cancel=True, negative_zero=index % 3 == 0)
                    try:
                        compare(actual, expected)
                    except AssertionError as error:
                        raise AssertionError(('matrix case', limit, dummy, index, mode, matrix, error.args)) from error
                    comparisons += 1
                    calls += actual[2]['calls']
        for size in (6, 12, 24):
            matrix, quality, coverage, bonus = fractional_matrix(size)
            first = solve(old, matrix, size, False, False, implicit=True)
            actual = solve(new, matrix, size, True, True, implicit=True, cancel=True)
            compare(actual, first)
            later = reserve_matrix(matrix, first[0]['U'], first[0]['V'], size, quality, coverage, bonus)
            expected = solve(old, later, size, False, False)
            actual = solve(new, later, size, True, True, cancel=True)
            compare(actual, expected)
            chosen = actual[0]['Assignment'][:size]
            idle = set(range(size)) - {worker for worker in chosen if 0 <= worker < size}
            assert len(idle) == 3
            assert sum(quality[j] for j in idle) == sum(sorted(quality[(r + 17) % size] for r in range(1, size, 2))[-3:])
            assert all(worker == (row + 17) % size for row, worker in enumerate(chosen) if 0 <= worker < size)
            work_pairs.append((size, limit, expected[2]['work'], actual[2]['work']))
            comparisons += 2
            calls += actual[2]['calls']
            if size == 24:
                count, stopped = pending_phases(graphs, symbol, new.pending_seed, limit)
                phases += count
                cancellations += stopped
        cancellations += len(new.cancel_states)
    assert cancellations and phases == 36
    print('WO_SCALE8_CANDIDATE_MODEL_PASS', {
        'comparisons': comparisons, 'calls': calls, 'guard_cases': guards,
        'default_off_exact_calls': default_calls, 'pending_phases': phases,
        'cancel_states': cancellations, 'work_pairs': work_pairs,
        'guard_sites': {str(key): value for key, value in replacements.items()},
        'production_wired': False,
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--random-cases', type=int, default=16)
    args = parser.parse_args()
    run(args.baseline, args.random_cases)
