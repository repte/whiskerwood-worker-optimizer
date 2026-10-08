"""Exact first-real-root coverage shortcut, compared with the original BFS."""

import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


PLANNER = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
FIXTURE_CLASS = None


def legacy_source(g, s, a, length):
    """Independent frozen pre-shortcut CoverageStep, not imported production DSL."""
    return f"""(fn LegacyCoverageStep ()
      {s('LastStepWork', '1')}
      (if (>= {g('QueueHead')} {length('Queue')})
        {s('CoverageSlotMatch', g('SavedSlotMatch'))}
        {s('CoverageWorkerMatch', g('SavedWorkerMatch'))}
        {s('PolicyCursor', '0')} {s('CurrentBuilding', '-1')}
        {s('BestPriority', '-1')} {s('State', '1')} (return))
      {s('SearchRow', a('Queue', g('QueueHead')))}
      {s('QueueHead', f'(+ {g("QueueHead")} 1)')}
      {s('FoundWorker', '-1')} {s('ScanWorker', '0')}
      (if (>= {g('SearchRow')} {g('SlotCount')})
        {s('UnionRow', a('BuildingFirstRow', f'(- {g("SearchRow")} {g("SlotCount")})'))}
        (else {s('UnionRow', '0')}))
      {s('State', '24')})"""


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests", "BP_CoverageRoot_" + uuid.uuid4().hex, PLANNER)
        graph = BP.add_function_graph(fixture, "LegacyCoverageStep")
        BP.compile_blueprint(fixture)

        def node(prefix, name):
            ending = prefix + name
            matches = [value for value in BP.find_node_types(graph, ending, []) if value.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            found = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            assert found is not None, (ending, matches)
            return found

        def g(name):
            return f"({node('Get', name)})"

        def s(name, value):
            return f"({node('Set', name)} {value})"

        def a(name, index):
            return f"(Utilities|Array|Get(aref) {g(name)} {index})"

        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, legacy_source(g, s, a, lambda name: f"(Utilities|Array|Length {g(name)})"))
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        FIXTURE_CLASS = fixture.generated_class()
    return FIXTURE_CLASS


def accepted(value):
    return value[-1] if isinstance(value, (tuple, list)) else value


def start(case, planner=None, legacy=False):
    if planner is None:
        planner = unreal.new_object(fixture_class() if legacy else PLANNER)
    planner.set_editor_property("StepWorkLimit", 1)
    planner.call_method("StartPlan", args=(case["scores"], case["buildings"], case["minimum"],
                                          case["priorities"], case["workers"], True))
    if "fixed" in case:
        assert accepted(planner.call_method("RequireFixedSlots", args=(case["fixed"],)))
    if "flexible" in case:
        assert accepted(planner.call_method("RequireFlexibleMinimum", args=(case["flexible"],)))
    if "reserve" in case:
        assert accepted(planner.call_method("KeepUnassigned", args=(
            case["reserve"], case["workers"], [float(index + 1) for index in range(case["workers"])])))
    return planner


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def coverage_result(planner):
    return tuple(tuple(planner.get_editor_property(name)) for name in (
        "CoverageSlotMatch", "CoverageWorkerMatch", "SavedSlotMatch", "SavedWorkerMatch",
        "Accepted", "Processed", "RequiredWorker", "FixedSlots", "FixedOwners"))


def finish_coverage(planner, limit, legacy=False):
    scans = 0
    for _ in range(200000):
        state = planner.get_editor_property("State")
        if state == 20:
            return coverage_result(planner), scans
        if planner.get_editor_property("PlanDone"):
            assert planner.get_editor_property("PlanSucceeded")
            assert planner.get_editor_property("WorkerCount") == 0 or planner.get_editor_property("RealSlotCount") == 0
            assert list(planner.get_editor_property("PlanAssignment")) == [-1] * planner.get_editor_property("RealSlotCount")
            before = coverage_result(planner)
            planner.call_method("AdvancePlan")
            assert planner.get_editor_property("LastStepWork") == 0
            assert coverage_result(planner) == before
            return before, scans
        assert not planner.get_editor_property("PlanDone"), ("Failed before coverage completed", state)
        if legacy and state == 3:
            planner.call_method("LegacyCoverageStep")
            assert planner.get_editor_property("LastStepWork") == 1
        else:
            # Stop on policy boundaries; only the worker scan itself is batched.
            work = advance(planner, limit if state == 24 else 1)
            if state == 24:
                scans += work
    raise AssertionError("Coverage did not complete")


def plan_result(planner):
    return (tuple(planner.get_editor_property("PlanAssignment")),
            tuple(planner.get_editor_property("ExpectedCounts")),
            tuple(struct.pack("!d", value) for value in planner.get_editor_property("ExpectedScores")),
            struct.pack("!d", planner.get_editor_property("BuilderTotal")), coverage_result(planner))


def finish_plan(planner, limit):
    for _ in range(300000):
        if planner.get_editor_property("PlanDone"):
            break
        advance(planner, limit)
    else:
        raise AssertionError("Planner did not complete")
    assert planner.get_editor_property("PlanSucceeded")
    result = plan_result(planner)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    assert result == plan_result(planner)
    return result


FULL = dict(workers=32, buildings=list(range(24)), minimum=[True] * 24,
            priorities=[2] * 24, fixed=[-1] * 24,
            scores=[100.0 if row == worker else 1.0 for row in range(24) for worker in range(32)], reserve=3)

CASES = [
    FULL,
    # Later partial root needs an alternating path through the earlier full root.
    dict(workers=2, buildings=[0, 1], minimum=[True, True], priorities=[4, 3],
         scores=[2.0, 1.0, 5.0, -1e20]),
    # A second minimum fails; the successful first root of that building must roll back.
    dict(workers=3, buildings=[0, 1, 1, 2], minimum=[True] * 4, priorities=[4, 3, 2],
         scores=[1.0] * 12, reserve=1),
    # No free worker, real and virtual roots, rejected building, and union-row scanning.
    dict(workers=2, buildings=[0, 1, 1, 2], minimum=[True, False, False, True],
         priorities=[4, 3, 2], flexible=[False, True, False],
         scores=[1.0, 1.0, -1e20, 2.0, 3.0, -1e20, 1.0, 1.0]),
    # Post-fixed-owner validation must not certify the other rows as all-real.
    dict(workers=4, buildings=[0, 0, 1, 2], minimum=[True, False, True, True],
         priorities=[4, 3, 2], fixed=[2, -1, -1, -1], scores=[1.0] * 16, reserve=1),
    dict(workers=1, buildings=[0, 1], minimum=[True, True], priorities=[0, 0], scores=[0.0, 0.0]),
    dict(workers=0, buildings=[0, 1], minimum=[True, True], priorities=[4, 0], scores=[]),
    dict(workers=3, buildings=[0, 1, 2], minimum=[True] * 3, priorities=[4, 3, 2],
         scores=[-1e20, -1.0, -1e20, 0.0, -1e20, 3.0, 1.0, 2.0, 3.0]),
]


def verify_fast_root():
    planner = start(FULL)
    result, scans = finish_coverage(planner, 64)
    assert all(planner.get_editor_property("RowAllReal"))
    assert scans == 0, (
        "All-real first roots with a free worker must use native first-free lookup, not worker probes",
        scans)
    return result


def verify_case(case, limit):
    current, reference = start(case), start(case, legacy=True)
    actual_coverage, _ = finish_coverage(current, limit)
    legacy_coverage, _ = finish_coverage(reference, limit, legacy=True)
    assert actual_coverage == legacy_coverage, ("Coverage arrays differ", case, limit)
    if case is CASES[1]:
        matches = list(current.get_editor_property("CoverageSlotMatch"))
        # State19 appends one unused virtual-root slot per building.
        assert matches == [1, 0, -1, -1], matches
    if case is CASES[2]:
        assert list(current.get_editor_property("Accepted")) == [True, False, True, True]
        assert list(current.get_editor_property("CoverageSlotMatch"))[:4] == [1, -1, -1, 2]
    actual, expected = finish_plan(current, limit), finish_plan(reference, limit)
    assert actual == expected, ("Final exact plan differs", case, limit)
    return actual


def verify_cancel_restart(limit):
    planner = start(FULL)
    for _ in range(100000):
        if planner.get_editor_property("State") == 3:
            break
        advance(planner, 1)
    else:
        raise AssertionError("Missing first BFS root")
    # One primitive runs the shortcut but has not yet changed either matching.
    before = coverage_result(planner)
    advance(planner, 1)
    assert planner.get_editor_property("State") == 22
    assert coverage_result(planner) == before
    planner.call_method("FailPlan")
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    assert coverage_result(planner) == before
    restarted = start(CASES[1], planner)
    actual, _ = finish_coverage(restarted, limit)
    fresh = start(CASES[1], legacy=True)
    expected, _ = finish_coverage(fresh, limit, legacy=True)
    assert actual == expected
    assert finish_plan(restarted, limit) == finish_plan(fresh, limit)


verify_fast_root()
for case in CASES:
    assert verify_case(case, 1) == verify_case(case, 3) == verify_case(case, 64)
for budget in (1, 3, 64):
    verify_cancel_restart(budget)
unreal.log("WO_PLANNER_COVERAGE_ROOT_TESTS_PASS: native first-free work, frozen legacy BFS, exact match/acceptance/plan bits, alternating paths, failed-building rollback, fixed/flexible/reserve, budgets1/3/64 and cancellation/restart")
