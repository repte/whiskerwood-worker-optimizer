"""Unsaved production-marker/Upper/Integer-U VM composition versus forced sorts."""

import ast
import copy
from pathlib import Path
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType

from solver_used_label_marker_prototype import render
from test_solver_native_lifecycle_model import emitted
from test_solver_cached_trace import benchmark_matrices
from test_solver_used_label_marker_model import reserve_matrix


def bits(value):
    return struct.pack('!d', float(value))


_tree = ast.parse(Path(__file__).with_name('test_solver_used_label_marker.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[item for item in _tree.body if isinstance(item, ast.FunctionDef)
                             and item.name == 'initialize'], type_ignores=[]), '<shared marker setup>', 'exec'))


def fixture_class():
    sources, symbol = emitted(Path(unreal.Paths.project_dir()) / 'Automation/WorkerOptimizer/generate_solver.py')
    parent = unreal.load_asset('/Game/Mods/WorkerOptimizer/BP_AssignmentSolver')
    child = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_ProductionUpper_' + str(time.time_ns()), parent.generated_class())
    for name, kind in (('UpperProbeForceSorts', 'bool'), ('UpperProbeSorts', 'int')):
        BP.add_variable(child, name, kind)
    names = ('ProbeUpperAdvance', 'ProbeUpperNative', 'ConfigureMarker', 'InitializeMarkerImplicit',
             'SeedMarkerNegativeZero', 'SetProbeMode', 'StopUpper')
    graphs = {name: BP.add_function_graph(child, name) for name in names}
    params = {
        'ConfigureMarker': [('Enabled', 'bool', False), ('Prefix', 'int', False), ('Offsets', 'int', True), ('Columns', 'int', True)],
        'SetProbeMode': [('ForceSorts', 'bool', False), ('Deferred', 'bool', False)],
        'SeedMarkerNegativeZero': [('Index', 'int', False), ('Zero', 'float', False)],
        'InitializeMarkerImplicit': [('Values', 'float', True), ('Workers', 'int', False), ('R', 'int', False),
            ('C', 'int', False), ('Starts', 'int', True), ('Ends', 'int', True), ('Allowed', 'bool', True),
            ('Minima', 'float', True), ('Seconds', 'float', True), ('Winners', 'int', True)],
    }
    for name, items in params.items():
        for param, kind, array in items:
            BP.add_function_param(graphs[name], param, kind, True, ContainerType.ARRAY if array else None)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(child)
    available = BP.find_node_types(graphs['ProbeUpperAdvance'], '', [])

    def node(ending):
        matches = [item for item in available if item.endswith('|' + ending)]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    g = lambda name: f'({node("Get" + name)})'
    s = lambda name, value: f'({node("Set" + name)} {value})'

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, symbol) and str(value).startswith('Variables|Default|'):
            return symbol(node(str(value).rsplit('|', 1)[1]))
        return value

    increment = [symbol('Variables|Default|SetUpperProbeSorts'),
                 [symbol('+'), [symbol('Variables|Default|GetUpperProbeSorts')], 1]]

    def instrument(value):
        if not isinstance(value, list):
            return value
        if len(value) == 1 and str(value[0]) in (
                'Variables|Default|GetUpperGlobalReady', 'Variables|Default|GetUpperPrefixReady'):
            return [symbol('and'), [symbol('not'), [symbol('Variables|Default|GetUpperProbeForceSorts')]], value]
        result = []
        for item in value:
            result.append(instrument(item))
            if (isinstance(item, list) and item and str(item[0]).endswith('SortFloatArray')
                    and any(isinstance(arg, list) and arg and str(arg[0]).endswith('GetNativeMaxScratch') for arg in item)):
                result.append(copy.deepcopy(increment))
        return result

    native = instrument(sources['AdvanceNativeRelaxation'])
    native[0][1] = symbol('ProbeUpperNative')
    defaults = {'ImplicitModes': '3', 'ImplicitMultipliers': '1', 'ImplicitMinimumRows': 'false',
                'ImplicitRealRows': 'true', 'ImplicitFixedWorkers': '-1'}
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs['ProbeUpperNative'], render(resolve(native), symbol))
        BP.write_graph_dsl(graphs['ProbeUpperAdvance'], f'''(fn ProbeUpperAdvance ()
          {s('LastStepWork', '0')} (if {g('Done')} (return))
          (if (<= {g('StepWorkLimit')} 0) {s('Done', 'true')} {s('Succeeded', 'false')} (return))
          (if (== {g('SolverState')} 11) ({node('ProbeUpperNative')}) (else ({node('Advance')}))))''')
        BP.write_graph_dsl(graphs['ConfigureMarker'], f'''(fn ConfigureMarker (Enabled Prefix Offsets Columns)
          {s('NativePlannerTrusted', 'true')} {s('NativeCsrReady', f'(not {g("ImplicitFirstPass")})')}
          {s('NativeRowOffsets', 'Offsets')} {s('NativeColumns', 'Columns')} {s('ImplicitWorkerCount', 'Prefix')}
          ({node('EnableNativeDeadLabels')})
          {s('UpperGlobalReady', 'true')} {s('UpperPrefixReady', 'true')}
          {s('UpperGlobalBound', '-1e20')} {s('UpperPrefixBound', '-1e20')}
          {s('UpperRow', '-99')} {s('UpperWidth', '-99')} {s('UpperPrefixWidth', '-99')}
          {s('UpperProbeSorts', '0')})''')
        BP.write_graph_dsl(graphs['SetProbeMode'], f'''(fn SetProbeMode (ForceSorts Deferred)
          {s('UpperProbeForceSorts', 'ForceSorts')} {s('IntegerUEnabled', 'Deferred')})''')
        BP.write_graph_dsl(graphs['SeedMarkerNegativeZero'], f'''(fn SeedMarkerNegativeZero (Index Zero)
          (if {g('ImplicitFirstPass')}
            (Utilities|Array|SetArrayElem :TargetArray {g('ImplicitScores')} :Index Index :Item (* Zero -1.0))
            (else (Utilities|Array|SetArrayElem :TargetArray {g('Scores')} :Index Index :Item (* Zero -1.0)))))''')
        BP.write_graph_dsl(graphs['StopUpper'], f'(fn StopUpper () {s("Done", "true")})')
        BP.write_graph_dsl(graphs['InitializeMarkerImplicit'], f'''
          (fn InitializeMarkerImplicit (Values Workers R C Starts Ends Allowed Minima Seconds Winners)
            {s('ImplicitWorkerCount', 'Workers')} {s('ImplicitScores', 'Values')}
            {s('ImplicitDummyStarts', 'Starts')} {s('ImplicitDummyEnds', 'Ends')} {s('ImplicitDummyRows', 'Allowed')}
            {s('ImplicitFillBonus', '0.0')} {s('ImplicitCoverageBonus', '0.0')} {s('ImplicitColumnBonus', '0.0')}
            {' '.join(f'(Utilities|Array|Clear {g(name)})' for name in defaults)}
            (for r (range R) {' '.join(f'(Utilities|Array|Add {g(name)} {value})' for name, value in defaults.items())})
            ({node('InitializeImplicitFirstPass')} :RowCount R :ColumnCount C)
            {s('RowMinCost', 'Minima')} {s('RowSecondMinCost', 'Seconds')} {s('RowMinColumn', 'Winners')})''')
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


def snapshot(obj):
    return {name: ([bits(v) for v in obj.get_editor_property(name)] if name in ('U', 'V', 'MinV')
                   else bits(obj.get_editor_property(name)) if name == 'Cur'
                   else list(obj.get_editor_property(name)) if name in ('Assignment', 'P', 'Way')
                   else obj.get_editor_property(name))
            for name in ('Assignment', 'P', 'Way', 'U', 'V', 'MinV', 'Cur', 'Done', 'Succeeded')}


def solve(obj, matrix, limit, prefix, force, deferred, implicit=False, dummy=False):
    initialize(obj, matrix, True, limit, prefix, dummy, implicit)
    obj.call_method('SetProbeMode', args=(force, deferred))
    trace, work = [], 0
    while not obj.get_editor_property('Done'):
        before = obj.get_editor_property('SolverState')
        obj.call_method('ProbeUpperAdvance')
        units = int(obj.get_editor_property('LastStepWork'))
        assert 0 < units <= limit
        work += units
        assert work < 1000000
        if before != 6 and obj.get_editor_property('SolverState') == 6:
            trace.append(tuple(obj.get_editor_property(name) for name in ('ActiveRow', 'I0', 'J0', 'J1'))
                         + (bits(obj.get_editor_property('Delta')),))
    return snapshot(obj), trace, int(obj.get_editor_property('UpperProbeSorts'))


def run():
    cls = fixture_class()
    reference, candidate = unreal.new_object(cls), unreal.new_object(cls)
    comparisons = old_sorts = new_sorts = 0
    specials = [[[-0., 0., -.125], [0., -0., .125]],
        [[1e20, -.125, 0.], [1e20, 1e20, 0.], [1e20, .125, 0.]],
        [[199999999999999.97, -.09, 99999999999999.92, 200000000000000.06],
         [-.05, 200000000000000.06, 200000000000000.1, -.05],
         [.02, -.05, -.01, -.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]]]
    for limit in (1, 3, 64):
        for deferred in (False, True):
            for matrix in specials:
                left = solve(reference, matrix, limit, 1, True, False)
                right = solve(candidate, matrix, limit, 1, False, deferred)
                assert left[:2] == right[:2], ('special', limit, deferred)
                comparisons += 1
            matrix, quality, coverage, bonus = benchmark_matrices(24)
            for implicit in (True, False):
                left = solve(reference, matrix, limit, 24, True, False, implicit)
                right = solve(candidate, matrix, limit, 24, False, deferred, implicit)
                assert left[:2] == right[:2], ('first/reserve', limit, deferred, implicit)
                old_sorts += left[2]; new_sorts += right[2]
                assert right[2] < left[2], ('Upper sort reduction', left[2], right[2])
                comparisons += 1
                if implicit:
                    matrix = reserve_matrix(matrix, list(reference.get_editor_property('U')),
                        list(reference.get_editor_property('V')), 24, quality, coverage, bonus)
    initialize(candidate, specials[0], True, 1, 1)
    candidate.call_method('SetProbeMode', args=(False, True))
    candidate.call_method('StopUpper')
    before = snapshot(candidate)
    candidate.call_method('ProbeUpperAdvance')
    assert snapshot(candidate) == before and candidate.get_editor_property('LastStepWork') == 0
    unreal.log(f'WO_PRODUCTION_UPPER_VM_PASS comparisons={comparisons} max_sorts={old_sorts}->{new_sorts} marker_u_composition=passed')


run()
