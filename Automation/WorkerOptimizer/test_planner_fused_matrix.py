"""Fused matrix construction keeps legacy masks and floating-point operations."""

import json
import struct

import unreal
from planner_test_cost_probe import probe_class, read_scores, supports_implicit


PLANNER_CLASS = unreal.load_class(
    None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def start(case, limit):
    planner = unreal.new_object(probe_class(PLANNER_CLASS))
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=(
        case["scores"], case["buildings"], case["minimum"],
        case["priorities"], case["workers"], case.get("strict", True)))
    if "fixed" in case:
        assert planner.call_method("RequireFixedSlots", args=(case["fixed"],))
    if "flexible" in case:
        assert planner.call_method("RequireFlexibleMinimum", args=(case["flexible"],))
    if "reserve" in case:
        assert planner.call_method("KeepUnassigned", args=(
            case["reserve"], case["workers"], case["quality"]))
    return planner


def advance(planner, limit):
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (limit, work)


def expected_pass(planner, first):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    base = list(get("BaseScores"))
    buildings, priorities = list(get("SlotBuildings")), list(get("Priorities"))
    accepted, fixed = list(get("Accepted")), list(get("FixedSlots"))
    minimum, dummies = list(get("Minimum")), list(get("DummyBuildings"))
    required = list(get("RequiredWorker"))
    tier, strict = get("Tier"), get("StrictMode")
    fill, coverage, column_bonus = get("FillBonus"), get("CoverageBonus"), get("ColumnBonus")
    allowed = [False] * (rows * columns) if first else list(get("AllowedEdges"))
    scores = []
    for row in range(rows):
        building = buildings[row]
        priority = priorities[building]
        for column in range(columns):
            index = row * columns + column
            expanded = -1e20
            if column < workers:
                if accepted[building] or fixed[row] >= 0:
                    expanded = base[row * workers + column]
            elif (dummies[column - workers] == building and fixed[row] < 0
                  and not (minimum[row] and accepted[building])):
                expanded = 0.0
            if first:
                allowed[index] = expanded >= 0.0
            score = -1e20
            if allowed[index]:
                score = 0.0
                if column < workers:
                    if priority >= 0 and tier >= 0:
                        if not strict:
                            score = fill + expanded * (priority + 1)
                        elif priority == tier:
                            score = fill + expanded
                    if priority < 0 and tier < 0:
                        score = expanded
                    if minimum[row]:
                        score = score + coverage
                if required[column]:
                    score = score + column_bonus
            scores.append(score)
    return allowed, scores


CASES = [
    dict(workers=4, buildings=[0, 0, 1, 1], minimum=[True, False, True, False],
         priorities=[4, 0], fixed=[2, -1, 0, -1], reserve=1, quality=[1.0, 4.0, 3.0, 2.0],
         scores=[1.0, -0.0, 0.25, 1000000.0, 0.125, 19.3, -1e20, 0.0,
                 2.5, 7.0, 0.1, 5.0, 1.0, 6.0, 3.0, 23.7]),
    dict(workers=3, buildings=[0, 0, 1, 1, 2], minimum=[False, False, False, False, True],
         priorities=[4, 2, 0], flexible=[True, True, False],
         scores=[-0.0, 2.0, -1e20, 8.0, 1.0, 0.25, 3.0, -1e20, 4.0,
                 0.1, 6.0, 2.0, 3.0, 2.0, 8.0]),
    dict(workers=2, buildings=[0, 0, 1, 1], minimum=[True, True, True, False],
         priorities=[4, 0], scores=[5.0, 1.0, 1.0, 7.0, 3.0, 2.0, 1.0, 3.0]),
    dict(workers=6, buildings=[0, 0, 1, 1, 2, 2],
         minimum=[True, False, True, False, True, False], priorities=[4, 2, 0],
         strict=False, reserve=1, quality=[1.0, 4.0, 6.0, 2.0, 3.0, 5.0],
         scores=[100.0 if row == worker else (row + worker + 1) / 7.0
                 for row in range(6) for worker in range(6)]),
]


def verify_fused_phase():
    planner = start(CASES[0], 1)
    for _ in range(10000):
        if planner.get_editor_property("State") == 26:
            break
        advance(planner, 1)
    else:
        raise AssertionError("Planner never reached matrix preparation")
    planner.set_editor_property("StepWorkLimit", 64)
    advance(planner, 64)
    assert planner.get_editor_property("State") == 28
    assert planner.get_editor_property("LastStepWork") == 1, (
        "Initial edge mask must be fused into BuildPass, not scanned separately",
        planner.get_editor_property("LastStepWork"))
    assert not list(planner.get_editor_property("ExpandedScores")), "Redundant float matrix was materialized"


def verify_case(case, limit):
    planner = start(case, limit)
    pending = None
    pending_refinement = None
    passes = 0
    saw_refinement = False
    for _ in range(100000):
        if planner.get_editor_property("PlanDone"):
            break
        state = planner.get_editor_property("State")
        if state == 4 and planner.get_editor_property("BuildIndex") == 0:
            pending = expected_pass(planner, passes == 0)
        if state == 6:
            saw_refinement = True
            if planner.get_editor_property("BuildIndex") == 0:
                implicit = planner.get_editor_property("ImplicitFirstPass")
                scores = read_scores(planner) if implicit else list(planner.get_editor_property("PassScores"))
                mask = [score >= 0.0 for score in scores] if implicit else list(planner.get_editor_property("AllowedEdges"))
                columns = planner.get_editor_property("SolveColumns")
                u, v = list(planner.get_editor_property("U")), list(planner.get_editor_property("V"))
                for index, allowed in enumerate(mask):
                    if allowed:
                        row, column = divmod(index, columns)
                        reduced = ((0.0 - scores[index]) - u[row + 1]) - v[column + 1]
                        mask[index] = -0.00001 <= reduced <= 0.00001
                refined_scores = [score if allowed else -1e20 for score, allowed in zip(scores, mask)]
                retained, offsets = [], [0]
                for row in range(planner.get_editor_property("SlotCount")):
                    retained.extend(column for column in range(columns) if mask[row * columns + column])
                    offsets.append(len(retained))
                pending_refinement = implicit, mask, refined_scores, retained, offsets
        advance(planner, limit)
        if pending_refinement is not None and planner.get_editor_property("State") == 30:
            implicit, mask, scores, retained, offsets = pending_refinement
            assert list(planner.get_editor_property("AllowedEdges")) == mask
            assert list(planner.get_editor_property("RetainedColumns")) == retained
            assert list(planner.get_editor_property("RetainedRowOffsets")) == offsets
            assert planner.get_editor_property("RetainedReady")
            if implicit:
                assert not list(planner.get_editor_property("PassScores")), "First refinement must defer dense scores"
            else:
                assert bits(planner.get_editor_property("PassScores")) == bits(scores)
            pending_refinement = None
        if pending is not None and planner.get_editor_property("State") == 5:
            mask, scores = pending
            implicit = supports_implicit(PLANNER_CLASS) and planner.get_editor_property("ImplicitFirstPass")
            if implicit:
                assert not list(planner.get_editor_property("PassScores"))
                assert not list(planner.get_editor_property("AllowedEdges"))
                actual_scores = read_scores(planner)
                assert [score >= 0.0 for score in actual_scores] == mask, (limit, passes, "implicit mask")
            else:
                assert list(planner.get_editor_property("AllowedEdges")) == mask, (limit, passes, "mask")
                actual_scores = list(planner.get_editor_property("PassScores"))
            assert bits(actual_scores) == bits(scores), (limit, passes, "cost")
            columns = planner.get_editor_property("SolveColumns")
            minima, second_minima, winners = [], [], []
            for row in range(planner.get_editor_property("SlotCount")):
                # The Blueprint DSL lowers unary minus to 0 - value, including signed zero.
                costs = [0.0 - score for score in scores[row * columns:(row + 1) * columns]]
                winner = min(range(columns), key=costs.__getitem__)
                minima.append(costs[winner])
                second_minima.append(sorted(costs)[1] if columns > 1 else 1e20)
                winners.append(winner + 1)
            actual_minima = list(planner.get_editor_property("RowMinCost"))
            actual_columns = list(planner.get_editor_property("RowMinColumn"))
            planner_minima = list(planner.get_editor_property("PassRowMinCost"))
            diagnostic = {
                "limit": limit, "pass": passes, "case": case,
                "state": planner.get_editor_property("State"),
                "solver_state": planner.get_editor_property("SolverState"),
                "tier": planner.get_editor_property("Tier"),
                "actual_minima": actual_minima, "expected_minima": minima,
                "actual_columns": actual_columns, "expected_columns": winners,
                "planner_minima": planner_minima,
                "planner_columns": list(planner.get_editor_property("PassRowMinColumn")),
                "actual_bits": [value.hex() for value in bits(actual_minima)],
                "expected_bits": [value.hex() for value in bits(minima)],
                "planner_bits": [value.hex() for value in bits(planner_minima)],
            }
            columns_valid = all(actual == expected or (implicit and actual == 0)
                                for actual, expected in zip(actual_columns, winners))
            if bits(actual_minima) != bits(minima) or not columns_valid:
                unreal.log_error("WO_FUSED_CACHE_DIAGNOSTIC " + json.dumps(diagnostic, sort_keys=True))
            assert bits(actual_minima) == bits(minima), diagnostic
            assert bits(planner.get_editor_property("RowSecondMinCost")) == bits(second_minima), diagnostic
            assert bits(planner.get_editor_property("PassRowSecondMinCost")) == bits(second_minima), diagnostic
            assert len(actual_columns) == len(winners) and columns_valid, diagnostic
            assert not list(planner.get_editor_property("ExpandedScores"))
            pending = None
            passes += 1
    else:
        raise AssertionError("Fused matrix fixture did not complete")
    assert planner.get_editor_property("PlanSucceeded"), case
    assert passes > 0 and pending is None and pending_refinement is None
    if case.get("strict", True) and len(set(case["priorities"])) > 1:
        assert saw_refinement and passes >= 2, (passes, saw_refinement)
    result = (list(planner.get_editor_property("PlanAssignment")),
              bits(planner.get_editor_property("ExpectedScores")),
              list(planner.get_editor_property("ExpectedCounts")),
              bits([planner.get_editor_property("BuilderTotal")]))
    planner.call_method("AdvancePlan")
    assert planner.get_editor_property("LastStepWork") == 0
    return result


if __name__ == "__main__":
    verify_fused_phase()
    for case in CASES:
        assert verify_case(case, 1) == verify_case(case, 3) == verify_case(case, 64)
    unreal.log("WO_PLANNER_FUSED_MATRIX_TESTS_PASS: legacy mask/cost bits, bounded row cursors, refined-mask preservation, fixed/flexible/reserve/weighted/rejected crews")
