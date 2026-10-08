"""Compiled RED draft for full-real refinement reuse and row reconstruction."""

import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from test_planner_fused_matrix import PLANNER_CLASS, expected_pass
from planner_refinement_test_support import refinement_work


FIXTURE_CLASS = None


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def reach_refine(planner):
    for _ in range(100000):
        if planner.get_editor_property("State") == 6:
            return
        assert not planner.get_editor_property("PlanDone"), "Missing refinement phase"
        advance(planner, 1)
    raise AssertionError("Fixture did not reach refinement")


def csr(mask, rows, columns):
    retained, offsets = [], [0]
    for row in range(rows):
        retained.extend(column for column in range(columns) if mask[row * columns + column])
        offsets.append(len(retained))
    return retained, offsets


def published(planner):
    get = planner.get_editor_property
    return (list(get("AllowedEdges")), bits(get("PassScores")),
            list(get("RetainedColumns")), list(get("RetainedRowOffsets")))


def verify_phase(planner, limit, first_ceiling=None, preserve_inputs=True):
    get = planner.get_editor_property
    rows, columns = get("SlotCount"), get("SolveColumns")
    implicit = get("ImplicitFirstPass")
    mask, scores = expected_pass(planner, implicit)
    if not implicit:
        assert bits(get("PassScores")) == bits(scores), "Later input scores must match the legacy formula"
    u, v = list(get("U")), list(get("V"))
    for index, allowed in enumerate(mask):
        if allowed:
            row, column = divmod(index, columns)
            reduced = ((0.0 - scores[index]) - u[row + 1]) - v[column + 1]
            mask[index] = -0.00001 <= reduced <= 0.00001
    scores = [] if implicit else [value if allowed else -1e20 for value, allowed in zip(scores, mask)]
    retained, offsets = csr(mask, rows, columns)
    expected_work = refinement_work(planner)
    before = published(planner)
    work = 0
    while get("State") == 6:
        work += advance(planner, limit)
        if preserve_inputs and get("State") == 6:
            assert published(planner) == before, "A partial reconstructed result became visible"
    assert get("State") == 30
    if first_ceiling is not None:
        # This precedes all candidate-specific assertions in the first fixture.
        assert work <= first_ceiling, (
            "Refinement must reuse equal complete real rows instead of scanning each copy",
            work, first_ceiling, rows, columns)
    assert work == expected_work, ("Exact reconstruction or fallback work", work, expected_work)
    assert list(get("AllowedEdges")) == mask
    assert bits(get("PassScores")) == bits(scores)
    assert list(get("RetainedColumns")) == retained
    assert list(get("RetainedRowOffsets")) == offsets
    assert bits(get("PassRowMinCost")) == bits([1e20] * rows)
    assert bits(get("PassRowSecondMinCost")) == bits([1e20] * rows)
    assert list(get("PassRowMinColumn")) == [1] * rows
    return work, mask, bits(scores), retained, offsets


def start_natural(tied):
    workers = 20
    planner = unreal.new_object(PLANNER_CLASS)
    quality = [0.0] * workers
    for row in range(workers):
        quality[(row + 17) % workers] = float(10000 + row if row % 2 == 0 else row // 2 + 1)
    planner.call_method("StartPlan", args=(
        [100.0 if tied or column == (row + 17) % workers else 1.0
         for row in range(workers) for column in range(workers)],
        [row // 2 for row in range(workers)], [True, False] * 10,
        [building % 5 for building in range(10)], workers, True))
    assert planner.call_method("KeepUnassigned", args=(2, workers, quality))[-1]
    return planner


def natural(tied, limit):
    planner = start_natural(tied)
    phases = []
    for _ in range(200000):
        if planner.get_editor_property("PlanDone"):
            break
        if planner.get_editor_property("State") == 6:
            phases.append(verify_phase(planner, limit, 318 if not phases else None,
                                       preserve_inputs=bool(phases)))
        else:
            advance(planner, limit)
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assert len(phases) >= 4
    assert list(planner.get_editor_property("ExpectedCounts")) == [2, 4, 4, 4, 4]
    assert bits(planner.get_editor_property("ExpectedScores")) == bits([200.0, 400.0, 400.0, 400.0, 400.0])
    assert planner.get_editor_property("BuilderTotal") == (20034.0 if tied else 7.0)
    result = (list(planner.get_editor_property("PlanAssignment")), phases)
    restart(planner, limit)
    return result


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_RefinementCache_" + uuid.uuid4().hex,
                          PLANNER_CLASS)
        prepare = BP.add_function_graph(child, "PrepareRefinement")
        BP.add_function_param(prepare, "InputTier", "int", True)
        BP.add_function_param(prepare, "InputRequired", "bool", True, ContainerType.ARRAY)
        seed = BP.add_function_graph(child, "SeedRefinement")
        params = (("InputScores", "float"), ("InputMask", "bool"), ("InputU", "float"),
                  ("InputV", "float"), ("InputColumns", "int"), ("InputOffsets", "int"),
                  ("InputWinners", "int"), ("InputSecond", "float"), ("InputTemplate", "float"))
        for name, kind in params:
            BP.add_function_param(seed, name, kind, True, ContainerType.ARRAY)
        BP.compile_blueprint(child)

        def setter(graph, name, value):
            ending = "Set" + name
            matches = [node for node in BP.find_node_types(graph, ending, []) if node.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            node = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            assert node is not None, (name, matches)
            return f"({node} {value})"

        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(prepare, "(fn PrepareRefinement (InputTier InputRequired) " +
                               setter(prepare, "Tier", "InputTier") + " " +
                               setter(prepare, "RequiredWorker", "InputRequired") + ")")
            source = "(fn SeedRefinement (InputScores InputMask InputU InputV InputColumns InputOffsets InputWinners InputSecond InputTemplate) "
            for name, value in (("PassScores", "InputScores"), ("AllowedEdges", "InputMask"),
                                ("U", "InputU"), ("V", "InputV"), ("RetainedColumns", "InputColumns"),
                                ("RetainedRowOffsets", "InputOffsets"), ("RowMinColumn", "InputWinners"),
                                ("RowSecondMinCost", "InputSecond"), ("ImplicitFirstPass", "false"),
                                ("SentinelRow", "InputTemplate"),
                                ("RetainedReady", "true"), ("RefineInitialized", "false"),
                                ("BuildIndex", "0"), ("PlanDone", "false"), ("State", "6")):
                source += setter(seed, name, value) + " "
            BP.write_graph_dsl(seed, source + ")")
            BP.compile_blueprint(child, warnings_as_errors=True)
        FIXTURE_CLASS = child.generated_class()
    return FIXTURE_CLASS


def seeded(case, limit):
    workers, rows = 8, 8
    planner = unreal.new_object(fixture_class())
    raw = [1.0] * (rows * workers)
    if case == "negative":
        for row in range(rows):
            raw[row * workers + row] = -1.0
    elif case == "nonuniform":
        raw = [float(column + 1) for row in range(rows) for column in range(workers)]
    planner.call_method("StartPlan", args=(raw, [row // 2 for row in range(rows)],
                                           [True, False] * 4, [4, 4, 0, 0], workers, True))
    if case == "fixed":
        assert planner.call_method("RequireFixedSlots", args=([0] + [-1] * (rows - 1),))
    reach_refine(planner)
    columns = planner.get_editor_property("SolveColumns")
    results = []
    # Same score class and row U, but a changed required set must invalidate reuse.
    for required_columns in ({0, 2}, {1, 3}):
        required = [column in required_columns for column in range(columns)]
        planner.call_method("PrepareRefinement", args=(4 if case == "nonuniform" else 3, required))
        mask, _ = expected_pass(planner, True)
        if case == "partial":
            for row in range(rows):
                mask[row * columns + row] = False
        # Set the old mask before asking the independent later-pass score oracle.
        retained, offsets = csr(mask, rows, columns)
        coverage = planner.get_editor_property("CoverageBonus")
        u = [0.0] + [0.0 - coverage if row % 2 == 0 else 0.0 for row in range(rows)]
        v = [0.0] * (columns + 1)
        template = [] if case == "missing_template" else [-1e20] * columns
        planner.call_method("SeedRefinement", args=(
            [-1e20] * (rows * columns), mask, u, v, retained, offsets, [1] * rows, [1e20] * rows, template))
        _, scores = expected_pass(planner, False)
        costs = [[0.0 - value for value in scores[row * columns:(row + 1) * columns]] for row in range(rows)]
        winners = [row.index(min(row)) + 1 for row in costs]
        second = [sorted(row)[1] if len(row) > 1 else 1e20 for row in costs]
        planner.call_method("SeedRefinement", args=(scores, mask, u, v, retained, offsets, winners, second, template))
        result = verify_phase(planner, limit, preserve_inputs=case != "missing_template")
        if case in {"negative", "partial", "fixed"}:
            # These rows lack a complete real prefix; no full-row cache may hide visits.
            old_real = sum(mask[row * columns + column] for row in range(rows) for column in range(workers))
            assert result[0] >= 2 + workers + 2 * rows + old_real
        elif case == "nonuniform":
            # Four active nonuniform rows scan fully; two lower-tier cache misses remain.
            assert result[0] >= 2 + workers + 2 * rows + (rows // 2 + 2) * workers
        elif case == "missing_template":
            assert result[0] == len(retained) + sum(a == b for a, b in zip(offsets, offsets[1:])) + 2
        results.append(result)
    assert results[0][1] != results[1][1], "Required-column change must alter the tight real masks"
    restart(planner, limit)
    return results


def restart(planner, limit):
    planner.call_method("StartPlan", args=([9.0], [0], [True], [2], 1, True))
    for _ in range(10000):
        if planner.get_editor_property("PlanDone"):
            break
        advance(planner, limit)
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assert list(planner.get_editor_property("PlanAssignment")) == [0]


def cancel(limit):
    planner = start_natural(False)
    reach_refine(planner)
    for _ in range(5):
        advance(planner, 1)
    before = published(planner)
    planner.call_method("FailPlan")
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    assert published(planner) == before
    restart(planner, limit)


for tied in (False, True):
    assert natural(tied, 1) == natural(tied, 3) == natural(tied, 64)
for case in ("constant", "negative", "partial", "nonuniform", "fixed", "missing_template"):
    assert seeded(case, 1) == seeded(case, 3) == seeded(case, 64)
for limit in (1, 3, 64):
    cancel(limit)
unreal.log("WO_PLANNER_REFINEMENT_CACHE_TESTS_PASS: mixed/tied row reuse, all-pass legacy mask/CSR/score bits, negative/nonuniform/partial/fixed fallbacks, required-set invalidation, atomic output, budgets1/3/64 and cancel/restart")
