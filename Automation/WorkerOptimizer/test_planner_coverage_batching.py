"""Stable tier selection and bounded coverage scans in compiled planner graphs."""

import struct

import unreal


PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")


def accepted(result):
    return result[-1] if isinstance(result, (tuple, list)) else result


def start(case, planner=None):
    planner = unreal.new_object(PLANNER_CLASS) if planner is None else planner
    planner.set_editor_property("StepWorkLimit", 1)
    planner.call_method("StartPlan", args=(case["scores"], case["buildings"],
        case["minimum"], case["priorities"], case["workers"], True))
    if "fixed" in case:
        assert accepted(planner.call_method("RequireFixedSlots", args=(case["fixed"],)))
    if "flexible" in case:
        assert accepted(planner.call_method("RequireFlexibleMinimum", args=(case["flexible"],)))
    if "reserve" in case:
        assert accepted(planner.call_method("KeepUnassigned", args=(
            case["reserve"], case["workers"], [1.0] * case["workers"])))
    return planner


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def verify_selection_work():
    case = dict(workers=40, buildings=list(range(30)), minimum=[True] * 30,
                priorities=[building % 5 for building in range(30)] + [4, 0, 3],
                scores=[1.0] * 1200, reserve=1)
    expected = sorted(range(30), key=lambda building: (-case["priorities"][building], building))
    planner = None
    for _ in range(2):
        planner = start(case, planner)
        order, selection_work = [], 0
        for _ in range(100000):
            state = planner.get_editor_property("State")
            if state == 20:
                break
            assert not planner.get_editor_property("PlanDone")
            work = advance(planner, 1)
            if state == 1:
                selection_work += work
                if planner.get_editor_property("State") == 2:
                    order.append(planner.get_editor_property("CurrentBuilding"))
        else:
            raise AssertionError("Building selection did not complete")
        assert order == expected, (order, expected)
        buildings = planner.get_editor_property("BuildingCount")
        assert selection_work <= 5 * (buildings + 1) + 1, (
            "Selection must scan each priority tier once, not all buildings per choice",
            selection_work, buildings)
        assert list(planner.get_editor_property("Accepted")) == [True] * 30 + [False] * 3 + [True]
        assert all(planner.get_editor_property("Processed"))


CASES = [
    dict(workers=4, buildings=[0, 0, 1, 1], minimum=[True, False, True, False],
         priorities=[4, 0], scores=[-1e20 if (row, worker) == (0, 3) else 10.0 if row == worker else 1.0
                                   for row in range(4) for worker in range(4)]),
    dict(workers=4, buildings=[0, 0, 1, 1], minimum=[True, False, True, False],
         priorities=[2, 0], fixed=[2, -1, -1, -1], reserve=1,
         scores=[1.0] * 16),
    dict(workers=3, buildings=[0, 0, 1, 1, 2], minimum=[False, False, False, False, True],
         priorities=[4, 2, 0], flexible=[True, True, False],
         scores=[-0.0, 2.0, -1e20, 8.0, 1.0, 0.25, 3.0, -1e20, 4.0,
                 0.1, 6.0, 2.0, 3.0, 2.0, 8.0]),
    dict(workers=2, buildings=[0, 0, 1, 1], minimum=[True, True, True, False],
         priorities=[4, 0], scores=[5.0, 1.0, 1.0, 7.0, 3.0, 2.0, 1.0, 3.0]),
]


def coverage_state(planner):
    values = {name: planner.get_editor_property(name) for name in (
        "State", "ScanWorker", "ScanRow", "SearchRow", "UnionRow", "FoundWorker",
        "QueueHead", "RootSlot", "CurrentBuilding", "CurrentSlot",
    )}
    for name in ("Visited", "ParentRow", "Queue", "CoverageSlotMatch",
                 "CoverageWorkerMatch", "SavedSlotMatch", "SavedWorkerMatch", "Accepted"):
        values[name] = list(planner.get_editor_property(name))
    return values


def result(planner):
    return (list(planner.get_editor_property("PlanAssignment")),
            list(planner.get_editor_property("ExpectedCounts")),
            [struct.pack("!d", value) for value in planner.get_editor_property("ExpectedScores")],
            struct.pack("!d", planner.get_editor_property("BuilderTotal")),
            list(planner.get_editor_property("Accepted")))


def verify_coverage(case, limit):
    single, batch = start(case), start(case)
    phases, scan_work = 0, 0
    for _ in range(100000):
        assert coverage_state(single) == coverage_state(batch)
        if batch.get_editor_property("PlanDone"):
            break
        if batch.get_editor_property("State") == 24:
            work = advance(batch, limit)
            for _ in range(work):
                assert single.get_editor_property("State") == 24, "Coverage batch crossed its phase boundary"
                single.call_method("PolicyStep")
            assert coverage_state(single) == coverage_state(batch), (limit, phases)
            phases += 1
            scan_work += work
        else:
            advance(single, 1)
            advance(batch, 1)
    else:
        raise AssertionError("Coverage comparison did not complete")
    assert single.get_editor_property("PlanSucceeded") and batch.get_editor_property("PlanSucceeded")
    assert phases > 0 and result(single) == result(batch)
    batch.call_method("AdvancePlan")
    assert batch.get_editor_property("LastStepWork") == 0
    return result(batch), scan_work


def reach_scan():
    planner = start(CASES[0])
    for _ in range(10000):
        if planner.get_editor_property("State") == 24:
            return planner
        advance(planner, 1)
    raise AssertionError("Fixture did not reach coverage scanning")


def verify_cancellation():
    planner = reach_scan()
    before = coverage_state(planner)
    planner.call_method("FailPlan")
    planner.set_editor_property("StepWorkLimit", 64)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    assert coverage_state(planner) == before
    assert not planner.get_editor_property("PlanSucceeded")

    planner = reach_scan()
    before = coverage_state(planner)
    planner.set_editor_property("StepWorkLimit", 0)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("PlanDone") and not planner.get_editor_property("PlanSucceeded")
    assert planner.get_editor_property("LastStepWork") == 0
    assert coverage_state(planner) == before


verify_selection_work()
for case in CASES:
    assert verify_coverage(case, 1) == verify_coverage(case, 3) == verify_coverage(case, 64)
verify_cancellation()
unreal.log("WO_PLANNER_COVERAGE_BATCHING_TESTS_PASS: stable bounded selection/reuse; primitive-vs-batch scans, budgets1/3/64, fixed/flexible/rejected/reserve, cancellation")
