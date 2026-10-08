"""Compiled RED for the exact first-refinement real-column certificate."""

import math
import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_test_cost_probe import probe_class
from planner_refinement_test_support import implicit_refinement_work


PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
FIXTURE_CLASS = None
EPSILON = 0.00001


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def reach_refinement(planner):
    for _ in range(100000):
        if planner.get_editor_property("State") == 6:
            assert planner.get_editor_property("ImplicitFirstPass")
            return
        assert not planner.get_editor_property("PlanDone"), "Missing first refinement"
        advance(planner, 1)
    raise AssertionError("Fixture did not reach first refinement")


def legacy_scores(planner):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    base = list(get("ImplicitScores"))
    fill, coverage, bonus = get("ImplicitFillBonus"), get("ImplicitCoverageBonus"), get("ImplicitColumnBonus")
    modes, multipliers = list(get("ImplicitModes")), list(get("ImplicitMultipliers"))
    minimum, real, dummy = (list(get(name)) for name in
                            ("ImplicitMinimumRows", "ImplicitRealRows", "ImplicitDummyRows"))
    fixed, starts, ends = (list(get(name)) for name in
                          ("ImplicitFixedWorkers", "ImplicitDummyStarts", "ImplicitDummyEnds"))
    scores = []
    for row in range(rows):
        for column in range(columns):
            value = -1e20
            if column < workers:
                if real[row] and base[row * workers + column] >= 0.0:
                    raw = base[row * workers + column]
                    value = 0.0
                    if modes[row] == 1:
                        value = fill + raw
                    elif modes[row] == 2:
                        value = fill + (raw * multipliers[row])
                    elif modes[row] == 3:
                        value = raw
                    if minimum[row]:
                        value = value + coverage
                    if column == fixed[row]:
                        value = value + bonus
            elif dummy[row] and starts[row] <= column < ends[row]:
                value = 0.0
            scores.append(value)
    return scores


def reference(planner):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    scores = legacy_scores(planner)
    u, v = list(get("U")), list(get("V"))
    mask, retained, offsets = [], [], [0]
    for row in range(rows):
        for column in range(columns):
            value = scores[row * columns + column]
            reduced = ((0.0 - value) - u[row + 1]) - v[column + 1]
            allowed = value >= 0.0 and -EPSILON <= reduced <= EPSILON
            mask.append(allowed)
            if allowed:
                retained.append(column)
        offsets.append(len(retained))
    maximum = max(v[1:workers + 1]) if workers else None
    winners, second = list(get("RowMinColumn")), list(get("RowSecondMinCost"))
    certified = 0
    for row in range(rows):
        if get("ImplicitRealRows")[row]:
            singleton = (workers > 0 and 1 <= winners[row] <= workers
                         and ((second[row] - u[row + 1]) - maximum) > EPSILON)
            certified += singleton
    return mask, retained, offsets, implicit_refinement_work(planner), certified, maximum


def verify_refinement(planner, limit, primitive=False, natural=False):
    get = planner.get_editor_property
    target = reference(planner)
    mask, retained, offsets, expected_work, certified, maximum = target
    rows, workers = get("SlotCount"), get("WorkerCount")
    work = 0
    while get("State") == 6:
        if primitive:
            planner.call_method("PolicyStep")
            work += 1
        else:
            work += advance(planner, limit)
    assert get("State") == 30
    if natural:
        assert certified == 12, ("Fixture must certify every productive real row", certified)
        # Old assets fail for actual work before any new-field lookup.
        assert work <= workers + 2 * rows + 3 * workers + 8, (
            "First refinement must certify nonwinning real columns without visiting them",
            work, expected_work, rows, workers)
    assert work == expected_work, (work, expected_work, certified, maximum)
    assert list(get("AllowedEdges")) == mask
    assert list(get("RetainedColumns")) == retained
    assert list(get("RetainedRowOffsets")) == offsets
    assert not list(get("PassScores"))
    assert get("RetainedReady") and get("RefineMaxVReady")
    if workers:
        # A maximum's zero sign is irrelevant to this monotone numeric bound.
        assert get("RefineMaxRealV") == maximum
    assert bits(get("PassRowMinCost")) == bits([1e20] * rows)
    assert bits(get("PassRowSecondMinCost")) == bits([1e20] * rows)
    assert list(get("PassRowMinColumn")) == [1] * rows
    return mask, retained, offsets, work


def natural(limit):
    workers = 12
    planner = unreal.new_object(PLANNER_CLASS)
    scores = [100.0 if worker == (row + 17) % workers else 1.0
              for row in range(workers) for worker in range(workers)]
    quality = [0.0] * workers
    for row in range(workers):
        quality[(row + 17) % workers] = float(10000 + row if row % 2 == 0 else row // 2 + 1)
    planner.call_method("StartPlan", args=(
        scores, [row // 2 for row in range(workers)], [True, False] * 6, [2] * 6, workers, True))
    assert planner.call_method("KeepUnassigned", args=(3, workers, quality))[-1]
    reach_refinement(planner)
    result = verify_refinement(planner, limit, natural=True)
    restart(planner, limit)
    return result


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_RefineCertificate_" + uuid.uuid4().hex,
                            probe_class(PLANNER_CLASS))
        graph = BP.add_function_graph(fixture, "SeedCertificate")
        params = (("InputU", "float", True), ("InputV", "float", True),
                  ("InputWinners", "int", True), ("InputSecond", "float", True),
                  ("InputWorkers", "int", False), ("InputReal", "bool", True),
                  ("InputBase", "float", True))
        for name, kind, array in params:
            BP.add_function_param(graph, name, kind, True, ContainerType.ARRAY if array else None)
        BP.compile_blueprint(fixture)

        def setter(name, value):
            ending = "Set" + name
            matches = [node for node in BP.find_node_types(graph, ending, []) if node.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            node = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            assert node is not None, (name, matches)
            return f"({node} {value})"

        source = "(fn SeedCertificate (InputU InputV InputWinners InputSecond InputWorkers InputReal InputBase) "
        for name, value in (("U", "InputU"), ("V", "InputV"), ("RowMinColumn", "InputWinners"),
                            ("RowSecondMinCost", "InputSecond"), ("WorkerCount", "InputWorkers"),
                            ("ImplicitWorkerCount", "InputWorkers"), ("ImplicitRealRows", "InputReal"),
                            ("ImplicitScores", "InputBase"), ("ImplicitFirstPass", "true"),
                            ("RetainedReady", "false"), ("RefineInitialized", "false"),
                            ("BuildIndex", "0"), ("PlanDone", "false"), ("State", "6")):
            source += setter(name, value) + " "
        source += ")"
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        FIXTURE_CLASS = fixture.generated_class()
    return FIXTURE_CLASS


def seeded(name, limit, primitive=False):
    planner = unreal.new_object(fixture_class())
    planner.call_method("StartPlan", args=([0.0] * 6, [0, 1], [True, True], [4, 0], 3, True))
    if name == "fixed":
        assert planner.call_method("RequireFixedSlots", args=([0, -1],))
    reach_refinement(planner)
    planner.call_method("SeedTestBonuses", args=(0.0, 0.0, 0.0))
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    scores = legacy_scores(planner)
    costs = [[0.0 - value for value in scores[row * columns:(row + 1) * columns]] for row in range(rows)]
    winners = [row.index(min(row)) + 1 for row in costs]
    second = [sorted(row)[1] if len(row) > 1 else 1e20 for row in costs]
    u, v = [0.0] * (rows + 1), [0.0] * (columns + 1)
    real, base = list(get("ImplicitRealRows")), list(get("ImplicitScores"))
    if name in {"below", "at", "above"}:
        threshold = {"below": math.nextafter(EPSILON, 0.0), "at": EPSILON,
                     "above": math.nextafter(EPSILON, math.inf)}[name]
        u[1:] = [0.0 - threshold] * rows
    elif name in {"unknown", "outside", "v0"}:
        u[1:] = [-1.0] * rows
        if name == "unknown":
            winners = [0] * rows
        elif name == "outside":
            winners = [workers + 1] * rows
        else:
            v[0] = 1e20
    elif name == "positive_v":
        v[1:workers + 1] = [0.1, 0.25, -0.5]
        u[1:] = [-0.25002] * rows
    elif name == "zero_workers":
        workers, real, base = 0, [False] * rows, []
    elif name == "signed_zero":
        u[1:] = [-0.0] * rows
        v[1:workers + 1] = [-0.0, 0.0, -0.0]
    planner.call_method("SeedCertificate", args=(u, v, winners, second, workers, real, base))
    result = verify_refinement(planner, limit, primitive)
    restart(planner, limit)
    return result


def restart(planner, limit):
    planner.call_method("StartPlan", args=([9.0], [0], [True], [2], 1, True))
    assert not planner.get_editor_property("RetainedReady")
    for _ in range(10000):
        if planner.get_editor_property("PlanDone"):
            break
        advance(planner, limit)
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assert list(planner.get_editor_property("PlanAssignment")) == [0]


assert natural(1) == natural(3) == natural(64)
for case in ("below", "at", "above", "unknown", "outside", "v0", "positive_v",
             "ties", "fixed", "zero_workers", "signed_zero"):
    assert (seeded(case, 1, True) == seeded(case, 1)
            == seeded(case, 3) == seeded(case, 64))
unreal.log("WO_PLANNER_REFINE_CERTIFICATE_TESTS_PASS: exact legacy masks/CSR, real-maxV work bound, tolerance-adjacent bits, unknown winners, V0 exclusion, positive V, ties/fixed/zero workers, budgets1/3/64 and restart")
