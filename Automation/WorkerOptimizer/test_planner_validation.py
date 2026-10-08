"""Validation batching preserves each score bit and stops at phase boundaries."""

import struct

import unreal


PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
SCORES = [
    1.0, -0.0, 0.25, 1000000.0,
    0.125, 19.3, -1e20, 0.0,
    2.5, 7.0, 0.1, 5.0,
    1.0, 6.0, 3.0, 23.7,
]


def scalar_bits(value):
    return struct.pack("!d", float(value))


def snapshot(planner):
    values = {name: planner.get_editor_property(name) for name in (
        "PlanValidationIndex", "State", "PlanDone", "PlanSucceeded",
        "PolicyCursor", "CurrentBuilding", "BestPriority",
    )}
    for name in ("MaxScore", "FillBonus", "CoverageBonus", "ColumnBonus"):
        values[name] = scalar_bits(planner.get_editor_property(name))
    values["BaseScores"] = tuple(
        scalar_bits(value) for value in planner.get_editor_property("BaseScores"))
    return values


def start(fixed=False, reserve=0, scores=None, planner=None):
    if planner is None:
        planner = unreal.new_object(PLANNER_CLASS)
    planner.set_editor_property("StepWorkLimit", 1)
    planner.call_method("StartPlan", args=(
        SCORES if scores is None else scores,
        [0, 0, 1, 1], [True, False, True, False], [4, 0], 4, True))
    if fixed:
        assert planner.call_method("RequireFixedSlots", args=([2, -1, 0, -1],))
    if reserve:
        assert planner.call_method("KeepUnassigned", args=(reserve, 4, [1.0] * 4))
    for _ in range(1000):
        if planner.get_editor_property("State") == 0:
            return planner
        assert not planner.get_editor_property("PlanDone"), "Fixture failed before validation"
        planner.call_method("AdvancePlan")
        assert planner.get_editor_property("LastStepWork") == 1
    raise AssertionError("Fixture never reached score validation")


def verify_differential(fixed, reserve, limit, scores=None):
    single = start(fixed, reserve, scores)
    batch = start(fixed, reserve, scores)
    batch.set_editor_property("StepWorkLimit", limit)
    total = 0
    while batch.get_editor_property("State") == 0 and not batch.get_editor_property("PlanDone"):
        remaining = len(batch.get_editor_property("BaseScores")) - batch.get_editor_property("PlanValidationIndex")
        batch.call_method("AdvancePlan")
        work = batch.get_editor_property("LastStepWork")
        assert 0 < work <= min(limit, remaining + 1), (limit, remaining, work)
        for _ in range(work):
            assert single.get_editor_property("State") == 0 and not single.get_editor_property("PlanDone")
            single.call_method("ValidateBlock")
        assert snapshot(batch) == snapshot(single), (fixed, reserve, limit, total)
        total += work
        assert total <= len(batch.get_editor_property("BaseScores")) + 1
    return batch, total


def verify_validation_fence():
    planner = start()
    cells = len(planner.get_editor_property("BaseScores"))
    planner.set_editor_property("StepWorkLimit", 64)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("State") == 19, (
        "Validation batch must yield before building preprocessing",
        planner.get_editor_property("State"))
    assert planner.get_editor_property("LastStepWork") == cells + 1
    assert planner.get_editor_property("PlanValidationIndex") == cells


def verify_invalid_masked_score():
    # Validation must inspect even a cell subsequently excluded by a fixed worker.
    for bad in (1000001.0, -1e21, float("inf"), float("nan")):
        scores = list(SCORES)
        scores[3] = bad
        for limit in (1, 3, 64):
            planner, work = verify_differential(True, 0, limit, scores)
            assert planner.get_editor_property("PlanDone")
            assert not planner.get_editor_property("PlanSucceeded")
            assert planner.get_editor_property("PlanValidationIndex") == 3
            assert work == 4


def verify_native_visited_reset():
    planner = start()
    resets = 0
    cleared_nonempty = False
    for _ in range(20000):
        if planner.get_editor_property("PlanDone"):
            break
        if planner.get_editor_property("State") == 21:
            root = planner.get_editor_property("RootSlot")
            cleared_nonempty |= any(planner.get_editor_property("Visited"))
            planner.call_method("AdvancePlan")
            assert planner.get_editor_property("LastStepWork") == 1
            assert planner.get_editor_property("State") == 3, "Visited reset must finish in one bounded native operation"
            assert list(planner.get_editor_property("Visited")) == [False] * 4
            assert list(planner.get_editor_property("Queue")) == [root]
            assert planner.get_editor_property("QueueHead") == 0
            resets += 1
        else:
            planner.call_method("AdvancePlan")
            assert planner.get_editor_property("LastStepWork") == 1
    else:
        raise AssertionError("Visited reset fixture did not complete")
    assert planner.get_editor_property("PlanSucceeded")
    assert resets >= 2 and cleared_nonempty, (resets, cleared_nonempty)
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0


verify_validation_fence()
for fixed in (False, True):
    for reserve in (0, 1):
        totals = []
        for limit in (1, 3, 64):
            planner, work = verify_differential(fixed, reserve, limit)
            assert not planner.get_editor_property("PlanDone")
            assert planner.get_editor_property("State") == 19
            if not fixed:
                assert planner.get_editor_property("MaxScore") == 1000000.0
            totals.append(work)
        assert len(set(totals)) == 1, (fixed, reserve, totals)
verify_invalid_masked_score()
verify_native_visited_reset()
unreal.log("WO_PLANNER_VALIDATION_TESTS_PASS: bit-exact single/batch validation, fixed/reserve/invalid scores, phase fence, native visited reset")
