"""Direct compiled production UV deferral; no candidate solver graph is authored."""

import math
import random

import unreal

from test_solver_integer_u import verify_vm_certification
from test_solver_integer_v import fixture_class, solve, special_phases
from test_solver_used_label_marker_model import reserve_matrix


def run(writer=None):
    cls = fixture_class(production=True, writer=writer)
    old, new = unreal.new_object(cls), unreal.new_object(cls)
    verify_vm_certification(new)
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]], [[0., 0.], [0., 0.]],
                [[math.nan, 0.]], [[math.inf, 0.]], [[float(2**49) + .125, 1.], [float(2**49) - .125, 0.]]]
    rng = random.Random(729584)
    for _ in range(30):
        rows, cols = rng.randint(1, 6), rng.randint(1, 8)
        matrices.append([[rng.choice([-1e20, -.125, -0.0, 0., 1., 7., float(2**50), float(2**50 + 1)])
                          for _ in range(cols)] for _ in range(rows)])
    cases = pending = 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for index, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[index % 4]
                expected = solve(old, matrix, False, limit, prefix, dummy, production=True)
                actual = solve(new, matrix, True, limit, prefix, dummy, production=True)
                assert actual[0] == expected[0], ('production eager versus UV', limit, dummy, index)
                cases += 1
                pending += actual[1]
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix, quality, coverage, bonus = benchmark_matrices(size)
            expected = solve(old, matrix, False, limit, size, implicit=True, production=True)
            actual = solve(new, matrix, True, limit, size, implicit=True, production=True)
            assert actual[0] == expected[0], ('implicit', size, limit)
            later = reserve_matrix(matrix, list(old.get_editor_property('U')), list(old.get_editor_property('V')),
                                   size, quality, coverage, bonus)
            expected = solve(old, later, False, limit, size, production=True)
            actual = solve(new, later, True, limit, size, production=True)
            assert actual[0] == expected[0], ('reserve', size, limit)
            pending += actual[1]
            stopped = solve(new, later, True, limit, size, cancel=True, production=True)
            assert stopped[0] is None and stopped[1] > 0
            assert solve(new, later, True, limit, size, production=True)[0] == expected[0]
            cases += 2
    phases = special_phases(old, new, production=True)
    assert cases == 228 and pending > 0
    unreal.log(f'WO_INTEGER_V_PRODUCTION_TESTS_PASS cases={cases} pending_calls={pending} special_phases={phases}')


if __name__ == '__main__':
    run()
