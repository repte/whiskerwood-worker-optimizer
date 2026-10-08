"""Compiled regression for deferred refinement scores and native row templates."""

import unreal

from test_planner_fused_matrix import PLANNER_CLASS, bits, expected_pass
from planner_refinement_test_support import implicit_refinement_work


def advance(planner, limit):
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("AdvancePlan")
    work = planner.get_editor_property("LastStepWork")
    assert 0 < work <= limit, (work, limit)
    return work


def reach(planner, state):
    for _ in range(100000):
        if planner.get_editor_property("State") == state:
            return
        assert not planner.get_editor_property("PlanDone"), ("Missing fixture phase", state)
        advance(planner, 1)
    raise AssertionError(("Fixture exceeded work guard", state))


def start():
    workers = 12
    planner = unreal.new_object(PLANNER_CLASS)
    planner.call_method("StartPlan", args=([100.0] * (workers * workers),
        [row // 2 for row in range(workers)], [True, False] * 6, [2] * 6, workers, True))
    assert planner.call_method("KeepUnassigned", args=(2, workers, [float(i + 1) for i in range(workers)]))[-1]
    reach(planner, 6)
    assert planner.get_editor_property("ImplicitFirstPass")
    return planner


def first_refinement(planner, limit):
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    allowed, scores = expected_pass(planner, True)
    u, v = list(get("U")), list(get("V"))
    target, retained, offsets = [], [], [0]
    for row in range(rows):
        for column in range(columns):
            index = row * columns + column
            reduced = ((0.0 - scores[index]) - u[row + 1]) - v[column + 1]
            keep = allowed[index] and -0.00001 <= reduced <= 0.00001
            target.append(keep)
            if keep:
                retained.append(column)
        offsets.append(len(retained))
    expected_work = implicit_refinement_work(planner)
    work = 0
    while get("State") == 6:
        work += advance(planner, limit)
    # This is intentionally first, so the old dense assets fail for the feature.
    assert not list(get("PassScores")), "First implicit refinement must defer the dense score matrix"
    assert get("State") == 30 and get("RetainedReady")
    assert work == expected_work, ("Reconstructed-range work", work, expected_work, rows)
    assert list(get("AllowedEdges")) == target
    assert list(get("RetainedColumns")) == retained
    assert list(get("RetainedRowOffsets")) == offsets
    for name in ("PassRowMinCost", "PassRowSecondMinCost"):
        assert bits(get(name)) == bits([1e20] * rows), name
    assert list(get("PassRowMinColumn")) == [1] * rows


def later_build(planner, limit):
    reach(planner, 4)
    get = planner.get_editor_property
    rows, columns, workers = get("SlotCount"), get("SolveColumns"), get("WorkerCount")
    mask, scores = expected_pass(planner, False)
    offsets, retained = list(get("RetainedRowOffsets")), list(get("RetainedColumns"))
    patches = full_rows = 0
    for row in range(rows):
        edge_columns = retained[offsets[row]:offsets[row + 1]]
        priority = get("Priorities")[get("SlotBuildings")[row]]
        tier, strict = get("Tier"), get("StrictMode")
        mode = 0
        if priority >= 0 and tier >= 0:
            mode = 2 if not strict else int(priority == tier)
        elif priority < 0 and tier < 0:
            mode = 3
        full_real = mode == 0 and workers > 0 and set(range(workers)).issubset(edge_columns)
        full_rows += full_real
        patches += len(edge_columns) - (workers if full_real else 0)
    assert full_rows > 0, "Fixture must exercise the native full-real constant-row template"
    work = 0
    while get("State") == 4:
        work += advance(planner, limit)
    assert get("State") == 5 and not get("ImplicitFirstPass")
    assert work == columns + 1 + rows + patches + 1, ("Template build work", work, columns, rows, patches)
    assert bits(get("PassScores")) == bits(scores)
    assert bits(get("Scores")) == bits(scores)
    assert list(get("AllowedEdges")) == mask
    minima, second, winners = [], [], []
    for row in range(rows):
        costs = [0.0 - value for value in scores[row * columns:(row + 1) * columns]]
        ordered = sorted(costs)
        minima.append(ordered[0] if costs else 1e20)
        second.append(ordered[1] if len(costs) > 1 else 1e20)
        winners.append(costs.index(ordered[0]) + 1 if costs else 1)
    for name in ("PassRowMinCost", "RowMinCost"):
        assert bits(get(name)) == bits(minima), name
    for name in ("PassRowSecondMinCost", "RowSecondMinCost"):
        assert bits(get(name)) == bits(second), name
    assert list(get("PassRowMinColumn")) == winners
    assert list(get("RowMinColumn")) == winners


def finish(planner, limit):
    for _ in range(100000):
        if planner.get_editor_property("PlanDone"):
            break
        advance(planner, limit)
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded")
    assignment = list(planner.get_editor_property("PlanAssignment"))
    workers = [worker for worker in assignment if worker >= 0]
    assert len(workers) == len(set(workers)) == 10
    assert all(assignment[row] >= 0 for row in range(0, 12, 2))
    assert planner.get_editor_property("BuilderTotal") == 23.0
    return assignment


def verify_restart(planner, limit):
    planner.call_method("StartPlan", args=([8.0, 1.0, 1.0, 9.0], [0, 1], [True, True], [2, 2], 2, True))
    assert not planner.get_editor_property("RetainedReady")
    assert not list(planner.get_editor_property("PassScores"))
    for _ in range(10000):
        if planner.get_editor_property("PlanDone"):
            break
        advance(planner, limit)
    assert planner.get_editor_property("PlanSucceeded")
    assert list(planner.get_editor_property("PlanAssignment")) == [0, 1]


def run():
    assignments = []
    for limit in (1, 3, 64):
        planner = start()
        first_refinement(planner, limit)
        later_build(planner, limit)
        assignments.append(finish(planner, limit))
        verify_restart(planner, limit)
        interrupted = start()
        for _ in range(5):
            advance(interrupted, 1)
        verify_restart(interrupted, limit)
    assert assignments[0] == assignments[1] == assignments[2]
    unreal.log("WO_PLANNER_DEFERRED_MATRIX_TESTS_PASS: candidate ranges, empty first scores, exact native-template costs/caches, budgets1/3/64 and restart")


if __name__ == "__main__":
    run()
