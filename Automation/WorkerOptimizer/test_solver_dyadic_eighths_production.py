"""Actual VM checks of the immutable dyadic mode against eager arithmetic."""

import math
import random
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from solver_integer_minv_dsl import check_value
from test_solver_integer_minv_production import fixture_class as minv_fixture, solve, special_phases
from test_solver_integer_minv_production_model import compare
from test_solver_scale8_candidate_model import fractional_matrix
from test_solver_used_label_marker_model import reserve_matrix


MODE = 'DyadicEighthsEnabled'
LIMIT = float(2**48)


def fixture_class(writer=None):
    write = writer or BP.write_graph_dsl
    bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_DyadicEighths_' + str(time.time_ns()),
                   minv_fixture(writer))
    configure = BP.add_function_graph(bp, 'ConfigureDyadicEighthsForTest')
    BP.add_function_param(configure, 'Enabled', 'bool', True)
    probe = BP.add_function_graph(bp, 'ProbeDyadicCertificates')
    BP.add_function_param(probe, 'InputValue', 'float', True)
    BP.add_function_param(probe, 'Eighths', 'bool', True)
    BP.compile_blueprint(bp)
    available = BP.find_node_types(configure, '', [])

    def node(ending):
        matches = [value for value in available if value.lower().endswith('|' + ending.lower())]
        for preferred in ('Variables|Default|' + ending, 'CallFunction|' + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    get = lambda name: '(' + node('Get' + name) + ')'
    put = lambda name, value: '(' + node('Set' + name) + ' ' + value + ')'
    with toolset_registry.tool_raising_exceptions():
        write(configure, f'''(fn ConfigureDyadicEighthsForTest (Enabled)
          {put(MODE, 'Enabled')})''')
        write(probe, f'''(fn ProbeDyadicCertificates (InputValue Eighths)
          {put(MODE, 'Eighths')}
          {put('IntegerUProbe', 'InputValue')} ({node('IntegerUCheckValue')})
          {put('IntegerMinProbe', 'InputValue')} {check_value(get, put, node('FloortoInteger64'))})''')
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return bp.generated_class()


class SolveAdapter:
    """Configure only between Initialize and Advance; keep the old VM oracle."""
    def __init__(self, obj, mode, eager=False):
        self.obj, self.mode, self.eager = obj, mode, eager

    def get_editor_property(self, name):
        return self.obj.get_editor_property(name)

    def set_editor_property(self, name, value):
        return self.obj.set_editor_property(name, value)

    def call_method(self, name, args=()):
        if name == 'ConfigureProductionIntegerU' and self.eager:
            args = (False,)
        result = self.obj.call_method(name, args=args)
        if name in ('Initialize', 'InitializeImplicitFirstPass', 'InitializeMarkerImplicit'):
            assert self.obj.get_editor_property(MODE) is False, 'Mode did not reset on reuse'
        if name == 'ConfigureProductionIntegerMinV':
            self.obj.call_method('ConfigureDyadicEighthsForTest', args=(self.mode,))
        if name == 'Advance':
            assert self.obj.get_editor_property(MODE) is self.mode, 'Mode changed inside a solve'
        return result


def guard_cases(obj):
    values = (-math.inf, math.nan, math.inf, -0.0, 0.0, .125, -.125, .375,
              .0625, .1, -.1, LIMIT, -LIMIT, LIMIT - .125, -LIMIT + .125,
              math.nextafter(LIMIT, math.inf), math.nextafter(-LIMIT, -math.inf),
              math.nextafter(LIMIT, 0.0), float(2**49), float(2**50), float(2**50 + 1))
    for mode in (False, True):
        for value in values:
            obj.call_method('ProbeDyadicCertificates', args=(value, mode))
            expected = (math.isfinite(value) and abs(value) <= (LIMIT if mode else 2**50)
                        and (value * (8.0 if mode else 1.0)).is_integer())
            for field in ('IntegerUCertified', 'IntegerMinCheck'):
                assert obj.get_editor_property(field) is expected, ('VM certificate', field, mode, value)
    return 2 * len(values)


def run(writer=None):
    cls = fixture_class(writer)
    left, right = unreal.new_object(cls), unreal.new_object(cls)
    guards = guard_cases(right)
    matrices = [
        [[10.125, 9.125, 0.], [10.125, 8.125, 0.], [10.125, 7.125, 0.]],
        [[-0.0, 0.0], [0.0, -0.0]], [[math.nan, 0.]], [[math.inf, 0.]],
        [[LIMIT, LIMIT - .125, 0.], [-LIMIT, .125, 0.]],
        [[float(2**49), .125, 0.], [float(2**49) - .125, .1, 0.]],
        [[math.nextafter(LIMIT, math.inf), .0625], [.1, -0.0]],
    ]
    rng = random.Random(800148)
    for _ in range(10):
        rows, cols = rng.randint(1, 5), rng.randint(1, 7)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., .125, .375, .0625, .1,
                                     7., LIMIT, LIMIT - .125, float(2**49)])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = pending = cancellations = phase_cases = phase_calls = 0
    work_pairs = []
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                for mode in (False, True):
                    expected, _ = solve(SolveAdapter(left, False, eager=True), matrix, prefix, False,
                                        limit, dummy=dummy, negative_zero=index % 3 == 0)
                    actual, count = solve(SolveAdapter(right, mode), matrix, prefix, True,
                                          limit, dummy=dummy, negative_zero=index % 3 == 0)
                    compare(actual, expected)
                    comparisons += 1
                    pending += count
        for size in (12, 24):
            matrix, quality, coverage, bonus = fractional_matrix(size)
            old, new = SolveAdapter(left, False, eager=True), SolveAdapter(right, True)
            first, _ = solve(old, matrix, size, False, limit, implicit=True)
            actual, count = solve(new, matrix, size, True, limit, implicit=True)
            compare(actual, first)
            pending += count
            later = reserve_matrix(matrix, first[0]['U'], first[0]['V'], size, quality, coverage, bonus)
            expected, _ = solve(old, later, size, False, limit)
            actual, count = solve(new, later, size, True, limit)
            compare(actual, expected)
            work_pairs.append((size, limit, expected[2]['work'], actual[2]['work']))
            pending += count
            stopped, count = solve(new, later, size, True, limit, cancel=True)
            assert stopped is None and count > 0
            restarted, _ = solve(new, later, size, True, limit)
            compare(restarted, expected)
            cancellations += 1
            comparisons += 2
            if size == 24:
                rejected = (.1, .0625, math.nextafter(LIMIT, math.inf))
                changes = ({}, {'Delta': 0.0}, {'Delta': -0.0}, {'Delta': .125}, {'Delta': -.125},
                           *({'Delta': value} for value in rejected), {'Delta': LIMIT}, {'Delta': -LIMIT},
                           {'FirstFreeColumn': 1}, {'force_domain_loss': True})
                cases, calls = special_phases(SolveAdapter(left, True), new, later, size, limit,
                                             changes=changes, rejected_deltas=rejected)
                phase_cases += cases
                phase_calls += calls
    assert pending > 0 and phase_cases == 36 and cancellations == 6
    unreal.log(f'WO_DYADIC_EIGHTHS_VM_PASS comparisons={comparisons} guards={guards} '
               f'pending={pending} phase_cases={phase_cases} phase_calls={phase_calls} '
               f'cancellations={cancellations} work_pairs={work_pairs}')


if __name__ == '__main__':
    run()
