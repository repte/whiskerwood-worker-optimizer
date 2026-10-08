"""Compiled RED: later refinement must visit and compact only retained edges."""

import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_refinement_test_support import refinement_work


PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
FIXTURE_CLASS = None


def bits(values):
    return [struct.pack("!d", float(value)) for value in values]


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def reach(planner, predicate):
    for _ in range(100000):
        if predicate(planner):
            return
        assert not planner.get_editor_property("PlanDone"), "Fixture ended before refinement"
        advance(planner, 1)
    raise AssertionError("Fixture did not reach refinement")


def csr(mask, rows, columns):
    retained, offsets = [], [0]
    for row in range(rows):
        retained.extend(column for column in range(columns) if mask[row * columns + column])
        offsets.append(len(retained))
    return retained, offsets


def expected(scores, mask, u, v, rows, columns):
    scores, mask = list(scores), list(mask)
    for index, allowed in enumerate(mask):
        if allowed:
            row, column = divmod(index, columns)
            reduced = ((0.0 - scores[index]) - u[row + 1]) - v[column + 1]
            if not -0.00001 <= reduced <= 0.00001:
                mask[index], scores[index] = False, -1e20
    retained, offsets = csr(mask, rows, columns)
    return scores, mask, retained, offsets


def verify_phase(planner, limit, primitive=False):
    get = planner.get_editor_property
    rows, columns = get("SlotCount"), get("SolveColumns")
    old_columns, old_offsets = list(get("RetainedColumns")), list(get("RetainedRowOffsets"))
    target = expected(get("PassScores"), get("AllowedEdges"), get("U"), get("V"), rows, columns)
    wanted = refinement_work(planner)
    work = 0
    while get("State") == 6:
        if primitive:
            planner.call_method("PolicyStep")
            work += 1
        else:
            work += advance(planner, limit)
    assert get("State") == 30, "Refinement must yield before required-column processing"
    assert work == wanted, (
        "Later refinement must use its bounded reconstruction or sparse fallback contract",
        work, wanted, rows, columns, len(old_columns))
    scores, mask, retained, offsets = target
    assert bits(get("PassScores")) == bits(scores)
    assert list(get("AllowedEdges")) == mask
    assert list(get("RetainedColumns")) == retained
    assert list(get("RetainedRowOffsets")) == offsets
    assert bits(get("PassRowMinCost")) == bits([1e20] * rows)
    assert bits(get("PassRowSecondMinCost")) == bits([1e20] * rows)
    assert list(get("PassRowMinColumn")) == [1] * rows
    assert get("RetainedReady"), "Readiness must survive later refinement"
    return bits(scores), mask, retained, offsets, work


def verify_work_bound():
    planner = unreal.new_object(PLANNER_CLASS)
    scores = [100.0 if worker == (row + 17) % 8 else 1.0
              for row in range(8) for worker in range(8)]
    planner.call_method("StartPlan", args=(
        scores, [0, 0, 1, 1, 2, 2, 3, 3], [True, False] * 4, [4, 4, 2, 0], 8, True))
    assert planner.call_method("KeepUnassigned", args=(1, 8, [1.0] * 8))[-1]
    reach(planner, lambda item: item.get_editor_property("State") == 6
          and not item.get_editor_property("ImplicitFirstPass"))
    assert len(planner.get_editor_property("RetainedColumns")) < planner.get_editor_property("MatrixCells")
    # This work assertion runs before looking up any newly introduced field.
    verify_phase(planner, 64)


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_SparseRefineInputs_" + uuid.uuid4().hex,
                            PLANNER_CLASS)
        graph = BP.add_function_graph(fixture, "SeedRefinement")
        params = (("InputPass", "float"), ("InputMask", "bool"), ("InputU", "float"),
                  ("InputV", "float"), ("InputColumns", "int"), ("InputOffsets", "int"))
        for name, kind in params:
            BP.add_function_param(graph, name, kind, True, ContainerType.ARRAY)
        BP.compile_blueprint(fixture)

        def setter(name, value):
            ending = "Set" + name
            matches = [node for node in BP.find_node_types(graph, ending, []) if node.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            node = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            assert node is not None, (name, matches)
            return f"({node} {value})"

        source = "(fn SeedRefinement (InputPass InputMask InputU InputV InputColumns InputOffsets) "
        for name, value in (("PassScores", "InputPass"), ("AllowedEdges", "InputMask"),
                            ("U", "InputU"), ("V", "InputV"), ("RetainedColumns", "InputColumns"),
                            ("RetainedRowOffsets", "InputOffsets"), ("RetainedReady", "true"),
                            ("RefineInitialized", "false"),
                            ("ImplicitFirstPass", "false"), ("FirstPass", "false"),
                            ("BuildIndex", "0"), ("PlanDone", "false"), ("PlanSucceeded", "false"),
                            ("Done", "true"), ("Succeeded", "true"), ("State", "6")):
            source += setter(name, value) + " "
        source += ")"
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        FIXTURE_CLASS = fixture.generated_class()
    return FIXTURE_CLASS


def seeded(case, limit, primitive=False):
    planner = unreal.new_object(fixture_class())
    planner.call_method("StartPlan", args=(
        [10.0 if row == worker else 1.0 for row in range(4) for worker in range(4)],
        [0, 0, 1, 1], [True, False, True, False], [4, 0], 4, True))
    reach(planner, lambda item: item.get_editor_property("State") == 5)
    rows, columns = planner.get_editor_property("SlotCount"), planner.get_editor_property("SolveColumns")
    assert (rows, columns) == (4, 6)
    positions = (
        {(1, 2), (1, 5), (3, 1), (3, 4)},
        set(),
        {(0, 5), (2, 1), (2, 2)},
        {(row, column) for row in range(rows) for column in range(columns)},
    )[case]
    mask = [(row, column) in positions for row in range(rows) for column in range(columns)]
    values = [-0.0, 0.0, 0.00001, -0.00001, 0.00001000000001, -0.00001000000001,
              1.03, 200000000000000.06]
    scores = [values[index % len(values)] if allowed else -1e20 for index, allowed in enumerate(mask)]
    retained, offsets = csr(mask, rows, columns)
    planner.call_method("SeedRefinement", args=(
        scores, mask, [0.0] * (rows + 1), [0.0] * (columns + 1), retained, offsets))
    result = verify_phase(planner, limit, primitive)
    # Reuse must invalidate CSR readiness, including after an all-empty compaction.
    planner.call_method("StartPlan", args=([1.0], [0], [True], [2], 1, True))
    assert not planner.get_editor_property("RetainedReady")
    return result


verify_work_bound()
for case in range(4):
    assert (seeded(case, 1, True) == seeded(case, 1)
            == seeded(case, 3) == seeded(case, 64))
unreal.log("WO_PLANNER_SPARSE_REFINEMENT_TESTS_PASS: retained-edge work, bit-exact scores/masks/caches, in-place CSR order, empty rows, tolerance boundaries, primitive/budgets1/3/64, reuse")
