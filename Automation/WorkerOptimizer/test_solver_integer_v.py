"""Shared VM fixtures and historical Used-V probe.

The standalone probe requires the frozen U-only Increment6 parent. Current
production is tested by test_solver_integer_v_production.py instead.
"""

import math
from pathlib import Path
import random
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import advance_shadows, projected_v, prototype_graphs
from solver_used_label_marker_prototype import render
from test_solver_integer_u import bits, equal_u, state, verify_vm_certification
from test_solver_integer_u_production import fixture_class as production_fixture
from test_solver_native_lifecycle_model import emitted
from test_solver_used_label_marker import initialize, result
from test_solver_used_label_marker_model import reserve_matrix


def fixture_class(production=False, writer=None):
    write = writer or BP.write_graph_dsl
    bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_IntegerV_' + str(time.time_ns()), production_fixture())
    base, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    candidate = {} if production else prototype_graphs(base, symbol)
    names = [name for name in candidate if name.startswith('IntegerV')]
    graphs = {name: BP.add_function_graph(bp, name) for name in names +
              ['SeedIntegerVZero', 'SeedIntegerVPhase', 'SeedIntegerVEntry']}
    BP.add_function_param(graphs['SeedIntegerVZero'], 'Index', 'int', True)
    BP.add_function_param(graphs['SeedIntegerVZero'], 'Zero', 'float', True)
    for name, kind in [('Pending', 'bool'), ('Terminal', 'bool'), ('DeltaValue', 'float'), ('Zero', 'float')]:
        BP.add_function_param(graphs['SeedIntegerVPhase'], name, kind, True)
    BP.add_function_param(graphs['SeedIntegerVEntry'], 'Value', 'float', True)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs['SeedIntegerVPhase'], '', [])

    def node(ending):
        matches = [value for value in available if value.rsplit('|', 1)[-1].casefold() == ending.casefold()]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, symbol):
            text = str(value)
            if text.startswith('Variables|Default|') or text.endswith('|FloortoInteger64'):
                return symbol(node(text.rsplit('|', 1)[-1]))
        return value

    g = lambda name: f'({node("Get" + name)})'
    s = lambda name, value: f'({node("Set" + name)} {value})'
    put = lambda name, index, value: f'(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})'
    fields = dict(Done='false', Succeeded='true', SolverState='6', Cursor='0', LastStepWork='0',
        Delta='DeltaValue', Rows='7', Cols='8', Width='8', J0='3', J1='(select Terminal 7 2)',
        ActiveRow='7', NonpositiveV='true', DummyCount='0', NativePlannerTrusted='true',
        NativeFreeValid='false', NativeFreeRow='7', NativeFreeColumn='0', NativeFreeMinimum='1e30',
        NativeValue='(* Zero -1.0)', NativeMaskReady='true', FirstFreeColumn='7',
        PotentialFreeFixedColumn='0', NativeDummyBoundReady='false', ImplicitWorkerCount='0',
        NativeDeadLabels='false', UpperGlobalReady='false', UpperPrefixReady='false',
        IntegerUEnabled='true', IntegerUActive='true', IntegerURoot='7', IntegerUTotal='0.0',
        IntegerUEpoch='(select Pending 2 0)')
    arrays = dict(U=['(* Zero -1.0)'] * 8, V=['(* Zero -1.0)'] * 9,
        MinV=['1.0'] * 9, P=['7', '1', '2', '3', '4', '5', '6', '0', '0'],
        UsedColumns=['0', '1', '3'], Used=['true', 'true', 'false', 'true'] + ['false'] * 5,
        IntegerUOffsets=['0.0'] * 9, IntegerUEpochs=['0'] * 9)
    seed_arrays = '\n'.join(f'(Utilities|Array|Clear {g(name)}) ' + ' '.join(
        f'(Utilities|Array|Add {g(name)} {value})' for value in values) for name, values in arrays.items())
    with toolset_registry.tool_raising_exceptions():
        for name in names:
            write(graphs[name], render(resolve(candidate[name]), symbol))
            unreal.log('WO_INTEGER_V_PROTOTYPE_GRAPH ' + name)
        write(graphs['SeedIntegerVZero'], f'''(fn SeedIntegerVZero (Index Zero)
          {put('V', 'Index', '(* Zero -1.0)')})''')
        write(graphs['SeedIntegerVPhase'], f'''(fn SeedIntegerVPhase (Pending Terminal DeltaValue Zero)
          ({node('IntegerUReset')}) {' '.join(s(name, value) for name, value in fields.items())}
          {seed_arrays} {put('V', '0', str(float(2**54 + 4)))})''')
        write(graphs['SeedIntegerVEntry'], f'''(fn SeedIntegerVEntry (Value)
          {s('SolverState', '4')} {s('J0', '2')} {s('I0', '2')} {put('V', '2', 'Value')})''')
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return bp.generated_class()


def step(obj, candidate, shadow_u, shadow_v, production=False):
    before = state(obj)
    obj.call_method('IntegerVAdvance' if candidate and not production else 'Advance')
    after = state(obj)
    advance_shadows(before, after, shadow_u, shadow_v)
    equal_u(projected_u(after), shadow_u)
    equal_u(projected_v(after) if candidate else after['V'], shadow_v)
    assert 0 < after['LastStepWork'] <= obj.get_editor_property('StepWorkLimit')
    return after


def solve(obj, matrix, candidate, limit, prefix, dummy=False, implicit=False, cancel=False,
          production=False):
    initialize(obj, matrix, True, limit, prefix, dummy, implicit)
    assert not obj.get_editor_property('IntegerUEnabled')
    assert not obj.get_editor_property('IntegerUOffsets')
    obj.call_method('ConfigureProductionIntegerU', args=(candidate if production else True,))
    for i in range(len(matrix) + 1):
        obj.call_method('SeedProductionUZero', args=(i, 0.0))
    for i in range(len(obj.get_editor_property('V'))):
        obj.call_method('SeedIntegerVZero', args=(i, 0.0))
    shadow_u, shadow_v = list(obj.get_editor_property('U')), list(obj.get_editor_property('V'))
    assert all(bits(v) == bits(-0.0) for v in shadow_u + shadow_v)
    calls = pending = 0
    while not obj.get_editor_property('Done'):
        after = step(obj, candidate, shadow_u, shadow_v, production)
        if any(bits(a) != bits(b) for a, b in zip(after['V'], shadow_v)):
            pending += 1
            if cancel:
                obj.call_method('StopMarker')
                frozen = state(obj)
                obj.call_method('Advance' if production else 'IntegerVAdvance')
                frozen['LastStepWork'] = 0
                assert state(obj) == frozen
                equal_u(projected_u(frozen), shadow_u)
                equal_u(projected_v(frozen), shadow_v)
                return None, pending
        calls += 1
        assert calls < 100000
    equal_u(list(obj.get_editor_property('U')), shadow_u)
    equal_u(list(obj.get_editor_property('V')), shadow_v)
    return (result(obj), [bits(v) for v in obj.get_editor_property('MinV')], bits(obj.get_editor_property('Delta'))), pending


def special_phases(old, new, production=False):
    cases = 0
    for limit in (1, 3, 64):
        for delta in (0.0, -0.0, 1.0, -1.0, .125, float(2**50 + 1), math.inf, -math.inf, math.nan):
            for terminal in (False, True):
                for pending in (False, True):
                    new.set_editor_property('StepWorkLimit', limit)
                    new.call_method('SeedIntegerVPhase', args=(pending, terminal, delta, 0.0))
                    actual = state(new)
                    u, v = list(actual['U']), list(actual['V'])
                    assert bits(u[1]) == bits(-0.0) and bits(v[1]) == bits(-0.0)
                    if pending:
                        for column in actual['UsedColumns']:
                            u[actual['P'][column]] = 0.0
                            if column:
                                v[column] = 0.0
                    count = 0
                    while new.get_editor_property('SolverState') == 6:
                        actual = step(new, True, u, v, production)
                        count += 1
                        assert count < 100
                    equal_u(projected_u(actual), u)
                    equal_u(projected_v(actual), v)
                    if terminal or not math.isfinite(delta) or delta == .125 or abs(delta) > 2**50:
                        equal_u(actual['U'], u)
                        equal_u(actual['V'], v)
                    cases += 1
        for value in (.25, float(2**50 + 1), math.inf, math.nan):
            new.set_editor_property('StepWorkLimit', limit)
            new.call_method('SeedIntegerVPhase', args=(True, False, 1.0, 0.0))
            new.call_method('SeedIntegerVEntry', args=(value,))
            actual = state(new)
            u, v = list(actual['U']), list(actual['V'])
            for column in actual['UsedColumns']:
                u[actual['P'][column]] = 0.0
                if column:
                    v[column] = 0.0
            new.call_method('IntegerUPrepareRow' if production else 'IntegerVPrepareRow')
            assert new.get_editor_property('IntegerUFlushMode') == 3
            while new.get_editor_property('IntegerUFlushMode'):
                actual = step(new, True, u, v, production)
            equal_u(actual['U'], u)
            equal_u(actual['V'], v)
            assert not actual['IntegerUActive']
            cases += 1
    return cases


def run(writer=None):
    cls = fixture_class(writer=writer)
    old, new = unreal.new_object(cls), unreal.new_object(cls)
    verify_vm_certification(new)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]], [[0., 0.], [0., 0.]],
                [[math.nan, 0.]], [[math.inf, 0.]], [[float(2**49) + .125, 1.], [float(2**49) - .125, 0.]]]
    rng = random.Random(872391)
    for _ in range(20):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    cases = pending = 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected = solve(old, matrix, False, limit, prefix, dummy)
                actual = solve(new, matrix, True, limit, prefix, dummy)
                assert actual[0] == expected[0], ('production U versus candidate UV', limit, dummy, index)
                cases += 1
                pending += actual[1]
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        matrix, quality, coverage, bonus = benchmark_matrices(24)
        expected = solve(old, matrix, False, limit, 24, implicit=True)
        actual = solve(new, matrix, True, limit, 24, implicit=True)
        assert actual[0] == expected[0]
        later = reserve_matrix(matrix, list(old.get_editor_property('U')), list(old.get_editor_property('V')),
                               24, quality, coverage, bonus)
        expected = solve(old, later, False, limit, 24)
        actual = solve(new, later, True, limit, 24)
        assert actual[0] == expected[0]
        pending += actual[1]
        stopped = solve(new, later, True, limit, 24, cancel=True)
        assert stopped[0] is None and stopped[1] > 0
        assert solve(new, later, True, limit, 24)[0] == expected[0]
        cases += 2
    phases = special_phases(old, new)
    assert cases == 156 and pending > 0
    unreal.log(f'WO_INTEGER_V_COMPILED_PROTOTYPE_PASS cases={cases} pending_calls={pending} special_phases={phases}')


if __name__ == '__main__':
    run()
