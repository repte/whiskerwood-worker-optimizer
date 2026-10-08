"""Compiled production integer-U and dead-label composition, with eager oracle."""

import math
import random
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from solver_integer_u_prototype import projected_u
from test_solver_integer_u import bits, equal_u, state, verify_vm_certification
from test_solver_used_label_marker import fixture_class as marker_fixture, initialize, result
from test_solver_used_label_marker_model import reserve_matrix


def fixture_class():
    parent = marker_fixture(production=True)
    bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_ProductionIntegerU_' + str(time.time_ns()), parent)
    graphs = {name: BP.add_function_graph(bp, name) for name in
              ('ConfigureProductionIntegerU', 'ProbeIntegerUValue', 'SeedProductionUZero')}
    BP.add_function_param(graphs['ConfigureProductionIntegerU'], 'Enabled', 'bool', True)
    BP.add_function_param(graphs['ProbeIntegerUValue'], 'InputValue', 'float', True)
    BP.add_function_param(graphs['SeedProductionUZero'], 'Row', 'int', True)
    BP.add_function_param(graphs['SeedProductionUZero'], 'Zero', 'float', True)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs['ConfigureProductionIntegerU'], '', [])

    def node(ending):
        matches = [value for value in available if value.endswith('|' + ending)]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graphs['ConfigureProductionIntegerU'], f'''(fn ConfigureProductionIntegerU (Enabled)
          ({node('SetIntegerUEnabled')} Enabled))''')
        BP.write_graph_dsl(graphs['ProbeIntegerUValue'], f'''(fn ProbeIntegerUValue (InputValue)
          ({node('SetIntegerUProbe')} InputValue) ({node('IntegerUCheckValue')}))''')
        BP.write_graph_dsl(graphs['SeedProductionUZero'], f'''(fn SeedProductionUZero (Row Zero)
          (Utilities|Array|SetArrayElem :TargetArray ({node('GetU')}) :Index Row :Item (* Zero -1.0)))''')
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return bp.generated_class()


def solve(obj, matrix, enabled, limit, prefix, dummy=False, implicit=False, negative_zero=False, cancel_at=None):
    initialize(obj, matrix, enabled, limit, prefix, dummy, implicit)
    assert not obj.get_editor_property('IntegerUEnabled')
    assert not obj.get_editor_property('IntegerUActive')
    assert not obj.get_editor_property('IntegerUOffsets')
    assert obj.get_editor_property('IntegerUFlushMode') == 0
    obj.call_method('ConfigureProductionIntegerU', args=(enabled,))
    if negative_zero:
        for row in range(len(matrix) + 1):
            obj.call_method('SeedProductionUZero', args=(row, 0.0))
        assert all(bits(value) == bits(-0.0) for value in obj.get_editor_property('U'))
    shadow = list(obj.get_editor_property('U'))
    trace, label_epoch = [], 0
    calls = deferred = flushes = 0
    while not obj.get_editor_property('Done'):
        before = state(obj)
        row = int(obj.get_editor_property('ActiveRow'))
        j0 = int(obj.get_editor_property('J0'))
        if cancel_at is not None and calls == cancel_at:
            obj.call_method('StopMarker')
            frozen = state(obj)
            obj.call_method('Advance')
            frozen['LastStepWork'] = 0
            assert state(obj) == frozen
            equal_u(projected_u(frozen), shadow)
            return None, trace, deferred, flushes
        obj.call_method('Advance')
        after = state(obj)
        if before['SolverState'] == 6 and before['IntegerUFlushMode'] == 0:
            rejected = after['IntegerUFlushMode'] == 1 and not before['IntegerUPhasePrepared']
            if before['Delta'] != 0.0 and not rejected:
                terminal = before['P'][before['J1']] == 0
                columns = (before['UsedColumns'][before['Cursor']:after['Cursor']] if terminal else
                           [j for j in range(before['Cursor'], after['Cursor']) if j in before['UsedColumns']])
                for column in columns:
                    target = before['P'][column]
                    shadow[target] = shadow[target] + before['Delta']
        equal_u(projected_u(after), shadow)
        deferred += any(bits(a) != bits(b) for a, b in zip(after['U'], shadow))
        flushes += before['IntegerUFlushMode'] != 0
        assert 0 < after['LastStepWork'] <= limit
        if before['SolverState'] != 6 and after['SolverState'] == 6:
            if before['SolverState'] == 5 and j0 == 0:
                label_epoch = row
            active = int(obj.get_editor_property('ActiveRow'))
            live = []
            if label_epoch == active:
                labels = list(obj.get_editor_property('MinV'))
                used = list(obj.get_editor_property('Used'))
                live = [(j, bits(labels[j])) for j in range(after['Width'] + 1) if not used[j]]
            trace.append((active, int(obj.get_editor_property('I0')), int(obj.get_editor_property('J0')),
                          after['J1'], bits(after['Delta']), live))
        calls += 1
        assert calls < 100000
    equal_u(list(obj.get_editor_property('U')), shadow)
    return result(obj), trace, deferred, flushes


def run():
    cls = fixture_class()
    baseline, candidate = unreal.new_object(cls), unreal.new_object(cls)
    verify_vm_certification(candidate)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
                [[-0.0, 0.0], [0.0, -0.0]], [[math.nan, 0.]], [[math.inf, 0.]],
                [[float(2**49) + .125, 1.], [float(2**49) - .125, 0.]]]
    rng = random.Random(158972)
    for _ in range(25):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    cases = deferred = flushes = 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                old = solve(baseline, matrix, False, limit, prefix, dummy, negative_zero=index % 5 == 0)
                new = solve(candidate, matrix, True, limit, prefix, dummy, negative_zero=index % 5 == 0)
                assert old[:2] == new[:2], ('combined production result/selection trace', limit, dummy, index)
                assert not baseline.get_editor_property('NativeDeadLabels')
                cases += 1
                deferred += new[2]
                flushes += new[3]
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix, quality, coverage, bonus = benchmark_matrices(size)
            old = solve(baseline, matrix, False, limit, size, implicit=True)
            new = solve(candidate, matrix, True, limit, size, implicit=True)
            assert old[:2] == new[:2], ('implicit', size, limit)
            deferred += new[2]
            flushes += new[3]
            later = reserve_matrix(matrix, list(baseline.get_editor_property('U')),
                list(baseline.get_editor_property('V')), size, quality, coverage, bonus)
            old = solve(baseline, later, False, limit, size)
            new = solve(candidate, later, True, limit, size)
            assert old[:2] == new[:2], ('reserve', size, limit)
            deferred += new[2]
            flushes += new[3]
            cases += 2
    for cancel_at in (5, 20, 40):
        solve(candidate, matrices[0], True, 1, 3, cancel_at=cancel_at)
        assert solve(candidate, matrices[0], True, 3, 3)[:2] == solve(baseline, matrices[0], False, 3, 3)[:2]
    assert cases == 198 and deferred > 0 and flushes > 0, (cases, deferred, flushes)
    unreal.log(f'WO_INTEGER_U_PRODUCTION_TESTS_PASS cases={cases} deferred_calls={deferred} flush_calls={flushes}')


if __name__ == '__main__':
    run()
