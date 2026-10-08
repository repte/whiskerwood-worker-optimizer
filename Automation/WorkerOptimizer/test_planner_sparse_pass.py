"""Later scoring passes preserve dense results while visiting retained edges only."""

import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_test_cost_probe import supports_implicit
from test_planner_fused_matrix import expected_pass


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
        assert not planner.get_editor_property("PlanDone"), "Fixture ended before its target phase"
        advance(planner, 1)
    raise AssertionError("Fixture did not reach its target phase")


def sparse_work(planner, mask):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    priorities, buildings = list(get("Priorities")), list(get("SlotBuildings"))
    tier, strict = get("Tier"), get("StrictMode")
    patches = 0
    for row in range(rows):
        priority = priorities[buildings[row]]
        mode = 0
        if priority >= 0 and tier >= 0:
            mode = int(priority == tier) if strict else 2
        elif priority < 0 and tier < 0:
            mode = 3
        row_mask = mask[row * columns:(row + 1) * columns]
        full_real_template = mode == 0 and workers > 0 and all(row_mask[:workers])
        patches += sum(row_mask[workers:] if full_real_template else row_mask)
    return columns + 1 + rows + patches + 1


def verify_sparse_work():
    planner = unreal.new_object(PLANNER_CLASS)
    scores = [100.0 if worker == (row + 17) % 6 else 1.0
              for row in range(6) for worker in range(6)]
    planner.call_method("StartPlan", args=(
        scores, [0, 0, 1, 1, 2, 2], [True, False] * 3, [2, 2, 2], 6, True))
    assert planner.call_method("KeepUnassigned", args=(1, 6, [1.0, 90.0, 2.0, 80.0, 3.0, 100.0]))[-1]
    reach(planner, lambda item: item.get_editor_property("State") == 4
          and item.get_editor_property("Tier") == -1)
    mask = list(planner.get_editor_property("AllowedEdges"))
    rows, columns = planner.get_editor_property("SlotCount"), planner.get_editor_property("SolveColumns")
    expected_work = sparse_work(planner, mask)
    assert expected_work < len(mask) + 1 and len(mask) + 1 <= 64
    work = advance(planner, 64)
    assert planner.get_editor_property("State") == 5
    assert work == expected_work, (
        "Later BuildPass must build row templates and patch retained edges only",
        work, expected_work, rows, columns)


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_SparsePassInputs_" + uuid.uuid4().hex,
                            PLANNER_CLASS)
        graph = BP.add_function_graph(fixture, "SeedRefinement")
        params = (("InputPass", "float"), ("InputMask", "bool"), ("InputU", "float"),
                  ("InputV", "float"), ("InputRequired", "bool"))
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

        source = "(fn SeedRefinement (InputPass InputMask InputU InputV InputRequired) "
        for name, value in (("PassScores", "InputPass"), ("AllowedEdges", "InputMask"),
                            ("U", "InputU"), ("V", "InputV"), ("RequiredWorker", "InputRequired"),
                            ("RetainedReady", "false"),
                            ("RefineInitialized", "false"),
                            ("FirstPass", "false"), ("BuildIndex", "0"), ("Tier", "4"),
                            ("PlanDone", "false"), ("PlanSucceeded", "false"),
                            ("Done", "true"), ("Succeeded", "true"), ("State", "6")):
            source += setter(name, value) + " "
        if supports_implicit(PLANNER_CLASS):
            source += setter("ImplicitFirstPass", "false") + " "
        source += ")"
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        FIXTURE_CLASS = fixture.generated_class()
    return FIXTURE_CLASS


def dense_expected(planner, mask):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    buildings, priorities = list(get("SlotBuildings")), list(get("Priorities"))
    minimum, required, base = list(get("Minimum")), list(get("RequiredWorker")), list(get("BaseScores"))
    fill, coverage, column_bonus = get("FillBonus"), get("CoverageBonus"), get("ColumnBonus")
    tier, strict = get("Tier"), get("StrictMode")
    scores = []
    for row in range(rows):
        priority = priorities[buildings[row]]
        for column in range(columns):
            score = -1e20
            if mask[row * columns + column]:
                score = 0.0
                if column < workers:
                    raw = base[row * workers + column]
                    if priority >= 0 and tier >= 0:
                        if not strict:
                            score = fill + raw * (priority + 1)
                        elif priority == tier:
                            score = fill + raw
                    if priority < 0 and tier < 0:
                        score = raw
                    if minimum[row]:
                        score = score + coverage
                if required[column]:
                    score = score + column_bonus
            scores.append(score)
    minima, winners = [], []
    for row in range(rows):
        costs = [0.0 - value for value in scores[row * columns:(row + 1) * columns]]
        winner = min(range(columns), key=costs.__getitem__)
        minima.append(costs[winner])
        winners.append(winner + 1)
    return scores, minima, winners


def verify_seeded_refinement(limit, all_forbidden, primitive=False):
    planner = unreal.new_object(fixture_class())
    planner.call_method("StartPlan", args=(
        [10.0 if row == worker else 1.0 for row in range(4) for worker in range(4)],
        [0, 0, 1, 1], [True, False, True, False], [4, 0], 4, True))
    reach(planner, lambda item: item.get_editor_property("State") == 5)
    rows, columns = planner.get_editor_property("SlotCount"), planner.get_editor_property("SolveColumns")
    assert (rows, columns) == (4, 6)
    before_mask, _ = expected_pass(planner, True)
    retained = set() if all_forbidden else {(0, 2), (1, 1), (1, 3), (1, 4), (3, 0), (3, 2), (3, 5)}
    potentials = [0.0, 0.0, -2.0, 0.0, 0.0, -3.0, 0.0]
    scores = []
    expected_mask = []
    for row in range(rows):
        for column in range(columns):
            allowed = before_mask[row * columns + column]
            keep = allowed and (row, column) in retained
            expected_mask.append(keep)
            scores.append((0.0 - potentials[column + 1]) + (0.0 if keep else 1.0) if allowed else -1e20)
    planner.call_method("SeedRefinement", args=(scores, before_mask, [0.0] * (rows + 1),
                                                potentials, [False] * columns))
    def phase_step():
        if primitive:
            planner.call_method("PolicyStep")
            return 1
        return advance(planner, limit)

    refine_work = 0
    while planner.get_editor_property("State") == 6:
        refine_work += phase_step()
    assert planner.get_editor_property("State") == 30
    assert refine_work == rows * columns + 2
    assert list(planner.get_editor_property("AllowedEdges")) == expected_mask
    forbidden_scores = [value if allowed else -1e20 for value, allowed in zip(scores, expected_mask)]
    assert bits(planner.get_editor_property("PassScores")) == bits(forbidden_scores)
    retained_columns, offsets = [], [0]
    for row in range(rows):
        retained_columns.extend(column for column in range(columns) if expected_mask[row * columns + column])
        offsets.append(len(retained_columns))
    assert list(planner.get_editor_property("RetainedColumns")) == retained_columns
    assert list(planner.get_editor_property("RetainedRowOffsets")) == offsets
    assert bits(planner.get_editor_property("PassRowMinCost")) == bits([1e20] * rows)
    assert list(planner.get_editor_property("PassRowMinColumn")) == [1] * rows
    reach(planner, lambda item: item.get_editor_property("State") == 4)
    assert planner.get_editor_property("Tier") == 0
    assert list(planner.get_editor_property("RequiredWorker")) == [False, True, False, False, True, False]
    expected, minima, winners = dense_expected(planner, expected_mask)
    second_minima = [sorted(0.0 - score for score in expected[row * columns:(row + 1) * columns])[1]
                     if columns > 1 else 1e20 for row in range(rows)]
    expected_work = sparse_work(planner, expected_mask)
    build_work = 0
    while planner.get_editor_property("State") == 4:
        build_work += phase_step()
    assert planner.get_editor_property("State") == 5
    assert build_work == expected_work, (build_work, expected_work)
    assert bits(planner.get_editor_property("PassScores")) == bits(expected)
    assert list(planner.get_editor_property("AllowedEdges")) == expected_mask
    for name in ("PassRowMinCost", "RowMinCost"):
        assert bits(planner.get_editor_property(name)) == bits(minima), name
    for name in ("PassRowSecondMinCost", "RowSecondMinCost"):
        assert bits(planner.get_editor_property(name)) == bits(second_minima), name
    for name in ("PassRowMinColumn", "RowMinColumn"):
        assert list(planner.get_editor_property(name)) == winners, name
    return bits(expected), bits(minima), winners, build_work


verify_sparse_work()
for all_forbidden in (False, True):
    assert (verify_seeded_refinement(1, all_forbidden, primitive=True)
            == verify_seeded_refinement(1, all_forbidden)
            == verify_seeded_refinement(3, all_forbidden)
            == verify_seeded_refinement(64, all_forbidden))
unreal.log("WO_PLANNER_SPARSE_PASS_TESTS_PASS: retained-edge work, exact dense score/cache bits, row offsets, empty rows, nonzero first columns, RequiredWorker changes, primitive/budgets1/3/64")
