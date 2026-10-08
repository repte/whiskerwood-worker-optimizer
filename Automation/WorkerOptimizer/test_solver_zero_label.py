"""Compiled differential tests for certified non-improving zero labels."""

import random
import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


ROOT = "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver"
production = unreal.load_asset(ROOT)
assert "ZeroLabelBound" in BP.list_variables(production), "Solver lacks the exact zero-label relaxation certificate"
production_class = production.generated_class()
fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_ZeroLabelReference_" + uuid.uuid4().hex, production_class)
graph = BP.add_function_graph(fixture, "SetCertificate")
BP.add_function_param(graph, "Enabled", "bool", True)
BP.compile_blueprint(fixture)
setters = [node for node in BP.find_node_types(graph, "SetZeroLabelBound", []) if node.endswith("|SetZeroLabelBound")]
preferred = "Variables|Default|SetZeroLabelBound"
setter = preferred if preferred in setters else setters[0] if len(setters) == 1 else None
assert setter is not None, setters
with toolset_registry.tool_raising_exceptions():
    BP.write_graph_dsl(graph, f"(fn SetCertificate (Enabled) ({setter} Enabled))")
    BP.compile_blueprint(fixture, warnings_as_errors=True)
reference_class = fixture.generated_class()


def bits(values):
    return [struct.pack("<d", float(value)) for value in values]


def snapshot(solver):
    result = {name: solver.get_editor_property(name) for name in (
        "Done", "Succeeded", "SolverState", "Cursor", "ActiveRow", "J0", "J1", "I0",
        "NonpositiveV", "FirstFreeColumn", "BestColumnFree", "LastStepWork",
    )}
    for name in ("Assignment", "P", "Way", "Used", "UsedColumns"):
        result[name] = list(solver.get_editor_property(name))
    for name in ("U", "V", "MinV"):
        result[name] = bits(solver.get_editor_property(name))
    for name in ("Cur", "Delta", "RowPotential"):
        result[name] = bits([solver.get_editor_property(name)])
    return result


def compare(matrix, mask, limit):
    rows, columns = len(matrix), len(matrix[0])
    enabled, disabled = unreal.new_object(production_class), unreal.new_object(reference_class)
    for solver in (enabled, disabled):
        solver.set_editor_property("StepWorkLimit", limit)
        solver.call_method("Initialize", args=([float(value) for row in matrix for value in row], rows, columns))
        solver.call_method("RestrictDummies", args=(mask,))
        assert not solver.get_editor_property("ZeroLabelBound"), "Initialize retained a stale certificate"
    bound = rows * columns + rows * (rows + 1) * (3 * (rows + columns) + 10) + 4 * (rows + columns) + 20
    work, skipped_labels = 0, 0
    for _ in range(bound + 1):
        if enabled.get_editor_property("Done"):
            break
        if enabled.get_editor_property("SolverState") == 5:
            if enabled.get_editor_property("ZeroLabelBound"):
                assert enabled.get_editor_property("J0") != 0
                first = enabled.get_editor_property("Cursor")
                end = min(enabled.get_editor_property("Width") + 1, first + limit)
                used, labels = enabled.get_editor_property("Used"), enabled.get_editor_property("MinV")
                skipped_labels += sum(not used[column] and labels[column] == 0.0 for column in range(first, end))
            disabled.call_method("SetCertificate", args=(False,))
            assert not disabled.get_editor_property("ZeroLabelBound")
        enabled.call_method("Advance")
        disabled.call_method("Advance")
        assert snapshot(enabled) == snapshot(disabled), (matrix, mask, limit, work)
        last = int(enabled.get_editor_property("LastStepWork"))
        assert 0 < last <= limit
        work += last
        assert work <= bound
    assert enabled.get_editor_property("Done") and disabled.get_editor_property("Done")
    disabled.call_method("SetCertificate", args=(True,))
    disabled.call_method("Initialize", args=([1.0], 1, 1))
    assert not disabled.get_editor_property("ZeroLabelBound"), "Initialize failed to reset a true certificate"
    return skipped_labels


hits = 0
for size in (4, 8, 16):
    for reserve_score in (0.0, -0.0, 1.0, 1.03):
        matrix = [[100.0 if column == row else -0.0 if column >= size else 1.0
                   for column in range(size + 2)] for row in range(size)]
        matrix += [[reserve_score] * size + [-1e20] * 2 for _ in range(2)]
        for limit in (1, 3, 64):
            hits += compare(matrix, [False] * len(matrix), limit)
assert hits > 0, "Fixtures never exercised a certified zero label"

rng = random.Random(93219)
values = [-1e20, -100.0, -0.09, -0.0, 0.0, 0.02, 1.03, 7.0,
          99999999999999.92, 200000000000000.06]
for _ in range(100):
    rows, columns = rng.randrange(1, 7), rng.randrange(0, 7)
    matrix = [[rng.choice(values) for _ in range(columns)] for _ in range(rows)]
    mask = [rng.choice([False, True]) for _ in range(rows)]
    compare(matrix, mask, rng.choice((1, 3, 64)))
unreal.log(f"WO_SOLVER_ZERO_LABEL_TESTS_PASS: {hits} certified labels; 36 reserve-like and 100 random full-state bitwise comparisons, budgets1/3/64, reuse reset")
