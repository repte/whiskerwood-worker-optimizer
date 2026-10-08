"""Exact emitted U preparation/setup fusion, aligned by unchanged work units."""

import copy
import itertools
import math
import random

from test_planner_validation_cache_model import encoded
from test_solver_integer_u_production_model import Machine
from test_solver_native_relaxation_model import check_structure
from test_solver_relaxation_range_model import emitted
from test_solver_used_label_marker_model import initialize, reserve_matrix


def legacy_graphs(graphs, symbol):
    """Restore just the old unconditional return after real U preparation."""
    result = copy.deepcopy(graphs)
    hits = []

    def walk(form):
        if not isinstance(form, list):
            return
        for index, child in enumerate(form):
            if (isinstance(child, list) and len(child) == 1
                    and str(child[0]).endswith('|IntegerUPrepareRow')):
                assert str(form[0]) == 'if' and index == 2 and len(form) == 4, form
                form[index + 1] = [symbol('return')]
                hits.append(form)
                return
            walk(child)

    walk(result['Advance'])
    assert len(hits) == 1, hits
    check_structure(result)
    assert all(result[name] == graphs[name] for name in graphs if name != 'Advance')
    return result


def state_bits(state):
    return {name: encoded(value) for name, value in state.items() if name != 'LastStepWork'}


class Pair:
    def __init__(self, current, reference, symbol, limit=64):
        self.current = Machine(current, symbol, limit, defer_v=True)
        self.reference = Machine(reference, symbol, limit, defer_v=True)
        self.calls = self.reference_calls = self.fusions = self.work = 0
        self.destinations = set()

    def seed(self, state):
        self.current.state = copy.deepcopy(state)
        self.reference.state = copy.deepcopy(state)

    def initialize(self, matrix, prefix, enabled=True, implicit=False, dummy=False, mode=False):
        for machine in (self.current, self.reference):
            initialize(machine, matrix, False, prefix, dummy, implicit)
            machine.state.update(IntegerUEnabled=enabled, IntegerMinEnabled=enabled,
                                 DyadicEighthsEnabled=mode, NativePlannerTrusted=enabled)
            if enabled:
                machine.invoke('EnableNativeDeadLabels')
        assert state_bits(self.current.state) == state_bits(self.reference.state)

    def step(self, limit, context):
        for machine in (self.current, self.reference):
            machine.state['StepWorkLimit'] = limit
        before = copy.deepcopy(self.current.state)
        self.current.invoke('Advance')
        actual_work = self.current.state['LastStepWork']
        assert 0 <= actual_work <= max(0, limit), (context, actual_work, limit)
        expected_work = calls = 0
        first = None
        for _ in range(2):
            self.reference.invoke('Advance')
            calls += 1
            expected_work += self.reference.state['LastStepWork']
            if first is None:
                first = copy.deepcopy(self.reference.state)
            if expected_work >= actual_work:
                break
        assert actual_work == expected_work, (context, 'work units', actual_work, expected_work)
        left, right = state_bits(self.current.state), state_bits(self.reference.state)
        assert left.keys() == right.keys(), (context, 'state schema', left.keys() ^ right.keys())
        for name in left:
            assert left[name] == right[name], (
                context, name, self.current.state[name], self.reference.state[name], before)
        if calls == 2:
            assert limit >= 2 and actual_work == 2 and first['LastStepWork'] == 1
            assert before['SolverState'] == 4 and not before['IntegerURowPrepared']
            assert first['SolverState'] == 4 and first['IntegerURowPrepared']
            assert first['IntegerUFlushMode'] == 0 and not first['IntegerMinActive']
            assert self.current.state['SolverState'] in (5, 6, 11)
            self.destinations.add(self.current.state['SolverState'])
            self.fusions += 1
        if limit <= 1 or not before['IntegerUEnabled'] or before['IntegerMinActive']:
            assert calls == 1, (context, 'protected path fused', before)
        self.calls += 1
        self.reference_calls += calls
        self.work += actual_work
        return calls

    def complete(self, budgets, context):
        for index in range(30000):
            if self.current.state['Done']:
                return
            self.step(budgets[index % len(budgets)], (context, index))
        raise AssertionError(('did not terminate', context))


def ready_seed(reference, symbol):
    machine = Machine(reference, symbol, 64, defer_v=True)
    initialize(machine, [[10., 9., 0.], [10., 8., 0.]], False, 2)
    machine.state.update(IntegerUEnabled=True, IntegerMinEnabled=True)
    machine.invoke('EnableNativeDeadLabels')
    for _ in range(100):
        if machine.state['SolverState'] == 4 and not machine.state['IntegerURowPrepared']:
            return copy.deepcopy(machine.state)
        machine.invoke('Advance')
    raise AssertionError('No natural U preparation boundary')


def guards(current, reference, symbol):
    seed = ready_seed(reference, symbol)
    checks = 0
    for mode, limit, change in itertools.product((False, True), (0, 1, 2, 3, 64), (
            {}, {'IntegerUEnabled': False}, {'NativePlannerTrusted': False},
            {'IntegerURowPrepared': True}, {'Done': True},
            {'invalid_u': .1}, {'invalid_u': .125}, {'invalid_u': .0625},
            {'invalid_u': float(2**50 + 1)}, {'invalid_u': math.inf},
            {'invalid_v': .1}, {'invalid_v': .125},
            {'min_active': True}, {'min_active_root_changed': True})):
        pair = Pair(current, reference, symbol, limit)
        changed = copy.deepcopy(seed)
        changed['DyadicEighthsEnabled'] = mode
        if 'invalid_u' in change or 'invalid_v' in change or 'min_active' in change:
            changed.update(IntegerURoot=changed['ActiveRow'], IntegerUActive=True,
                           IntegerUOffsets=[0.0] * (changed['Width'] + 1),
                           IntegerUEpochs=[0] * (changed['Width'] + 1))
        if 'invalid_u' in change:
            changed['U'][changed['P'][changed['J0']]] = change['invalid_u']
        elif 'invalid_v' in change:
            changed.update(J0=1, UsedColumns=[0])
            changed['P'][1] = 1
            changed['V'][1] = change['invalid_v']
        elif 'min_active' in change or 'min_active_root_changed' in change:
            changed.update(IntegerMinActive=True, IntegerUActive=True, IntegerMinPrefix=2,
                           IntegerMinOffset=0.0, IntegerMinEpoch=0,
                           IntegerMinBirth=[0] * 3, IntegerMinZero=[0.0] * 3,
                           IntegerMinFlushCursor=0)
            if 'min_active_root_changed' in change:
                changed.update(IntegerURoot=-1, J0=1, UsedColumns=[0])
                changed['P'][1] = 1
        else:
            changed.update(change)
        pair.seed(changed)
        pair.step(limit, ('guard', mode, limit, change))
        # Test a following call too: preparation may have requested a label/U flush.
        pair.step(max(1, limit), ('after guard', mode, limit, change))
        checks += 1
    return checks


def run():
    current, symbol = emitted()
    reference = legacy_graphs(current, symbol)
    pair = Pair(current, reference, symbol)
    seed = ready_seed(reference, symbol)
    pair.seed(seed)
    pair.step(64, 'target successful preparation')
    assert pair.fusions == 1 and pair.current.state['LastStepWork'] == 2, (
        'Successful preparation still requires its own callback',
        pair.fusions, pair.current.state['LastStepWork'], pair.current.state['SolverState'])

    guard_cases = guards(current, reference, symbol)
    matrices = [
        [[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
        [[-0.0, 0.0], [0.0, -0.0]],
        [[.125, .375, 0.], [.1, .0625, 0.]],
        [[math.nan, 0.]], [[math.inf, 0.]],
        [[float(2**50), .125, 0.], [float(2**50 + 1), 1., 0.]],
    ]
    rng = random.Random(130012)
    for _ in range(8):
        rows, cols = rng.randint(1, 5), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -0.0, 0., .125, .1, .0625, 7., 1e14 + .06])
                          for _ in range(cols)] for _ in range(rows)])
    solves = cancellations = calls = old_calls = fusions = 0
    destinations = set()
    budgets_list = ((1,), (2,), (3,), (64,), (1, 2, 64, 3))
    for budgets, enabled, mode in itertools.product(budgets_list, (False, True), (False, True)):
        pair = Pair(current, reference, symbol, budgets[0])
        for index, matrix in enumerate(matrices):
            pair.initialize(matrix, len(matrix[0]), enabled, dummy=index % 2 == 1, mode=mode)
            pair.complete(budgets, ('generic', solves))
            solves += 1
        if enabled:
            from test_solver_cached_trace import benchmark_matrices
            from test_solver_scale8_candidate_model import fractional_matrix
            matrix, quality, coverage, bonus = (fractional_matrix(12) if mode else benchmark_matrices(12))
            pair.initialize(matrix, 12, implicit=True, mode=mode)
            pair.complete(budgets, ('implicit', mode, budgets))
            later = reserve_matrix(matrix, pair.reference.state['U'], pair.reference.state['V'],
                                   12, quality, coverage, bonus)
            pair.initialize(later, 12, mode=mode)
            pair.complete(budgets, ('later', mode, budgets))
            solves += 2
            # Cancel immediately after an aligned advance, then reuse both objects.
            pair.initialize(matrix, 12, implicit=True, mode=mode)
            for index in range(1000):
                pair.step(budgets[index % len(budgets)], ('before cancellation', index))
                if pair.current.state['SolverState'] in (5, 6, 11):
                    break
            else:
                raise AssertionError('No cancellable phase')
            for machine in (pair.current, pair.reference):
                machine.state['Done'] = True
                machine.state['StepWorkLimit'] = budgets[0]
            before = state_bits(pair.current.state)
            pair.step(budgets[0], 'cancelled')
            assert state_bits(pair.current.state) == before
            pair.initialize(later, 12, mode=mode)
            pair.complete(budgets, ('restart', mode, budgets))
            cancellations += 1
            solves += 1
        calls += pair.calls
        old_calls += pair.reference_calls
        fusions += pair.fusions
        destinations |= pair.destinations
    assert fusions > 0 and old_calls - calls == fusions
    assert destinations == {5, 6, 11}, destinations
    assert [name for name in current if current[name] != reference[name]] == ['Advance']
    print('WO_PREPARE_FUSION_MODEL_PASS', f'{guard_cases} guard cases, {solves} solves, '
          f'{calls}/{old_calls} aligned callbacks, {fusions} fusions, '
          f'{cancellations} cancellations/restarts, all state bits and total work unchanged')


if __name__ == '__main__':
    run()
