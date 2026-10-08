"""Unsaved compiled integer-U prototype; no production asset is modified.

Run only with saved solver assets matching the current generator. The private
opt-in/native flags are configured after initialization and immutable per solve.
"""

import math
from pathlib import Path
import random
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType

from solver_integer_u_prototype import INTEGER_U_VARIABLES, projected_u, prototype_graphs
from solver_used_label_marker_prototype import render
from test_solver_native_lifecycle_model import emitted


def bits(value):
    return struct.pack('!d', float(value))


def fixture_class():
    parent = unreal.load_asset('/Game/Mods/WorkerOptimizer/BP_AssignmentSolver')
    child = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_IntegerU_' + str(time.time_ns()), parent.generated_class())
    for kind, names in INTEGER_U_VARIABLES.items():
        for name in names.split():
            BP.add_variable(child, name, kind.removesuffix('[]'),
                            container_type=ContainerType.ARRAY if kind.endswith('[]') else None)
    base, symbol = emitted(Path(__file__).with_name('generate_solver.py'))
    candidate = prototype_graphs(base, symbol)
    names = [name for name in candidate if name.startswith('IntegerU')]
    graphs = {name: BP.add_function_graph(child, name) for name in names + ['ConfigureIntegerU', 'SeedIntegerUZero', 'ProbeIntegerUValue', 'StopIntegerU']}
    for name in ('IntegerUInitialize', 'IntegerUInitializeImplicitFirstPass'):
        if name == 'IntegerUInitialize':
            BP.add_function_param(graphs[name], 'IncomingScores', 'float', True, ContainerType.ARRAY)
        BP.add_function_param(graphs[name], 'RowCount', 'int', True)
        BP.add_function_param(graphs[name], 'ColumnCount', 'int', True)
    for name, kind, array in (('Enabled', 'bool', False), ('Native', 'bool', False),
                              ('Offsets', 'int', True), ('Columns', 'int', True)):
        BP.add_function_param(graphs['ConfigureIntegerU'], name, kind, True, ContainerType.ARRAY if array else None)
    BP.add_function_param(graphs['SeedIntegerUZero'], 'Row', 'int', True)
    BP.add_function_param(graphs['SeedIntegerUZero'], 'Zero', 'float', True)
    BP.add_function_param(graphs['ProbeIntegerUValue'], 'InputValue', 'float', True)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(child)
    available = BP.find_node_types(graphs['IntegerUAdvance'], '', [])

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
            if text.startswith('Variables|Default|') or text == 'Math|Float|FloortoInteger64':
                return symbol(node(text.rsplit('|', 1)[-1]))
        return value

    g = lambda name: f'({node("Get" + name)})'
    s = lambda name, value: f'({node("Set" + name)} {value})'
    with toolset_registry.tool_raising_exceptions():
        for name in names:
            BP.write_graph_dsl(graphs[name], render(resolve(candidate[name]), symbol))
            unreal.log('WO_INTEGER_U_PROTOTYPE_GRAPH ' + name)
        BP.write_graph_dsl(graphs['ConfigureIntegerU'], f'''(fn ConfigureIntegerU (Enabled Native Offsets Columns)
          {s('IntegerUEnabled', 'Enabled')} {s('NativePlannerTrusted', 'Native')} {s('NativeCsrReady', 'Native')}
          {s('NativeRowOffsets', 'Offsets')} {s('NativeColumns', 'Columns')})''')
        BP.write_graph_dsl(graphs['SeedIntegerUZero'], f'''(fn SeedIntegerUZero (Row Zero)
          (Utilities|Array|SetArrayElem :TargetArray {g('U')} :Index Row :Item (* Zero -1.0)))''')
        BP.write_graph_dsl(graphs['ProbeIntegerUValue'], f'''(fn ProbeIntegerUValue (InputValue)
          {s('IntegerUProbe', 'InputValue')} ({node('IntegerUCheckValue')}))''')
        BP.write_graph_dsl(graphs['StopIntegerU'], f'(fn StopIntegerU () {s("Done", "true")})')
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


FIELDS = ('U', 'V', 'P', 'Way', 'MinV', 'UsedColumns', 'Assignment', 'Succeeded', 'Done',
          'Rows', 'Width', 'Cursor', 'SolverState', 'J1', 'Delta', 'Cur', 'LastStepWork')
FIELDS += tuple(name for names in INTEGER_U_VARIABLES.values() for name in names.split())


def state(obj):
    result = {}
    for name in FIELDS:
        value = obj.get_editor_property(name)
        result[name] = value if isinstance(value, (bool, int, float)) else list(value)
    return result


def equal_u(actual, expected):
    assert [bits(v) for v in actual] == [bits(v) for v in expected], (actual, expected)


def initialize(obj, matrix, enabled, native, limit, negative_zero=False):
    rows, cols = len(matrix), len(matrix[0])
    obj.set_editor_property('StepWorkLimit', limit)
    obj.call_method('IntegerUInitialize', args=([v for row in matrix for v in row], rows, cols))
    assert not obj.get_editor_property('IntegerUEnabled')
    assert not obj.get_editor_property('IntegerUActive')
    assert not obj.get_editor_property('IntegerUOffsets')
    obj.call_method('RestrictDummies', args=([False] * rows,))
    if negative_zero:
        for row in range(rows + 1):
            obj.call_method('SeedIntegerUZero', args=(row, 0.0))
        assert all(bits(v) == bits(-0.0) for v in obj.get_editor_property('U'))
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    obj.call_method('ConfigureIntegerU', args=(enabled, native, offsets, columns))


def solve(obj, matrix, enabled, native, limit, negative_zero=False, cancel_at=None):
    initialize(obj, matrix, enabled, native, limit, negative_zero)
    shadow = list(obj.get_editor_property('U'))
    calls = deferred = flush_calls = 0
    while not obj.get_editor_property('Done'):
        before = state(obj)
        if cancel_at is not None and calls == cancel_at:
            obj.call_method('StopIntegerU')
            frozen = state(obj)
            obj.call_method('IntegerUAdvance')
            after = state(obj)
            frozen['LastStepWork'] = 0
            assert after == frozen
            equal_u(projected_u(after), shadow)
            return after, deferred, flush_calls
        obj.call_method('IntegerUAdvance')
        after = state(obj)
        if before['SolverState'] == 6 and before['IntegerUFlushMode'] == 0:
            rejected = after['IntegerUFlushMode'] == 1 and not before['IntegerUPhasePrepared']
            if before['Delta'] != 0.0 and not rejected:
                terminal = before['P'][before['J1']] == 0
                columns = (before['UsedColumns'][before['Cursor']:after['Cursor']] if terminal else
                           [j for j in range(before['Cursor'], after['Cursor']) if j in before['UsedColumns']])
                for column in columns:
                    row = before['P'][column]
                    shadow[row] = shadow[row] + before['Delta']
        equal_u(projected_u(after), shadow)
        deferred += any(bits(a) != bits(b) for a, b in zip(after['U'], shadow))
        flush_calls += before['IntegerUFlushMode'] != 0
        assert 0 < after['LastStepWork'] <= limit
        calls += 1
        assert calls < 100000
    equal_u(after['U'] if calls else shadow, shadow)
    return state(obj), deferred, flush_calls


def compare(left, right):
    for name in ('Assignment', 'Succeeded', 'P', 'Way'):
        assert left[name] == right[name], (name, left[name], right[name])
    for name in ('U', 'V', 'MinV'):
        equal_u(left[name], right[name])
    assert bits(left['Cur']) == bits(right['Cur'])


def verify_vm_certification(obj):
    cases = [(float(2**49) + .125, False), (float(2**50) - .25, False),
             (-float(2**49) - .125, False), (float(2**50), True),
             (-float(2**50), True), (float(2**50 + 1), False),
             (-float(2**50 + 1), False), (math.nan, False),
             (math.inf, False), (-math.inf, False), (0.0, True)]
    for value, expected in cases:
        obj.call_method('ProbeIntegerUValue', args=(value,))
        actual_input = obj.get_editor_property('IntegerUProbe')
        if math.isfinite(value):
            assert bits(actual_input) == bits(value), ('Probe lost binary64 input precision', value, actual_input)
        else:
            assert math.isnan(actual_input) if math.isnan(value) else actual_input == value
        assert obj.get_editor_property('IntegerUCertified') == expected, ('VM integral certificate', value, expected)
    unreal.log('WO_INTEGER_U_VM_CERTIFICATION_PASS binary64 fractional boundaries, int64 conversion, NaN/Inf guards')


def run():
    cls = fixture_class()
    old, new = unreal.new_object(cls), unreal.new_object(cls)
    verify_vm_certification(new)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
                [[0., 0.], [0., 0.]], [[math.nan, 0.]], [[math.inf, 0.]]]
    rng = random.Random(2500816)
    for _ in range(36):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, 0., 1., 7., float(2**50), float(2**50+1)])
                          for _ in range(cols)] for _ in range(rows)])
    cases = deferred = flushes = 0
    for limit in (1, 3, 64):
        for native in (False, True):
            for number, matrix in enumerate(matrices):
                reference = solve(old, matrix, False, native, limit, number % 5 == 0)
                actual = solve(new, matrix, True, native, limit, number % 5 == 0)
                compare(actual[0], reference[0])
                cases += 1
                deferred += actual[1]
                flushes += actual[2]
    for call in (5, 20, 40):
        solve(new, matrices[0], True, True, 1, cancel_at=call)
        compare(solve(new, matrices[0], True, True, 3)[0], solve(old, matrices[0], False, True, 3)[0])
    assert deferred > 0 and flushes > 0, (deferred, flushes)
    unreal.log(f'WO_INTEGER_U_COMPILED_PROTOTYPE_PASS cases={cases} deferred_calls={deferred} flush_calls={flushes}')


if __name__ == '__main__':
    run()
