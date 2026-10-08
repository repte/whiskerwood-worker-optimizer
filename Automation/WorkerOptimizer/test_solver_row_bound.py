"""Exact row-minimum certificates must avoid redundant first relaxations."""

import itertools
import random
import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


disabled_class = None


def reference_class():
    global disabled_class
    if disabled_class is None:
        parent = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_RowBoundReference_" + uuid.uuid4().hex, parent)
        graph = BP.add_function_graph(fixture, "DisableCertificate")
        BP.compile_blueprint(fixture)
        setters = [node for node in BP.find_node_types(graph, "SetNonpositiveV", []) if node.endswith("|SetNonpositiveV")]
        preferred = "Variables|Default|SetNonpositiveV"
        setter = preferred if preferred in setters else setters[0] if len(setters) == 1 else None
        assert setter is not None, setters
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, f"(fn DisableCertificate () ({setter} false))")
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        disabled_class = fixture.generated_class()
    return disabled_class


def execute(matrix, mask, limit=64, disable_certificate=False):
    rows = len(matrix)
    columns = len(matrix[0]) if matrix else 0
    cls = reference_class() if disable_certificate else unreal.load_class(
        None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
    solver = unreal.new_object(cls)
    solver.set_editor_property("StepWorkLimit", limit)
    solver.call_method("Initialize", args=([float(value) for row in matrix for value in row], rows, columns))
    solver.call_method("RestrictDummies", args=(mask,))
    if disable_certificate:
        solver.call_method("DisableCertificate")
        assert not solver.get_editor_property("NonpositiveV"), (
            "Reference subclass did not disable the production certificate", solver.get_class().get_name())
    work = 0
    bound = rows * columns + rows * (rows + 1) * (3 * (rows + columns) + 10) + 4 * (rows + columns) + 20
    for _ in range(bound + 1):
        if solver.get_editor_property("Done"):
            break
        solver.call_method("Advance")
        last = int(solver.get_editor_property("LastStepWork"))
        assert 0 < last <= limit, (last, limit)
        work += last
        assert work <= bound
    assert solver.get_editor_property("Done")
    if disable_certificate:
        assert not solver.get_editor_property("NonpositiveV"), "Production solver re-enabled the disabled certificate"
    return solver, list(solver.get_editor_property("Assignment")), work


def run():
    size = 80
    matrix = [[-1.0 if column == (row + 17) % size else -100.0 for column in range(size)] for row in range(size)]
    solver, assignment, unique_work = execute(matrix, [False] * size)
    assert solver.get_editor_property("Succeeded") and assignment == [(row + 17) % size for row in range(size)]
    target = size * size + 60 * size
    assert unique_work <= target, ("Certified unique row minima repeated full relaxation scans", unique_work, target)
    solver, assignment, tie_work = execute([[0.0] * size for _ in range(size)], [False] * size)
    assert solver.get_editor_property("Succeeded") and assignment == list(range(size))
    assert tie_work <= target, ("Certified free tied minima repeated full relaxation scans", tie_work, target)

    # A false certificate must route through the original Hungarian search.
    small = [[-1.0 if column == row else -100.0 for column in range(8)] for row in range(8)]
    _, enabled, enabled_work = execute(small, [False] * 8, limit=1)
    _, disabled, disabled_work = execute(small, [False] * 8, limit=1, disable_certificate=True)
    assert enabled == disabled == list(range(8)) and disabled_work > enabled_work, (
        "Disabled-certificate reference diverged", enabled, disabled, enabled_work, disabled_work)

    fixtures = (
        ([[10.0, 0.0], [10.0, 9.0]], [False, False]),
        ([[10.0, 9.0], [10.0, 0.0]], [False, False]),
        ([[-1.0], [-2.0]], [True, True]),
        ([[-1.0], [3.0]], [True, False]),
        ([[], []], [True, True]),
    )
    for matrix, mask in fixtures:
        solver, assignment, _ = execute(matrix, mask, limit=1)
        assert solver.get_editor_property("Succeeded")
        values = []
        for candidate in itertools.product(range(-1, len(matrix[0])), repeat=len(matrix)):
            used = [column for column in candidate if column >= 0]
            if len(used) != len(set(used)) or any(column < 0 and not mask[row] for row, column in enumerate(candidate)):
                continue
            values.append(sum(matrix[row][column] for row, column in enumerate(candidate) if column >= 0))
        actual = sum(matrix[row][column] for row, column in enumerate(assignment) if column >= 0)
        assert actual == max(values), (matrix, mask, assignment)

    rng = random.Random(92150)
    values = [-1e20, -100.0, -0.09, -0.0, 0.0, 0.02, 1.03, 7.0,
              99999999999999.92, 200000000000000.06]
    for case in range(100):
        rows, columns = rng.randrange(1, 7), rng.randrange(0, 7)
        matrix = [[rng.choice(values) for _ in range(columns)] for _ in range(rows)]
        mask = [rng.choice([False, True]) for _ in range(rows)]
        enabled, enabled_assignment, _ = execute(matrix, mask, limit=1)
        disabled, disabled_assignment, _ = execute(matrix, mask, limit=1, disable_certificate=True)
        assert enabled.get_editor_property("Succeeded") == disabled.get_editor_property("Succeeded"), case
        assert enabled_assignment == disabled_assignment, (case, matrix, mask)
        assert list(enabled.get_editor_property("P")) == list(disabled.get_editor_property("P")), case
        for name in ("U", "V"):
            enabled_bits = [struct.pack("<d", float(value)) for value in enabled.get_editor_property(name)]
            disabled_bits = [struct.pack("<d", float(value)) for value in disabled.get_editor_property(name)]
            assert enabled_bits == disabled_bits, (case, name, matrix, mask)
    unreal.log(f"WO_SOLVER_ROW_BOUND_TESTS_PASS: unique80={unique_work}, ties80={tie_work}, target={target}; exact fallback, 100 bitwise differential cases and limit1")


run()
