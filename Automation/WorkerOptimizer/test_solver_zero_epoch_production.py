"""Actual VM checks for certified zero-epoch materialization elision.

The baseline clears only RawExact before each production Advance. Integer U/V,
MinV, native selection and all ordinary arithmetic remain enabled on both sides.
An additional eager reference checks the complete solve independently.
"""

from collections import Counter
import copy
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from benchmark_native_relaxation import equal
from solver_integer_minv_dsl import store_improvement
from solver_integer_u_prototype import projected_u
from solver_integer_v_prototype import advance_shadows, projected_v
from test_solver_dyadic_eighths_production import fixture_class as dyadic_fixture, SolveAdapter
from test_solver_integer_minv_production import solve, special_phases, state
from test_solver_integer_minv_production_model import LabelAudit, compare, label_projection
from test_solver_scale8_candidate_model import fractional_matrix
from test_solver_cached_trace import benchmark_matrices
from test_solver_used_label_marker import initialize
from test_solver_used_label_marker_model import reserve_matrix


PROOF = 'IntegerMinRawExact'


def fixture_class(writer=None):
    write = writer or BP.write_graph_dsl
    bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_ZeroEpochProduction_' + str(time.time_ns()),
                   dyadic_fixture(writer))
    names = ('ClearZeroEpochProof', 'SeedZeroEpochBits', 'ProbeZeroEpochStore', 'FlushZeroEpochForTest')
    graphs = {name: BP.add_function_graph(bp, name) for name in names}
    for name, kind in (('Scenario', 'int'), ('Eighths', 'bool'), ('Zero', 'float')):
        BP.add_function_param(graphs['SeedZeroEpochBits'], name, kind, True)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs['ClearZeroEpochProof'], '', [])

    def node(ending):
        matches = [value for value in available if value.casefold().endswith('|' + ending.casefold())]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    get = lambda name: f'({node("Get" + name)})'
    put = lambda name, value: f'({node("Set" + name)} {value})'
    at = lambda name, index: f'(Utilities|Array|Get(aref) :Array {get(name)} :"Dimension 1" {index})'
    set_at = lambda name, index, value: f'(Utilities|Array|SetArrayElem :TargetArray {get(name)} :Index {index} :Item {value})'
    arrays = {'MinV': ('Zero', '5.0', '7.0'), 'IntegerMinZero': ('Zero', '5.0', 'Zero'),
              'IntegerMinBirth': ('0', '0', '0'), 'Used': ('true', 'false', 'false')}
    seed_arrays = '\n'.join(f'(Utilities|Array|Clear {get(name)}) ' + ' '.join(
        f'(Utilities|Array|Add {get(name)} {value})' for value in values) for name, values in arrays.items())
    fields = dict(IntegerMinEnabled='true', IntegerMinActive='true', IntegerMinPrefix='2',
                  IntegerMinOffset='0.0', IntegerMinEpoch='0', IntegerMinFlushCursor='0',
                  IntegerMinPhasePrepared='false', IntegerMinGathering='false',
                  IntegerMinRawExact='true', DyadicEighthsEnabled='Eighths', Cur='(* Zero -1.0)')
    with toolset_registry.tool_raising_exceptions():
        write(graphs['ClearZeroEpochProof'], f'(fn ClearZeroEpochProof () {put(PROOF, "false")})')
        write(graphs['SeedZeroEpochBits'], f'''(fn SeedZeroEpochBits (Scenario Eighths Zero)
          {seed_arrays} {' '.join(put(name, value) for name, value in fields.items())}
          (if (== Scenario 0)
            {put(PROOF, 'false')} {set_at('MinV', '1', 'Zero')}
            {set_at('IntegerMinZero', '1', '(* Zero -1.0)')})
          (if (== Scenario 2)
            {put(PROOF, 'false')} {put('IntegerMinEpoch', '2')}
            {set_at('MinV', '1', '(* Zero -1.0)')} {set_at('IntegerMinZero', '1', '(* Zero -1.0)')})
          (if (== Scenario 3) {put('Cur', '0.1')})
          (if (== Scenario 4) {put('Cur', '-1125899906842625.0')}))''')
        write(graphs['ProbeZeroEpochStore'], f'''(fn ProbeZeroEpochStore ()
          (bind j (+ 0 1)) {store_improvement(get, put, at, set_at, node('FloortoInteger64'))})''')
        write(graphs['FlushZeroEpochForTest'], f'''(fn FlushZeroEpochForTest ()
          (if (== {get('IntegerMinFlushCursor')} 0) {put('IntegerMinFlushCursor', '1')})
          ({node('IntegerMinFlush')}))''')
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return bp.generated_class()


class Adapter(SolveAdapter):
    def __init__(self, obj, mode, suppress=False, eager=False):
        super().__init__(obj, mode, eager)
        self.suppress = suppress
        self.counts = Counter()

    def call_method(self, name, args=()):
        if name == 'ConfigureProductionIntegerMinV' and self.eager:
            args = (False,)
        before = None
        if name == 'Advance':
            if self.suppress:
                self.obj.call_method('ClearZeroEpochProof')
            before = state(self.obj)
            assert not self.suppress or before[PROOF] is False
        result = super().call_method(name, args)
        if name in ('Initialize', 'InitializeImplicitFirstPass', 'InitializeMarkerImplicit'):
            assert self.obj.get_editor_property(PROOF) is False, 'Proof leaked across initialization'
        if name == 'Advance':
            after = state(self.obj)
            if after[PROOF]:
                assert after['IntegerMinActive'] and after['IntegerMinEpoch'] == 0
                assert after['IntegerMinOffset'] == 0.0
                assert equal(after['MinV'], label_projection(after)), 'Compiled raw-exact proof is unsound'
                self.counts['proof_calls'] += 1
            if before['IntegerMinActive'] and not after['IntegerMinActive']:
                remaining = before['IntegerMinPrefix'] - max(before['IntegerMinFlushCursor'], 1) + 1
                if self.suppress:
                    # A phase fence must prevent reacquiring proof and flushing
                    # it inside this same Advance call.
                    assert after['LastStepWork'] == min(before['StepWorkLimit'], remaining), (
                        'Suppressed proof did not retain the original bounded flush', before, after)
                elif before[PROOF] and before['IntegerMinEpoch'] == 0 and remaining > 1:
                    assert after['LastStepWork'] == 1
                    self.counts['fast_flushes'] += 1
        return result


def bit_cases(obj):
    cases = 0
    obj.set_editor_property('StepWorkLimit', 1)
    for mode in (False, True):
        for scenario in range(5):
            obj.call_method('SeedZeroEpochBits', args=(scenario, mode, 0.0))
            if scenario in (1, 3, 4):
                before = list(obj.get_editor_property('MinV'))
                obj.call_method('ProbeZeroEpochStore')
                if scenario == 1:
                    assert equal(obj.get_editor_property('MinV')[1], -0.0), 'Native store normalized raw -0'
                    assert obj.get_editor_property(PROOF) is True
                    assert equal(list(obj.get_editor_property('MinV')), label_projection(state(obj)))
                else:
                    assert obj.get_editor_property('IntegerMinFlushCursor') == 1
                    assert equal(list(obj.get_editor_property('MinV')), before), 'Rejected store mutated labels'
            obj.call_method('FlushZeroEpochForTest')
            expected = -0.0 if scenario in (0, 1) else (0.0 if scenario == 2 else 5.0)
            assert equal(obj.get_editor_property('MinV')[1], expected), ('VM zero payload', mode, scenario)
            assert obj.get_editor_property('LastStepWork') == 1
            if scenario in (0, 2):
                assert obj.get_editor_property('IntegerMinActive') is True, 'Unproven flush was elided'
                obj.call_method('FlushZeroEpochForTest')
            assert obj.get_editor_property('IntegerMinActive') is False
            assert obj.get_editor_property(PROOF) is False
            assert obj.get_editor_property('IntegerMinValue') == 7.0, 'Final decoder scratch changed'
            cases += 1
    return cases


def cancel_at_proof(adapter, matrix, prefix, limit, implicit):
    initialize(adapter, matrix, True, limit, prefix, implicit=implicit)
    adapter.call_method('SeedProductionIntegerMinScratch')
    adapter.call_method('ConfigureProductionIntegerU', args=(True,))
    adapter.call_method('ConfigureProductionIntegerMinV', args=(True,))
    before = state(adapter)
    shadow_u, shadow_v = list(before['U']), list(before['V'])
    audit = LabelAudit()
    for _ in range(100000):
        adapter.call_method('Advance')
        after = state(adapter)
        advance_shadows(before, after, shadow_u, shadow_v)
        assert equal(projected_u(after), shadow_u) and equal(projected_v(after), shadow_v)
        audit.observe(before, after)
        if after[PROOF]:
            adapter.call_method('StopMarker')
            frozen = state(adapter)
            adapter.call_method('Advance')
            frozen['LastStepWork'] = 0
            assert equal(state(adapter), frozen), 'Cancelled zero-epoch proof changed'
            return
        assert not after['Done'], 'Fixture never acquired zero-epoch proof'
        before = after
    raise AssertionError('No bounded zero-epoch cancellation point')


def run(writer=None):
    cls = fixture_class(writer)
    eager_obj, old_obj, new_obj = (unreal.new_object(cls) for _ in range(3))
    zeros = bit_cases(new_obj)
    matrices = [
        [[10.125, 9.375, 0.0], [10.125, 8.125, 0.0], [10.125, 7.875, 0.0]],
        [[-0.0, 0.0], [0.0, -0.0]],
        [[10.1, 9.0625, 0.0], [10.125, 8.1, 0.0], [10.375, 7.0625, 0.0]],
    ]
    comparisons = cancellations = phases = phase_calls = fast_flushes = proof_calls = 0
    work_pairs = []
    for limit in (1, 3, 64):
        for mode in (False, True):
            eager = Adapter(eager_obj, mode, eager=True)
            old = Adapter(old_obj, mode, suppress=True)
            new = Adapter(new_obj, mode)
            for dummy in (False, True):
                for matrix in matrices:
                    prefix = len(matrix[0]) - 1
                    expected, _ = solve(eager, matrix, prefix, False, limit, dummy=dummy, negative_zero=True)
                    baseline, _ = solve(old, matrix, prefix, True, limit, dummy=dummy, negative_zero=True)
                    actual, _ = solve(new, matrix, prefix, True, limit, dummy=dummy, negative_zero=True)
                    compare(actual, expected)
                    compare(actual, baseline)
                    comparisons += 1
            matrix, quality, coverage, bonus = (fractional_matrix(12) if mode else benchmark_matrices(12))
            first, _ = solve(eager, matrix, 12, False, limit, implicit=True)
            baseline, _ = solve(old, matrix, 12, True, limit, implicit=True)
            actual, _ = solve(new, matrix, 12, True, limit, implicit=True)
            compare(actual, first)
            compare(actual, baseline)
            work_pairs.append((mode, limit, 'first', baseline[2]['work'], actual[2]['work']))
            cancel_at_proof(new, matrix, 12, limit, True)
            restarted, _ = solve(new, matrix, 12, True, limit, implicit=True)
            compare(restarted, first)
            cancellations += 1
            later = reserve_matrix(matrix, first[0]['U'], first[0]['V'], 12, quality, coverage, bonus)
            expected, _ = solve(eager, later, 12, False, limit)
            baseline, _ = solve(old, later, 12, True, limit)
            actual, _ = solve(new, later, 12, True, limit)
            compare(actual, expected)
            compare(actual, baseline)
            work_pairs.append((mode, limit, 'reserve', baseline[2]['work'], actual[2]['work']))
            stopped, pending = solve(new, later, 12, True, limit, cancel=True)
            assert stopped is None and pending > 0
            restarted, _ = solve(new, later, 12, True, limit)
            compare(restarted, expected)
            cancellations += 1
            rejected = (.1, .0625) if mode else (.125, -.125)
            changes = ({'Delta': rejected[0]}, {'Delta': rejected[1]}, {'force_domain_loss': True})
            count, calls = special_phases(old, new, later, 12, limit,
                                         changes=changes, rejected_deltas=rejected)
            phases += count
            phase_calls += calls
            comparisons += 2
            fast_flushes += new.counts['fast_flushes']
            proof_calls += new.counts['proof_calls']
    assert all(actual < baseline for _, _, _, baseline, actual in work_pairs), (
        'Certified zero-epoch flush still materializes every real label', work_pairs)
    assert fast_flushes > 0 and proof_calls > 0 and cancellations == 12
    unreal.log(f'WO_ZERO_EPOCH_PRODUCTION_VM_PASS comparisons={comparisons} zeros={zeros} '
               f'guard_phases={phases} phase_calls={phase_calls} cancellations={cancellations} '
               f'proof_calls={proof_calls} fast_flushes={fast_flushes} work_pairs={work_pairs}')


if __name__ == '__main__':
    run()
