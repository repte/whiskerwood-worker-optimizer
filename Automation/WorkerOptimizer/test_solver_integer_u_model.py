"""Actual-emitted private integer-U graphs versus eager solver arithmetic."""

import argparse
from collections import Counter
import copy
import itertools
import json
import math
from pathlib import Path
import random

from benchmark_native_relaxation import equal
from solver_integer_u_prototype import LIMIT, projected_u, prototype_graphs
from solver_integer_v_prototype import advance_shadows, projected_v
from test_solver_native_lifecycle_model import SolverMachine, emitted


class IntegerMachine(SolverMachine):
    def __init__(self, graphs, symbol, limit, defer_v=False):
        super().__init__(graphs, symbol, limit)
        self.eager_u = None
        self.eager_v = None
        self.defer_v = defer_v
        self.counts = Counter()

    def evaluate(self, form):
        if isinstance(form, list) and form:
            name = str(form[0])
            if name.rsplit('|', 1)[-1] == 'FloortoInteger64':
                value = self.evaluate(form[2])
                assert math.isfinite(value) and abs(value) <= LIMIT
                return math.floor(value)
            if name == 'Variables|SetBy-RefVar':
                assert str(form[1]) == ':Target' and str(form[3]) == ':Value'
                target = form[2]
                assert str(target[0]) == 'Utilities|Array|Get(aref)'
                array, index = self.evaluate(target[2]), self.evaluate(target[4])
                assert 0 <= index < len(array)
                target_name = str(target[2][0]).removeprefix('Variables|Default|Get')
                self.counts['writes_' + target_name] += 1
                array[index] = self.evaluate(form[4])
                return
            if name == 'Utilities|Array|SetArrayElem':
                target = str(form[2][0]).removeprefix('Variables|Default|Get')
                self.counts['writes_' + target] += 1
        return super().evaluate(form)

    def advance_checked(self, method='IntegerUAdvance'):
        before = copy.deepcopy(self.state)
        if self.eager_v is None:
            self.eager_v = projected_v(before) if self.defer_v else list(before['V'])
        self.invoke(method)
        advance_shadows(before, self.state, self.eager_u, self.eager_v)
        assert equal(projected_u(self.state), self.eager_u), (
            'Per-call projected U bits', method, self.state, self.eager_u)
        visible_v = projected_v(self.state) if self.defer_v else self.state['V']
        assert equal(visible_v, self.eager_v), ('Per-call V bits', method, self.state, self.eager_v)
        assert 0 < self.state['LastStepWork'] <= self.state['StepWorkLimit']


def start(machine, matrix, enabled, native, limit):
    rows, cols = len(matrix), len(matrix[0])
    machine.eager_u = None
    machine.eager_v = None
    machine.state['StepWorkLimit'] = limit
    machine.invoke('IntegerUInitialize', [[v for row in matrix for v in row], rows, cols])
    assert machine.state['IntegerUEnabled'] is False
    assert not machine.state['IntegerUActive'] and machine.state['IntegerUFlushMode'] == 0
    assert not machine.state['IntegerUOffsets'] and not machine.state['IntegerUEpochs']
    machine.invoke('RestrictDummies', [[False] * rows])
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    machine.state.update(IntegerUEnabled=enabled, NativePlannerTrusted=native,
                         NativeCsrReady=native, NativeRowOffsets=offsets, NativeColumns=columns)
    machine.eager_u = list(machine.state['U'])
    machine.eager_v = list(machine.state['V'])


def solve(machine, matrix, enabled, native, limit, cancelled):
    start(machine, matrix, enabled, native, limit)
    calls = 0
    while not machine.state['Done']:
        machine.advance_checked()
        calls += 1
        assert calls < 100000
        category = (machine.state.get('IntegerUFlushMode', 0),
                    bool(machine.state.get('IntegerUPhasePrepared')),
                    machine.state['SolverState'])
        if category not in cancelled and (category[0] or category[1] or category[2] == 4):
            stop = copy.deepcopy(machine)
            stop.state['Done'] = True
            before, u = copy.deepcopy(stop.state), list(stop.eager_u)
            stop.invoke('IntegerUAdvance')
            before['LastStepWork'] = 0
            assert equal(stop.state, before)
            assert equal(projected_u(stop.state), u)
            assert equal(projected_v(stop.state) if stop.defer_v else stop.state['V'], stop.eager_v)
            cancelled.add(category)
    assert equal(machine.state['U'], machine.eager_u), 'Successful exit must publish actual U'
    assert equal(machine.state['V'], machine.eager_v), 'Successful exit must publish actual V'
    return copy.deepcopy(machine.state), calls


def compare_result(left, right):
    for name in ('Assignment', 'Succeeded', 'P', 'Way', 'U', 'V', 'MinV', 'Cur', 'Delta', 'J1'):
        assert equal(left.get(name, 0), right.get(name, 0)), (name, left, right)


def phase_seed(limit, delta, terminal, pending=True, negative_zero=False):
    width, rows = 8, 7
    used_columns = [0, 1, 3]
    p = [rows, 1, 2, 3, 4, 5, 6, 0, 0]
    u = [-0.0 if negative_zero else 0.0] * (rows + 1)
    state = dict(StepWorkLimit=limit, Done=False, Succeeded=True,
        SolverState=6, Cursor=0, LastStepWork=0, Delta=delta, Rows=rows, Cols=width, Width=width,
        P=p, UsedColumns=used_columns, Used=[j in used_columns for j in range(width + 1)],
        U=u, V=[0.0] * (width + 1), MinV=[1.0] * (width + 1),
        J0=3, J1=7 if terminal else 2, ActiveRow=rows, NonpositiveV=True,
        DummyCount=0, NativePlannerTrusted=True, NativeFreeValid=False,
        NativeFreeRow=rows, NativeFreeColumn=0, NativeFreeMinimum=1e30,
        NativeValue=-0.0, NativeMaskReady=True, FirstFreeColumn=7,
        PotentialFreeFixedColumn=0, NativeDummyBoundReady=False, ImplicitWorkerCount=0,
        IntegerUEnabled=True, IntegerUActive=True, IntegerURoot=rows,
        IntegerUTotal=0.0, IntegerUEpoch=2 if pending else 0,
        IntegerUOffsets=[0.0] * (width + 1), IntegerUEpochs=[0] * (width + 1),
        IntegerUPhasePrepared=False, IntegerUPhaseNonzero=False, IntegerUPhaseTerminal=False,
        IntegerURowPrepared=False, IntegerUFlushMode=0, IntegerUFlushCursor=0)
    shadow = list(u)
    if pending:
        for j in used_columns:
            # Two real nonzero additions cancel; -0 must become +0.
            shadow[p[j]] = (shadow[p[j]] + 1.0) + -1.0
    return state, shadow


def special_phases(graphs, symbol, defer_v=False):
    cases = calls = 0
    for limit, delta, terminal, pending, negative_zero in itertools.product(
            (1, 3, 64), (0.0, -0.0, 1.0, -1.0, .125, float(LIMIT + 1),
                         -float(LIMIT + 1), math.inf, -math.inf, math.nan),
            (False, True), (False, True), (False, True)):
        actual = IntegerMachine(graphs, symbol, limit, defer_v)
        actual.state, actual.eager_u = phase_seed(limit, delta, terminal, pending, negative_zero)
        reference = IntegerMachine(graphs, symbol, limit)
        reference.state = copy.deepcopy(actual.state)
        reference.state['IntegerUEnabled'] = False
        reference.state['U'] = list(actual.eager_u)
        while reference.state['SolverState'] == 6:
            reference.invoke('Advance')
        while actual.state['SolverState'] == 6:
            actual.advance_checked()
            calls += 1
            assert calls < 50000
        assert equal(projected_u(actual.state), reference.state['U'])
        assert equal(projected_v(actual.state) if defer_v else actual.state['V'], reference.state['V'])
        for name in ('MinV', 'NativeValue', 'NativeFreeMinimum', 'NativeFreeColumn', 'J0', 'SolverState'):
            assert equal(actual.state.get(name, 0), reference.state.get(name, 0)), (name, delta, actual.state, reference.state)
        if terminal or abs(delta) > LIMIT or not math.isfinite(delta) or delta == .125:
            assert equal(actual.state['U'], reference.state['U'])
        cases += 1
    # An uncertified newly visited row flushes existing work before state4 uses U.
    for limit, value in itertools.product((1, 3, 64), (.25, float(LIMIT + 1), math.inf, math.nan)):
        actual = IntegerMachine(graphs, symbol, limit, defer_v)
        actual.state, actual.eager_u = phase_seed(limit, 1.0, False, True, True)
        actual.state.update(SolverState=4, J0=2, I0=2)
        actual.state['U'][2] = actual.eager_u[2] = value
        actual.invoke('IntegerUPrepareRow')
        assert actual.state['IntegerUFlushMode'] == 3
        while actual.state['IntegerUFlushMode']:
            actual.advance_checked()
            calls += 1
        assert not actual.state['IntegerUActive']
        assert equal(actual.state['U'], actual.eager_u)
        cases += 1
    return cases, calls


def run(baseline=False, defer_v=True):
    reference, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    if 'IntegerUDeferredPotentials' in reference:
        graphs = dict(reference)
        graphs['IntegerUAdvance'] = graphs['Advance']
        graphs['IntegerUInitialize'] = graphs['Initialize']
    else:
        graphs = prototype_graphs(reference, symbol)
    machine = IntegerMachine(graphs, symbol, 1, defer_v)
    old = IntegerMachine(graphs, symbol, 1)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
                [[-0.0, 0.0], [0.0, -0.0]], [[math.nan, 0.0]], [[math.inf, 0.0]]]
    for values in itertools.product((-1.0, -0.0, 0.0, 1.0), repeat=4):
        matrices.append([list(values[:2]), list(values[2:])])
    rng = random.Random(502816)
    for _ in range(80):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0.0, 1., 3., 17., float(LIMIT), float(LIMIT+1)])
                          for _ in range(cols)] for _ in range(rows)])
    cancelled = set()
    comparisons = calls = 0
    for limit in (1, 3, 64):
        for native in (False, True):
            for matrix in matrices:
                expected, _ = solve(old, matrix, False, native, limit, set())
                actual, count = solve(machine, matrix, not baseline, native, limit, cancelled)
                compare_result(actual, expected)
                calls += count
                comparisons += 1
    cases, phase_calls = special_phases(graphs, symbol, defer_v)
    from test_solver_cached_trace import benchmark_matrices
    from test_solver_row_order_model import reserve_matrix
    matrix, quality, coverage, bonus = benchmark_matrices(24)
    first, _ = solve(old, matrix, False, True, 64, set())
    # reserve_matrix expects the faithful Python trace's lower-case fields.
    later, _ = reserve_matrix(matrix, dict(u=first['U'], v=first['V']), 24, quality, coverage, bonus)
    old.counts.clear()
    expected, _ = solve(old, later, False, True, 64, set())
    machine.counts.clear()
    actual, _ = solve(machine, later, not baseline, True, 64, cancelled)
    compare_result(actual, expected)
    old_writes, new_writes = old.counts['writes_U'], machine.counts['writes_U']
    assert new_writes < old_writes // 2, ('Integer-U prototype must remove repeated used-row writes', old_writes, new_writes)
    print('WO_INTEGER_U_PROTOTYPE_MODEL_PASS ' + json.dumps(dict(
        comparisons=comparisons, calls=calls, special_phases=cases, special_calls=phase_calls,
        cancel_states=len(cancelled), reserve24_u_writes=[old_writes, new_writes]), sort_keys=True))


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--baseline', action='store_true')
    args.add_argument('--defer-v', action=argparse.BooleanOptionalAction, default=True,
                      help='Check current UV production; --no-defer-v is for historical U-only graphs.')
    options = args.parse_args()
    run(options.baseline, options.defer_v)
