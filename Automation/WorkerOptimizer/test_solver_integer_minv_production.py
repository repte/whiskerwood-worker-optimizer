"""Actual compiled Integer-MinV path, checked against the eager production path."""

import copy
import math
import random
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from benchmark_native_relaxation import equal
from solver_integer_minv_dsl import INTEGER_MINV_VARIABLES, load_value
from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import advance_shadows, projected_v
from test_solver_integer_minv_production_model import (
    LabelAudit, SNAPSHOT_FIELDS, compare, label_projection, semantic_snapshot,
)
from test_solver_integer_u import bits, verify_vm_certification
from test_solver_integer_v import fixture_class as uv_fixture
from test_solver_used_label_marker import initialize
from test_solver_used_label_marker_model import reserve_matrix


def fixture_class(writer=None):
    write = writer or BP.write_graph_dsl
    bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_ProductionIntegerMinV_' + str(time.time_ns()),
                   uv_fixture(production=True, writer=writer))
    graphs = {name: BP.add_function_graph(bp, name) for name in
              ('ConfigureProductionIntegerMinV', 'ReadProductionIntegerMinV', 'SeedProductionIntegerMinV',
               'ChangeProductionIntegerMinPhase', 'MaterializeProductionIntegerMinV',
               'SeedProductionIntegerMinScratch')}
    BP.add_function_param(graphs['ConfigureProductionIntegerMinV'], 'Enabled', 'bool', True)
    BP.add_function_param(graphs['ReadProductionIntegerMinV'], 'Index', 'int', True)
    for name, kind in (('DeltaValue', 'float'), ('FreeColumn', 'int'), ('RawUpper', 'float')):
        BP.add_function_param(graphs['ChangeProductionIntegerMinPhase'], name, kind, True)
    for name, kind in (('Raw', 'float'), ('Offset', 'float'), ('Zero', 'float'), ('Birth', 'int'),
                       ('Epoch', 'int'), ('Active', 'bool'), ('Flush', 'int')):
        BP.add_function_param(graphs['SeedProductionIntegerMinV'], name, kind, True)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs['ConfigureProductionIntegerMinV'], '', [])

    def node(ending):
        matches = [name for name in available if name.rsplit('|', 1)[-1].casefold() == ending.casefold()]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    get = lambda name: f'({node("Get" + name)})'
    put = lambda name, value: f'({node("Set" + name)} {value})'
    at = lambda name, index: f'(Utilities|Array|Get(aref) :Array {get(name)} :"Dimension 1" {index})'
    arrays = {'MinV': ('0.0', 'Raw', '7.0'), 'IntegerMinBirth': ('0', 'Birth', '0'),
              'IntegerMinZero': ('0.0', '(* Zero -1.0)', '0.0')}
    seed = '\n'.join(f'(Utilities|Array|Clear {get(name)}) ' + ' '.join(
        f'(Utilities|Array|Add {get(name)} {value})' for value in values) for name, values in arrays.items())
    fields = dict(IntegerMinActive='Active', IntegerMinPrefix='1', IntegerMinOffset='Offset',
                  IntegerMinEpoch='Epoch', IntegerMinFlushCursor='Flush')
    with toolset_registry.tool_raising_exceptions():
        write(graphs['ConfigureProductionIntegerMinV'], f'''(fn ConfigureProductionIntegerMinV (Enabled)
          {put('IntegerMinEnabled', 'Enabled')})''')
        write(graphs['ReadProductionIntegerMinV'], f'''(fn ReadProductionIntegerMinV (Index)
          {load_value(get, put, at, 'Index')})''')
        write(graphs['SeedProductionIntegerMinV'], f'''(fn SeedProductionIntegerMinV (Raw Offset Zero Birth Epoch Active Flush)
          {seed} {' '.join(put(name, value) for name, value in fields.items())}
          (if (not Active)
            (Utilities|Array|Clear {get('IntegerMinBirth')})
            (Utilities|Array|Clear {get('IntegerMinZero')})))''')
        write(graphs['ChangeProductionIntegerMinPhase'], f'''(fn ChangeProductionIntegerMinPhase (DeltaValue FreeColumn RawUpper)
          {put('Delta', 'DeltaValue')} {put('FirstFreeColumn', 'FreeColumn')}
          {put('IntegerMinRawUpper', 'RawUpper')})''')
        write(graphs['MaterializeProductionIntegerMinV'], f'''(fn MaterializeProductionIntegerMinV ()
          (if (== {get('IntegerMinFlushCursor')} 0) {put('IntegerMinFlushCursor', '1')})
          ({node('IntegerMinFlush')}))''')
        write(graphs['SeedProductionIntegerMinScratch'], f'''(fn SeedProductionIntegerMinScratch ()
          {put('NativeValue', '-123.25')})''')
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return bp.generated_class()


def state(obj):
    result = {}
    for name in dict.fromkeys((*SNAPSHOT_FIELDS, *INTEGER_MINV_VARIABLES, 'FirstFreeColumn')):
        value = obj.get_editor_property(name)
        result[name] = value if isinstance(value, (bool, int, float)) else list(value)
    return result


def decoder_probes(obj):
    cases = flushes = 0
    obj.set_editor_property('StepWorkLimit', 1)
    for raw, offset in ((0.0, 0.0), (1.0, 1.0), (-1.0, -1.0), (float(2**50), 1.0),
                        (-float(2**50), -1.0), (math.inf, 1.0)):
        for birth, epoch in ((0, 0), (0, 2), (2, 2)):
            for active in (False, True):
                for flush in (0, 1, 2):
                    obj.call_method('SeedProductionIntegerMinV', args=(raw, offset, 0.0, birth, epoch, active, flush))
                    expected = raw
                    if active and flush < 2:
                        expected = raw - offset
                        if expected == 0.0:
                            expected = -0.0 if birth == epoch else 0.0
                    obj.call_method('ReadProductionIntegerMinV', args=(1,))
                    assert bits(obj.get_editor_property('IntegerMinValue')) == bits(expected), (
                        'Compiled decoder', raw, offset, birth, epoch, active, flush, expected)
                    obj.call_method('ReadProductionIntegerMinV', args=(2,))
                    assert obj.get_editor_property('IntegerMinValue') == 7.0
                    if active and flush == 1:
                        obj.call_method('IntegerMinFlush')
                        assert bits(obj.get_editor_property('MinV')[1]) == bits(expected)
                        assert not obj.get_editor_property('IntegerMinActive')
                        assert obj.get_editor_property('LastStepWork') == 1
                        flushes += 1
                    cases += 1
    return cases, flushes


def solve(obj, matrix, prefix, enabled, limit, implicit=False, dummy=False, cancel=False, negative_zero=False):
    initialize(obj, matrix, True, limit, prefix, dummy, implicit)
    # Initialize intentionally retains this scratch field; compare equal starts,
    # including after cancellation, without changing the production contract.
    obj.call_method('SeedProductionIntegerMinScratch')
    assert obj.get_editor_property('IntegerMinEnabled') is False
    assert obj.get_editor_property('IntegerMinActive') is False
    assert not obj.get_editor_property('IntegerMinBirth')
    assert not obj.get_editor_property('IntegerMinZero')
    obj.call_method('ConfigureProductionIntegerU', args=(True,))
    obj.call_method('ConfigureProductionIntegerMinV', args=(enabled,))
    if negative_zero:
        for row in range(len(matrix) + 1):
            obj.call_method('SeedProductionUZero', args=(row, 0.0))
        for j in range(len(obj.get_editor_property('V'))):
            obj.call_method('SeedIntegerVZero', args=(j, 0.0))
    audit = LabelAudit()
    before = state(obj)
    shadow_u, shadow_v = list(before['U']), list(before['V'])
    pending = 0
    while not before['Done']:
        obj.call_method('Advance')
        after = state(obj)
        advance_shadows(before, after, shadow_u, shadow_v)
        assert equal(projected_u(after), shadow_u), ('Compiled per-call U', before, after)
        assert equal(projected_v(after), shadow_v), ('Compiled per-call V', before, after)
        audit.observe(before, after)
        if after['IntegerMinActive'] and after['IntegerMinEpoch']:
            pending += 1
            if cancel:
                obj.call_method('StopMarker')
                frozen = state(obj)
                obj.call_method('Advance')
                frozen['LastStepWork'] = 0
                assert equal(state(obj), frozen), 'Cancelled lazy representation changed'
                assert equal(projected_u(frozen), shadow_u)
                assert equal(projected_v(frozen), shadow_v)
                return None, pending
        assert audit.stats['work'] < 10000000, 'Compiled solver did not finish'
        before = after
    assert not after['IntegerMinActive'], 'Completed labels were not materialized'
    assert equal(after['U'], shadow_u) and equal(after['V'], shadow_v)
    assert equal(after['MinV'], label_projection(after))
    return (after, copy.deepcopy(audit.events), dict(audit.stats)), pending


def special_phases(old, new, matrix, prefix, limit, changes=None,
                   rejected_deltas=(.125, -.125, float(2**50 + 1))):
    if changes is None:
        changes = ({}, {'Delta': 0.0}, {'Delta': -0.0}, {'Delta': .125}, {'Delta': -.125},
                   {'Delta': float(2**50 + 1)}, {'FirstFreeColumn': 1},
                   {'force_domain_loss': True})
    calls = 0
    for changed in changes:
        results = []
        for obj, enabled in ((old, False), (new, True)):
            initialize(obj, matrix, True, limit, prefix)
            obj.call_method('SeedProductionIntegerMinScratch')
            obj.call_method('ConfigureProductionIntegerU', args=(True,))
            obj.call_method('ConfigureProductionIntegerMinV', args=(True,))
            for _ in range(100000):
                obj.call_method('Advance')
                if (obj.get_editor_property('SolverState') == 6
                        and obj.get_editor_property('Cursor') == 0
                        and obj.get_editor_property('IntegerMinActive')
                        and obj.get_editor_property('IntegerMinEpoch') > 0
                        and not obj.get_editor_property('IntegerMinPhasePrepared')
                        and not obj.get_editor_property('IntegerUPhasePrepared')
                        and obj.get_editor_property('IntegerUFlushMode') == 0
                        and obj.get_editor_property('P')[obj.get_editor_property('J1')] != 0):
                    break
            else:
                raise AssertionError('No genuine pending phase available for VM guard tests')
            before = state(obj)
            labels = label_projection(before)
            if not enabled:
                while obj.get_editor_property('IntegerMinActive'):
                    obj.call_method('MaterializeProductionIntegerMinV')
                obj.call_method('ConfigureProductionIntegerMinV', args=(False,))
                assert equal(list(obj.get_editor_property('MinV')), labels)
            obj.call_method('ChangeProductionIntegerMinPhase', args=(
                changed.get('Delta', before['Delta']), changed.get('FirstFreeColumn', before['FirstFreeColumn']),
                before['IntegerMinDummyBound'] if changed.get('force_domain_loss') else before['IntegerMinRawUpper']))
            before = state(obj)
            shadow_u, shadow_v = projected_u(before), projected_v(before)
            audit = LabelAudit()
            audit.label_epoch = before['ActiveRow']
            audit.label_shadow = list(labels)
            while before['SolverState'] == 6:
                obj.call_method('Advance')
                after = state(obj)
                advance_shadows(before, after, shadow_u, shadow_v)
                assert equal(projected_u(after), shadow_u), ('VM guarded phase U', changed, before, after)
                assert equal(projected_v(after), shadow_v), ('VM guarded phase V', changed, before, after)
                audit.observe(before, after)
                calls += 1
                assert calls < 100000
                before = after
            if enabled and (changed.get('force_domain_loss') or changed.get('FirstFreeColumn') == 1
                            or changed.get('Delta') in rejected_deltas):
                assert not after['IntegerMinActive'], ('Expected bounded flush did not happen', changed)
            results.append(semantic_snapshot(after, label_projection(after), True))
        assert equal(results[0], results[1]), ('Compiled pending phase guard', limit, changed, results)
    return len(changes), calls


def run(writer=None, random_cases=15):
    cls = fixture_class(writer)
    old, new = unreal.new_object(cls), unreal.new_object(cls)
    verify_vm_certification(new)
    decoder_cases, flush_cases = decoder_probes(new)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
                [[-0.0, 0.0], [0.0, -0.0]], [[math.nan, 0.0]], [[math.inf, 0.0]],
                [[float(2**50), .125, -1e20], [float(2**50 + 1), -0.0, 0.0]]]
    rng = random.Random(816731)
    for _ in range(random_cases):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = pending = cancellations = phase_cases = phase_calls = 0
    work_pairs = []
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected, _ = solve(old, matrix, prefix, False, limit, dummy=dummy, negative_zero=index % 5 == 0)
                actual, observed = solve(new, matrix, prefix, True, limit, dummy=dummy, negative_zero=index % 5 == 0)
                compare(actual, expected)
                comparisons += 1
                pending += observed
        for size in (12, 24):
            matrix, quality, coverage, bonus = benchmark_matrices(size)
            first, _ = solve(old, matrix, size, False, limit, implicit=True)
            actual, observed = solve(new, matrix, size, True, limit, implicit=True)
            compare(actual, first)
            pending += observed
            later = reserve_matrix(matrix, first[0]['U'], first[0]['V'], size, quality, coverage, bonus)
            expected, _ = solve(old, later, size, False, limit)
            actual, observed = solve(new, later, size, True, limit)
            compare(actual, expected)
            pending += observed
            work_pairs.append((size, limit, expected[2]['work'], actual[2]['work']))
            stopped, observed = solve(new, later, size, True, limit, cancel=True)
            assert stopped is None and observed > 0
            restarted, _ = solve(new, later, size, True, limit)
            compare(restarted, expected)
            cancellations += 1
            comparisons += 2
            if size == 24:
                count, calls = special_phases(old, new, later, size, limit)
                phase_cases += count
                phase_calls += calls
    assert pending > 0
    assert all(new_work < old_work for _, _, old_work, new_work in work_pairs), work_pairs
    unreal.log(f'WO_INTEGER_MINV_PRODUCTION_VM_PASS comparisons={comparisons} pending_calls={pending} '
               f'decoder_cases={decoder_cases} flush_cases={flush_cases} '
               f'cancellations={cancellations} phase_cases={phase_cases} phase_calls={phase_calls} '
               f'work_pairs={work_pairs}')


if __name__ == '__main__':
    run()
