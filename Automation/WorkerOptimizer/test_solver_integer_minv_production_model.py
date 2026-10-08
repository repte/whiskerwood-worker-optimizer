"""Execute emitted Integer-MinV graphs against the unchanged eager solver path.

The oracle observes actual selection/potential boundaries, not a second lazy
implementation. Its per-call label shadow applies the original subtraction to
the logical cursor interval, including intervals completed by a certified jump.
"""

import copy
from collections import Counter
import math
from pathlib import Path
import random
import struct

from benchmark_native_relaxation import equal
from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import projected_v
from solver_integer_v_prototype import advance_shadows
from test_solver_integer_u_production_model import Machine as IntegerMachine
from test_solver_native_lifecycle_model import emitted
from test_solver_used_label_marker_model import initialize, reserve_matrix


def float_bits(value):
    return struct.pack('>d', value)


def label_projection(state):
    """Decode only live, not-yet-materialized real labels using exact integers."""
    values = list(state.get('MinV', []))
    if not state.get('IntegerMinActive'):
        return values
    for j in range(1, state['IntegerMinPrefix'] + 1):
        if state['Used'][j] or (state['IntegerMinFlushCursor'] and j < state['IntegerMinFlushCursor']):
            continue
        value = values[j] - state['IntegerMinOffset']
        if value == 0.0:
            value = state['IntegerMinZero'][j] if state['IntegerMinBirth'][j] == state['IntegerMinEpoch'] else 0.0
        values[j] = value
    return values


SNAPSHOT_FIELDS = (
    'StepWorkLimit', 'LastStepWork', 'Done', 'Succeeded', 'SolverState', 'Cursor',
    'Rows', 'Cols', 'Width', 'ActiveRow', 'I0', 'J0', 'J1', 'Delta', 'Cur',
    'FirstFreeColumn', 'NonpositiveV', 'DummyCount', 'ImplicitWorkerCount',
    'Assignment', 'P', 'Way', 'U', 'V', 'MinV', 'Used', 'UsedColumns',
    'NativeValue', 'NativeFreeMinimum', 'NativeFreeColumn', 'NativeFreeValid', 'NativeFreeRow',
    'NativeUsedRealOnly', 'NativeDummyBoundReady', 'NativeDummyBound', 'NativeDummyBoundRow',
    'PotentialFreeFixedColumn', 'PotentialEnd', 'PotentialLoopEnd',
    'NativePhase', 'NativePlannerTrusted', 'NativeDeadLabels', 'NativeDeadPrefixWidth', 'NativeDeadPrefixUsed',
    'IntegerUEnabled', 'IntegerUActive', 'IntegerUTotal', 'IntegerUEpoch',
    'IntegerUOffsets', 'IntegerUEpochs', 'IntegerUPhasePrepared',
    'IntegerUPhaseNonzero', 'IntegerUPhaseTerminal', 'IntegerUFlushMode',
    'IntegerUFlushCursor', 'IntegerURowPrepared',
    'IntegerMinEnabled', 'IntegerMinActive', 'IntegerMinGathering', 'IntegerMinCertified',
    'IntegerMinOffset', 'IntegerMinEpoch', 'IntegerMinBirth', 'IntegerMinZero',
    'IntegerMinPrefix', 'IntegerMinRawUpper', 'IntegerMinDummyBound', 'IntegerMinLastLive',
    'IntegerMinFlushCursor', 'IntegerMinPhasePrepared', 'IntegerMinProposedOffset',
    'IntegerMinValue', 'IntegerMinProbe', 'IntegerMinRawMinimum', 'IntegerMinFlushEnd',
    'IntegerMinIndex', 'IntegerMinCheck', 'IntegerMinProposedDummyBound', 'IntegerMinCount', 'IntegerMinDummyCount',
)


def snapshot(state):
    """Avoid copying immutable score matrices on every bounded solver call."""
    return {name: copy.deepcopy(state[name]) for name in SNAPSHOT_FIELDS if name in state}


def live_labels(state, labels):
    return [(j, labels[j]) for j in range(1, state['Width'] + 1) if not state['Used'][j]]


def semantic_snapshot(state, labels, valid_labels):
    result = {name: copy.deepcopy(state.get(name, 0)) for name in (
        'ActiveRow', 'I0', 'J0', 'J1', 'Delta', 'Cur', 'P', 'Way',
        'NativeValue', 'NativeFreeMinimum', 'NativeFreeColumn', 'NativeFreeValid')}
    result.update(U=projected_u(state), V=projected_v(state),
                  MinV=live_labels(state, labels) if valid_labels else [])
    return result


class LabelAudit:
    """Shared independent transition oracle for the model and actual VM tests."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.label_shadow = None
        self.label_epoch = 0
        self.phase_key = None
        self.events = []
        self.stats = Counter()

    def observe(self, before, after):
        self.stats['calls'] += 1
        self.stats['work'] += after['LastStepWork']
        assert 0 < after['LastStepWork'] <= after['StepWorkLimit'], 'Unbounded helper work'
        if before['SolverState'] == 6:
            self._potential_shadow(before, after)
        if before['SolverState'] != 6 and after['SolverState'] == 6:
            if before['SolverState'] == 5 and before.get('J0') == 0:
                self.label_epoch = after['ActiveRow']
            labels = label_projection(after)
            self.label_shadow = list(labels)
            self.phase_key = (after['ActiveRow'], after['J0'], after['J1'], float_bits(after['Delta']))
            self.events.append(('select', semantic_snapshot(after, labels, self.label_epoch == after['ActiveRow'])))
        if before['SolverState'] == 6 and after['SolverState'] in (4, 7):
            self.events.append(('potential', semantic_snapshot(
                after, label_projection(after), self.label_epoch == after['ActiveRow'])))

    def _potential_shadow(self, before, after):
        if self.label_shadow is None or self.label_epoch != before['ActiveRow']:
            return
        terminal = before['P'][before['J1']] == 0
        if not terminal and before['Delta'] != 0.0:
            assert after['Cursor'] >= before['Cursor'], ('Potential cursor regressed', before, after)
            expected_value = before.get('NativeValue', 0.0)
            for j in range(before['Cursor'], min(after['Cursor'], before['Width'] + 1)):
                if not before['Used'][j]:
                    self.label_shadow[j] = self.label_shadow[j] - before['Delta']
                    expected_value = self.label_shadow[j]
            if before.get('NativePlannerTrusted') and before['DummyCount'] == 0 and before['Width'] == before['Cols']:
                assert equal(after.get('NativeValue', 0.0), expected_value), (
                    'Per-call NativeValue bits', self.phase_key, before['Cursor'], after['Cursor'],
                    after.get('NativeValue', 0.0), expected_value)
        actual = label_projection(after)
        for j in range(1, before['Width'] + 1):
            if not before['Used'][j]:
                assert equal(actual[j], self.label_shadow[j]), (
                    'Per-call projected label bits', self.phase_key, j,
                    before['Cursor'], after['Cursor'], actual[j], self.label_shadow[j])


class Machine(IntegerMachine):
    def __init__(self, graphs, symbol, limit):
        super().__init__(graphs, symbol, limit, True)
        self.audit = LabelAudit()
        self.cancel_states = set()
        self.pending_seed = None

    @property
    def events(self):
        return self.audit.events

    @property
    def stats(self):
        return self.audit.stats

    def advance_checked(self, method='Advance'):
        state = self.state
        if (self.pending_seed is None and state['SolverState'] == 6 and state['Cursor'] == 0
                and state.get('IntegerMinActive') and state.get('IntegerMinEpoch', 0) > 0
                and state['P'][state['J1']] != 0 and not state.get('IntegerUPhasePrepared')
                and state.get('IntegerUFlushMode', 0) == 0):
            self.pending_seed = copy.deepcopy(state)
        before = snapshot(self.state)
        self.invoke(method)
        advance_shadows(before, self.state, self.eager_u, self.eager_v)
        assert equal(projected_u(self.state), self.eager_u), ('Per-call projected U', before, self.state)
        assert equal(projected_v(self.state), self.eager_v), ('Per-call projected V', before, self.state)
        self.audit.observe(before, self.state)

    def check_cancel(self):
        state = self.state
        key = (state['SolverState'], state.get('NativePhase', 0),
               bool(state.get('IntegerMinFlushCursor', 0)), state.get('IntegerUFlushMode', 0))
        if key in self.cancel_states:
            return
        cancelled = copy.deepcopy(self)
        cancelled.state['Done'] = True
        before = copy.deepcopy(cancelled.state)
        labels = label_projection(before)
        cancelled.invoke('Advance')
        before['LastStepWork'] = 0
        assert equal(cancelled.state, before), ('Cancellation mutated private/public state', key)
        assert equal(label_projection(cancelled.state), labels)
        self.cancel_states.add(key)


def solve(machine, matrix, prefix, enabled, implicit=False, dummy=False, cancel=False):
    machine.eager_u = machine.eager_v = None
    machine.audit.reset()
    machine.pending_seed = None
    initialize(machine, matrix, False, prefix, dummy, implicit)
    assert machine.state.get('IntegerMinEnabled') is False, 'Integer-MinV is absent or enabled by initialization'
    assert not machine.state.get('IntegerMinActive') and not machine.state.get('IntegerMinGathering')
    assert not machine.state.get('IntegerMinCertified') and not machine.state.get('IntegerMinFlushCursor', 0)
    assert machine.state.get('IntegerMinOffset', 0) == 0 and machine.state.get('IntegerMinEpoch', 0) == 0
    machine.state['IntegerUEnabled'] = True
    machine.invoke('EnableNativeDeadLabels')
    machine.state['IntegerMinEnabled'] = enabled
    machine.eager_u = list(machine.state['U'])
    machine.eager_v = list(machine.state['V'])
    while not machine.state['Done']:
        if cancel:
            machine.check_cancel()
        machine.advance_checked()
        assert machine.stats['work'] < 10000000, ('No bounded completion', machine.state)
    assert not machine.state.get('IntegerMinActive'), 'Completion must flush the representation'
    assert equal(machine.state['U'], machine.eager_u)
    assert equal(machine.state['V'], machine.eager_v)
    return copy.deepcopy(machine.state), copy.deepcopy(machine.events), dict(machine.stats)


def compare(actual, expected):
    for name in ('Assignment', 'Succeeded', 'P', 'Way', 'U', 'V', 'MinV', 'Cur', 'Delta', 'J1'):
        assert equal(actual[0].get(name, 0), expected[0].get(name, 0)), (
            name, actual[0].get(name), expected[0].get(name))
    assert len(actual[1]) == len(expected[1]), ('Boundary count', len(actual[1]), len(expected[1]))
    for index, (left, right) in enumerate(zip(actual[1], expected[1])):
        assert left[0] == right[0]
        for name in left[1]:
            assert equal(left[1][name], right[1][name]), (
                'Exact semantic boundary', index, left[0], name, left[1][name], right[1][name])


def special_phases(graphs, symbol, seed, limit):
    """Flush/fallback must retain the eager phase, not merely its final assignment."""
    assert seed is not None, 'No real pending-offset phase was exercised'
    changes = ({}, {'Delta': 0.0}, {'Delta': -0.0}, {'Delta': .125},
               {'Delta': -.125}, {'Delta': float(2**50 + 1)},
               {'FirstFreeColumn': 1}, {'IntegerMinRawUpper': seed['IntegerMinDummyBound']})
    cases = calls = 0
    for changed in changes:
        pair = []
        for enabled in (False, True):
            machine = Machine(graphs, symbol, limit)
            machine.state = copy.deepcopy(seed)
            machine.state.update(changed)
            original = label_projection(machine.state)
            if not enabled:
                machine.state.update(IntegerMinEnabled=False, IntegerMinActive=False,
                    IntegerMinGathering=False, IntegerMinCertified=False,
                    IntegerMinOffset=0.0, IntegerMinEpoch=0, IntegerMinFlushCursor=0,
                    IntegerMinPhasePrepared=False, MinV=list(original))
            machine.eager_u = projected_u(machine.state)
            machine.eager_v = projected_v(machine.state)
            machine.audit.label_epoch = machine.state['ActiveRow']
            machine.audit.label_shadow = list(original)
            machine.audit.phase_key = (machine.state['ActiveRow'], machine.state['J0'],
                                       machine.state['J1'], float_bits(machine.state['Delta']))
            while machine.state['SolverState'] == 6:
                machine.check_cancel()
                machine.advance_checked()
                calls += 1
                assert calls < 100000
            if enabled and (changed.get('Delta', 0.0) in (.125, -.125, float(2**50 + 1))
                            or 'FirstFreeColumn' in changed or 'IntegerMinRawUpper' in changed):
                assert not machine.state['IntegerMinActive'], ('Seeded guard must flush', changed)
            pair.append(semantic_snapshot(machine.state, label_projection(machine.state), True))
        assert equal(pair[0], pair[1]), ('Seeded phase/fallback', limit, changed, pair)
        cases += 1
    return cases, calls


def gather_gate_run():
    """Remove only the new gate to retain the exact former gathering path."""
    graphs, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    old = copy.deepcopy(graphs)
    replaced = 0

    def without_gate(value):
        nonlocal replaced
        if not isinstance(value, list):
            return value
        if (len(value) == 3 and str(value[0]) == '>'
                and value[1] == [symbol('Variables|Default|GetFirstFreeColumn')]
                and value[2] == [symbol('Variables|Default|GetImplicitWorkerCount')]):
            replaced += 1
            return True
        return [without_gate(item) for item in value]

    old['AdvanceRelaxation'] = without_gate(old['AdvanceRelaxation'])
    matrix = [[10., 9., 8., 0.], [10., 8., 7., 0.], [10., 7., 6., 0.]]
    pairs = []
    for limit in (1, 3, 64):
        reference, actual = Machine(old, symbol, limit), Machine(graphs, symbol, limit)
        expected = solve(reference, matrix, 3, True, cancel=True)
        result = solve(actual, matrix, 3, True, cancel=True)
        compare(result, expected)
        old_writes = reference.counts['writes_IntegerMinBirth'] + reference.counts['writes_IntegerMinZero']
        new_writes = actual.counts['writes_IntegerMinBirth'] + actual.counts['writes_IntegerMinZero']
        pairs.append((limit, old_writes, new_writes, expected[2]['work'], result[2]['work']))
    assert all(old_count > 0 and new_count == 0 and new_work < old_work
               for _, old_count, new_count, old_work, new_work in pairs), (
        'Free real columns still trigger unusable MinV gathering', pairs)
    assert replaced == 1, ('Exactly the new AdvanceRelaxation gate', replaced)

    from solver_integer_minv_dsl import begin_scan
    from test_solver_native_relaxation_model import parser
    parse, _ = parser()
    get = lambda name: f'(Variables|Default|Get{name})'
    put = lambda name, value: f'(Variables|Default|Set{name} {value})'
    for first_free, enabled in ((1, False), (3, False), (4, True)):
        machine = Machine(graphs, symbol, 1)
        machine.state.update(IntegerMinEnabled=True, Cursor=1, IntegerMinActive=False,
            IntegerMinGathering=True, IntegerUActive=True, NativeDeadLabels=True,
            NativePlannerTrusted=True, NativeUsedRealOnly=True, DummyCount=0, Width=4,
            Cols=4, ImplicitWorkerCount=3, FirstFreeColumn=first_free,
            IntegerMinBirth=[], IntegerMinZero=[])
        for form in parse(begin_scan(get, put)):
            machine.evaluate(form)
        assert machine.state['IntegerMinGathering'] is enabled, (
            'Stale gathering cleanup and strict gate', first_free, machine.state)
    print('WO_INTEGER_MINV_GATHER_GATE_MODEL_PASS', pairs, 'stale_cleanup=3')


def run(size=24, random_cases=30, limits=(1, 3, 64)):
    graphs, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    matrices = [
        [[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
        [[-0.0, 0.0], [0.0, -0.0]],
        [[math.nan, 0.0]], [[math.inf, 0.0]], [[-math.inf, 0.0]],
        [[float(2**50), .125, -1e20], [float(2**50 + 1), -0.0, 0.]],
        [[199999999999999.97, -.09, 99999999999999.92, 200000000000000.06],
         [-.05, 200000000000000.06, 200000000000000.1, -.05],
         [.02, -.05, -.01, -.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]],
    ]
    rng = random.Random(725801)
    for _ in range(random_cases):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    from test_solver_cached_trace import benchmark_matrices
    comparisons = phase_cases = phase_calls = 0
    work_pairs = []
    for limit in limits:
        old, new = Machine(graphs, symbol, limit), Machine(graphs, symbol, limit)
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected = solve(old, matrix, prefix, False, dummy=dummy)
                actual = solve(new, matrix, prefix, True, dummy=dummy, cancel=True)
                compare(actual, expected)
                comparisons += 1
        matrix, quality, coverage, bonus = benchmark_matrices(size)
        first = solve(old, matrix, size, False, implicit=True)
        actual = solve(new, matrix, size, True, implicit=True, cancel=True)
        compare(actual, first)
        later = reserve_matrix(matrix, first[0]['U'], first[0]['V'], size, quality, coverage, bonus)
        expected = solve(old, later, size, False)
        actual = solve(new, later, size, True, cancel=True)
        compare(actual, expected)
        count, calls = special_phases(graphs, symbol, new.pending_seed, limit)
        phase_cases += count
        phase_calls += calls
        work_pairs.append((limit, expected[2]['work'], actual[2]['work']))
        comparisons += 2
    assert all(new_work < old_work for _, old_work, new_work in work_pairs), (
        'Integer-MinV must remove real-prefix potential work', work_pairs)
    print('WO_INTEGER_MINV_PRODUCTION_MODEL_PASS', comparisons, 'comparisons', work_pairs,
          phase_cases, 'seeded phases', phase_calls, 'seeded calls')


if __name__ == '__main__':
    import argparse
    args = argparse.ArgumentParser()
    args.add_argument('--size', type=int, default=24)
    args.add_argument('--random-cases', type=int, default=30)
    args.add_argument('--limits', type=int, nargs='+', default=(1, 3, 64))
    args.add_argument('--gather-gate', action='store_true')
    options = args.parse_args()
    gather_gate_run() if options.gather_gate else run(options.size, options.random_cases, options.limits)
