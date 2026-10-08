"""Compiled exactness/work regression for full-CSR single-maximum templates."""

import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType


PARENT = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
SINGLE_AVAILABLE = False


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def fixture_class():
    global SINGLE_AVAILABLE
    fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_SingleMaximum_" + uuid.uuid4().hex, PARENT)
    graph = BP.add_function_graph(fixture, "SeedBuild")
    for name, kind in (("InputColumns", "int"), ("InputOffsets", "int"),
                       ("InputRequired", "bool"), ("InputMask", "bool"), ("InputSingle", "bool")):
        BP.add_function_param(graph, name, kind, True, ContainerType.ARRAY)
    BP.compile_blueprint(fixture)

    def node(ending):
        matches = [name for name in BP.find_node_types(graph, ending, []) if name.endswith("|" + ending)]
        preferred = "Variables|Default|" + ending
        assert preferred in matches or len(matches) == 1, (ending, matches)
        return preferred if preferred in matches else matches[0]

    source = "(fn SeedBuild (InputColumns InputOffsets InputRequired InputMask InputSingle) "
    for name, value in (("RetainedColumns", "InputColumns"), ("RetainedRowOffsets", "InputOffsets"),
                        ("RequiredWorker", "InputRequired"), ("AllowedEdges", "InputMask"),
                        ("RetainedReady", "true"), ("FirstPass", "false"), ("Tier", "4")):
        source += f"({node('Set' + name)} {value}) "
    # Old assets have no certificate yet; both paths then correctly do full work.
    single_setters = [name for name in BP.find_node_types(graph, "SetRowSingleMaximum", [])
                      if name.endswith("|SetRowSingleMaximum")]
    SINGLE_AVAILABLE = bool(single_setters)
    if single_setters:
        source += f"({node('SetRowSingleMaximum')} InputSingle) "
    source += f"({node('BeginPass')}))"
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graph, source)
        BP.compile_blueprint(fixture, warnings_as_errors=True)
    return fixture.generated_class()


def advance(planner, limit):
    fields = ("State", "PlanDone", "PlanSucceeded", "Done", "SolverState", "PolicyCursor",
              "PlanValidationIndex", "ScanRow", "ScanWorker", "BuildIndex")
    before = tuple(planner.get_editor_property(name) for name in fields)
    assert not before[1], ("Fixture terminated before target", dict(zip(fields, before)))
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    after = tuple(planner.get_editor_property(name) for name in fields)
    assert 0 <= work <= limit, (work, limit, dict(zip(fields, before)), dict(zip(fields, after)))
    assert work > 0 or before != after, ("No work or state progress", work, limit, dict(zip(fields, before)))
    assert not (after[1] and not after[2]), ("Fixture failed", dict(zip(fields, before)), dict(zip(fields, after)))
    return work


def run_seeded(cls, workers, limit, enabled, *, partial=False, varied=False, weighted=False, reuse=False):
    rows = 16
    minimum = [row % 2 == 0 for row in range(rows)]
    bases = []
    for row in range(rows):
        background = (0.01 if row % 3 else 0.0101) if varied else 0.01
        bases.extend(100.0 if worker == (row * 7 + 3) % workers else background
                     for worker in range(workers))
    planner = unreal.new_object(cls)
    buildings = [row // 2 for row in range(rows)]
    planner.call_method("StartPlan", args=(bases, buildings, minimum, [4] * (rows // 2), workers, not weighted))
    for _ in range(100000):
        if planner.get_editor_property("State") == 5:
            break
        advance(planner, 64)
    else:
        raise AssertionError("First pass did not initialize")
    columns = planner.get_editor_property("SolveColumns")
    dummy_starts = list(planner.get_editor_property("BuildingDummyStart"))
    dummy_ends = list(planner.get_editor_property("BuildingDummyEnd"))
    masks, retained, offsets = [], [], [0]
    for row in range(rows):
        row_columns = [worker for worker in range(workers)
                       if not partial or worker != (row + 1) % workers]
        if not minimum[row]:
            row_columns.extend(range(dummy_starts[buildings[row]], dummy_ends[buildings[row]]))
        retained.extend(row_columns)
        offsets.append(len(retained))
        masks.extend(column in row_columns for column in range(columns))
    required = [column % 3 == 1 for column in range(columns)]
    all_snapshots, total_work = [], 0
    for epoch in range(2 if reuse else 1):
        if epoch:
            required = [not value for value in required]
        planner.call_method("SeedBuild", args=(retained, offsets, required, masks, [enabled] * rows))
        if SINGLE_AVAILABLE:
            assert list(planner.get_editor_property("RowSingleMaximum")) == [enabled] * rows
        work = 0
        while planner.get_editor_property("State") == 4:
            work += advance(planner, limit)
        assert planner.get_editor_property("State") == 5
        get = planner.get_editor_property
        fill, coverage, bonus = get("FillBonus"), get("CoverageBonus"), get("ColumnBonus")
        expected = []
        for row in range(rows):
            for column in range(columns):
                value = -1e20
                if masks[row * columns + column]:
                    value = 0.0
                    if column < workers:
                        raw = bases[row * workers + column]
                        value = fill + (raw * 5 if weighted else raw)
                        if minimum[row]:
                            value = value + coverage
                    if required[column]:
                        value = value + bonus
                expected.append(value)
        assert bits(get("PassScores")) == bits(expected), (limit, enabled, partial, varied, weighted, epoch)
        assert bits(get("Scores")) == bits(expected)
        caches = []
        for row in range(rows):
            costs = [0.0 - score for score in expected[row * columns:(row + 1) * columns]]
            first = min(costs)
            caches.append((first, sorted(costs)[1], costs.index(first) + 1))
        for name, index in (("PassRowMinCost", 0), ("PassRowSecondMinCost", 1),
                            ("RowMinCost", 0), ("RowSecondMinCost", 1)):
            assert bits(get(name)) == bits([cache[index] for cache in caches]), (name, epoch)
        for name in ("PassRowMinColumn", "RowMinColumn"):
            assert list(get(name)) == [cache[2] for cache in caches], (name, epoch)
        for _ in range(100000):
            if get("Done"):
                break
            planner.set_editor_property("StepWorkLimit", 64)
            planner.call_method("Advance")
        else:
            raise AssertionError("Seeded solver did not finish")
        assert get("Succeeded")
        all_snapshots.append((bits(expected), tuple(get("Assignment")), tuple(get("P")),
                              bits(get("U")), bits(get("V"))))
        total_work += work
    return all_snapshots, total_work


def run():
    cls = fixture_class()
    measurements = []
    comparisons = 0
    for limit in (1, 3, 64):
        for options in ({}, {"partial": True}, {"varied": True}, {"weighted": True}, {"reuse": True}):
            reference, reference_work = run_seeded(cls, 32, limit, False, **options)
            optimized, optimized_work = run_seeded(cls, 32, limit, True, **options)
            assert optimized == reference, (limit, options)
            comparisons += 1
            if not options:
                measurements.append((limit, reference_work, optimized_work))
            if options.get("partial"):
                assert optimized_work == reference_work, ("Partial CSR must fall back", limit)
    unreal.log("WO_SINGLE_MAX_TEMPLATE_EXACTNESS_PASS comparisons=" + str(comparisons))
    for limit, reference_work, optimized_work in measurements:
        assert optimized_work <= 240 and optimized_work < reference_work, (
            "Single-maximum full rows still calculate every real edge", limit, reference_work, optimized_work)
    unreal.log("WO_SINGLE_MAX_TEMPLATE_TESTS_PASS " + str(measurements))


run()
