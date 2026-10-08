"""Fixed-index relaxation versus the prior emitted per-cell cursor loop."""

import ast
import copy
import importlib
import itertools
import math
from pathlib import Path

from planner_cost_dsl import implicit_row_setup
from test_planner_validation_cache_model import encoded
from test_solver_integer_u_production_model import Machine
from test_solver_native_relaxation_model import parser, check_structure
from test_solver_used_label_marker_model import initialize


def old_dispatch(get, regular, certified, bounded, implicit_regular,
                 implicit_certified, implicit_bounded, finish):
    def loop(edge):
        return f'''(for work (range {get('LastStepWork')})
          (if (<= {get('Cursor')} {get('Width')}) {edge} (else {finish})))'''

    def mode(plain, zero, lower):
        return f'''(if {get('RelaxationBoundEnabled')} {loop(lower)}
          (else (if {get('ZeroLabelBound')} {loop(zero)} (else {loop(plain)}))))'''

    return f'''(if {get('ImplicitFirstPass')} {mode(implicit_regular, implicit_certified, implicit_bounded)}
      (else {mode(regular, certified, bounded)}))'''


def emitted(legacy=False, syntax=None):
    path = Path(__file__).with_name('generate_solver.py')
    def node(name):
        return {'SortFloatArray': 'Utilities|Array|Sort|SortFloatArray',
                'FindItem': 'Utilities|Array|FindItem'}.get(name, 'Variables|Default|' + name)
    env = {'node': node}
    active = False
    for item in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(item, ast.ImportFrom) and item.module in {
                'planner_cost_dsl', 'solver_relaxation_bound_dsl', 'solver_native_relaxation_dsl',
                'solver_integer_u_dsl', 'solver_integer_minv_dsl'}:
            helper = importlib.import_module(item.module)
            for alias in item.names:
                env[alias.asname or alias.name] = getattr(helper, alias.name)
        if isinstance(item, ast.FunctionDef) and item.name == 'get':
            active = True
        if active and isinstance(item, (ast.FunctionDef, ast.Assign)):
            if legacy and isinstance(item, ast.FunctionDef) and item.name == 'relaxation_dispatch':
                env[item.name] = lambda *args: old_dispatch(env['get'], *args)
            else:
                exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), 'exec'), env)
    parse, symbol = syntax or parser()
    graphs = {}
    for source in env.values():
        if isinstance(source, str) and source.lstrip().startswith('(fn '):
            forms = parse(source)
            graphs[str(forms[0][1])] = forms
    graphs['SetupProbeRow'] = parse('(fn SetupProbeRow () ' +
        implicit_row_setup(env['get'], env['put'], env['at'], '0') + ')')
    check_structure(graphs)
    return graphs, symbol


class CounterMachine(Machine):
    def __init__(self, *args):
        super().__init__(*args, defer_v=True)
        self.cursor_writes = 0

    def evaluate(self, form):
        if isinstance(form, list) and form and str(form[0]).endswith('|SetCursor'):
            self.cursor_writes += 1
        return super().evaluate(form)


def state_bits(state):
    # This is the only new private scratch; every pre-existing field is compared.
    return {name: encoded(value) for name, value in state.items() if name != 'RelaxationEnd'}


def loops_in(value):
    if not isinstance(value, list):
        return []
    return ([value] if value and str(value[0]) == 'for' else []) + [
        loop for child in value for loop in loops_in(child)]


def direct_seed(machine, native_mode, implicit, bound_mode, start):
    matrix = [[100.125, 10.125, -0.0, 100.125, 1e-12, 0.0, 0.0],
              [10.125, 100.125, 0.0, -0.0, 1e6, 0.0, 0.0]]
    initialize(machine, matrix, False, 5, implicit=implicit)
    machine.state.update(SolverState=5, Cursor=start, Width=7, DummyCount=0,
        ActiveRow=1, I0=1, J0=1, J1=0, RowPotential=-0.0, RowScoreOffset=-1,
        Delta=1e30, Cur=-0.0, BestColumnFree=False,
        NativePlannerTrusted=native_mode != 0, NativeUsedRealOnly=True,
        NativeDeadLabels=native_mode == 2, NativeDeadPrefixWidth=5, NativeDeadPrefixUsed=2,
        IntegerUActive=True, IntegerMinEnabled=native_mode == 2,
        IntegerMinGathering=native_mode == 2, IntegerMinCertified=True,
        IntegerMinPrefix=5, IntegerMinCount=0, IntegerMinDummyCount=0,
        IntegerMinRawUpper=-1e30, IntegerMinDummyBound=1e30,
        IntegerMinBirth=[0] * 6, IntegerMinZero=[0.0] * 6,
        FirstFreeColumn=8, RelaxationBoundEnabled=bound_mode == 2,
        RelaxationLowerBound=0.0, ZeroLabelBound=bound_mode == 1,
        NativeDummyBound=1e30, NativeDummyBoundRow=1, NativeDummyInitCount=0,
        NativeFreeColumn=0, NativeFreeMinimum=1e30, NativeFreeValid=False,
        U=[0.0] * 10, V=[0.0, -0.0, -3.0, 0.0, 1.0, -1e-12, 0.0, 0.0, 0.0, 0.0],
        Used=[True, False, False, False, True, False, False, False, False, False],
        MinV=[math.inf, -0.0, 3.0, -2.0, math.inf, 1e20, 0.0, -0.0, 0.0, 0.0],
        P=[1, 2, 0, 0, 1, 0, 0, 0, 0, 0], Way=[0] * 10)
    if implicit:
        machine.invoke('SetupProbeRow')


def run():
    syntax = parser()
    current, symbol = emitted(syntax=syntax)
    reference, _ = emitted(legacy=True, syntax=syntax)
    changed = [name for name in current if current[name] != reference[name]]
    assert changed in ([], ['AdvanceRelaxation']), changed
    calls = direct_cases = original_writes = replacement_writes = 0
    for native_mode, implicit, bound_mode in itertools.product(range(3), (False, True), range(3)):
        for start in (1, 6, 7, 8):
            for budgets in ((1,), (3,), (64,), (3, 1, 64)):
                pair = [CounterMachine(graphs, symbol, budgets[0]) for graphs in (current, reference)]
                for machine in pair:
                    direct_seed(machine, native_mode, implicit, bound_mode, start)
                for call in range(20):
                    if pair[0].state['SolverState'] != 5:
                        break
                    for machine in pair:
                        machine.state['StepWorkLimit'] = budgets[call % len(budgets)]
                        machine.cursor_writes = 0
                        machine.invoke('AdvanceRelaxation')
                    assert state_bits(pair[0].state) == state_bits(pair[1].state), (
                        native_mode, implicit, bound_mode, start, budgets, call)
                    assert 0 < pair[0].state['LastStepWork'] <= pair[0].state['StepWorkLimit']
                    original_writes += pair[1].cursor_writes
                    replacement_writes += pair[0].cursor_writes
                    calls += 1
                else:
                    raise AssertionError('Direct relaxation did not reach the phase boundary')
                direct_cases += 1
    for budget in (0, -1):
        pair = [CounterMachine(graphs, symbol, budget) for graphs in (current, reference)]
        for machine in pair:
            direct_seed(machine, 2, True, 2, 1)
            machine.invoke('AdvanceRelaxation')
        assert state_bits(pair[0].state) == state_bits(pair[1].state), ('nonpositive direct budget', budget)

    full_batch = [CounterMachine(graphs, symbol, 64) for graphs in (current, reference)]
    for machine in full_batch:
        direct_seed(machine, 0, False, 0, 1)
        machine.state.update(Width=128, Cols=128, Scores=[1.0] * 256,
                             Used=[False] * 130, MinV=[1e30] * 130,
                             V=[0.0] * 130, P=[0] * 130, Way=[0] * 130)
        machine.cursor_writes = 0
        machine.invoke('AdvanceRelaxation')
    assert state_bits(full_batch[0].state) == state_bits(full_batch[1].state)
    assert full_batch[0].state['LastStepWork'] == 64 and full_batch[0].state['Cursor'] == 65

    restarts = 0
    for implicit in (False, True):
        pair = [CounterMachine(graphs, symbol, 3) for graphs in (current, reference)]
        for machine in pair:
            direct_seed(machine, 2, implicit, 0, 1)
            machine.invoke('AdvanceRelaxation')
            assert machine.state['Cursor'] == 4
            machine.state['Done'] = True
            before = state_bits(machine.state)
            machine.invoke('Advance')
            before['LastStepWork'] = 0
            assert state_bits(machine.state) == before, 'Cancelled solver must remain inert'
            matrix = [[10.0, 9.0, 0.0, 0.0], [10.0, 8.0, 0.0, 0.0], [10.0, 7.0, 0.0, 0.0]]
            initialize(machine, matrix, False, 2, implicit=implicit)
            machine.state['RelaxationEnd'] = -999
        entered_scan = False
        for call in range(10000):
            if pair[0].state['Done']:
                break
            before_state = pair[0].state['SolverState']
            for machine in pair:
                machine.state['StepWorkLimit'] = (1, 3, 64)[call % 3]
                machine.invoke('Advance')
            entered_scan |= before_state == 5
            assert state_bits(pair[0].state) == state_bits(pair[1].state), ('reuse', implicit, call)
        else:
            raise AssertionError('Reused solver failed to terminate')
        assert entered_scan
        restarts += 1

    full_calls = solves = 0
    matrices = [
        [[9.0, 1.0, 0.0], [1.0, 9.0, 0.0]],
        [[0.0, -0.0, 0.0]] * 3,
        [[100.125, 10.125, 10.125, 0.0, 0.0], [10.125, 100.125, 10.125, 0.0, 0.0],
         [10.125, 10.125, 100.125, 0.0, 0.0], [1.125, 2.125, 3.125, 0.0, 0.0]],
    ]
    for budgets, native, implicit in itertools.product(((1,), (3,), (64,), (64, 1, 3)), (False, True), (False, True)):
        for matrix in matrices:
            pair = [CounterMachine(graphs, symbol, budgets[0]) for graphs in (current, reference)]
            for machine in pair:
                initialize(machine, matrix, False, 3, implicit=implicit)
                machine.state.update(NativePlannerTrusted=native, IntegerUEnabled=native,
                                     IntegerMinEnabled=native, DyadicEighthsEnabled=True)
                if native:
                    machine.invoke('EnableNativeDeadLabels')
            for call in range(10000):
                if pair[0].state['Done']:
                    break
                for machine in pair:
                    machine.state['StepWorkLimit'] = budgets[call % len(budgets)]
                    machine.invoke('Advance')
                assert state_bits(pair[0].state) == state_bits(pair[1].state), (budgets, native, implicit, solves, call)
                full_calls += 1
            else:
                raise AssertionError('Complete solver did not terminate')
            solves += 1
    print(f'RELAXATION_RANGE_EQUIVALENCE_PASS: {direct_cases} direct cases/{calls} calls, '
          f'{solves} full solves/{full_calls} calls, {restarts} cancelled/reused initializers, '
          'all old field bits/work unchanged')
    assert full_batch[0].cursor_writes == 1 and full_batch[1].cursor_writes == 64, (
        'A complete 64-edge chunk must write Cursor exactly once',
        full_batch[0].cursor_writes, full_batch[1].cursor_writes)
    assert replacement_writes < original_writes, (
        'Batch relaxation must publish Cursor once instead of after every edge', replacement_writes, original_writes)
    loops = loops_in(current['AdvanceRelaxation'])
    assert len(loops) == 18
    for loop in loops:
        assert str(loop[1]) == 'j'
        assert loop[2] == [symbol('range'), [symbol('Variables|Default|GetCursor')],
                           [symbol('Variables|Default|GetRelaxationEnd')]], 'ForLoop bound must be cached'
    print(f'WO_SOLVER_RELAXATION_RANGE_MODEL_PASS: Cursor writes {original_writes}->{replacement_writes}')


if __name__ == '__main__':
    run()
