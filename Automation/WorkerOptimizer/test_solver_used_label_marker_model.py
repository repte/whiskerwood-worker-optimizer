"""Actual-emitted lifecycle differential for the isolated used-label prototype."""

import math
from pathlib import Path
import random

from benchmark_native_relaxation import equal
from solver_used_label_marker_prototype import prototype_graphs
from test_solver_native_lifecycle_model import SolverMachine, emitted


def initialize(machine, matrix, enabled, prefix, dummy=False, implicit=False):
    rows, cols = len(matrix), len(matrix[0])
    if implicit:
        starts, ends, allowed = [], [], []
        for row in matrix:
            legal = [j for j in range(prefix, cols) if row[j] >= 0.0]
            assert not legal or legal == list(range(legal[0], legal[-1] + 1))
            starts.append(legal[0] if legal else prefix)
            ends.append(legal[-1] + 1 if legal else prefix)
            allowed.append(bool(legal))
        machine.state.update(ImplicitWorkerCount=prefix,
            ImplicitScores=[v for row in matrix for v in row[:prefix]],
            ImplicitModes=[3] * rows, ImplicitMultipliers=[1] * rows,
            ImplicitMinimumRows=[False] * rows, ImplicitRealRows=[True] * rows,
            ImplicitDummyRows=allowed, ImplicitFixedWorkers=[-1] * rows,
            ImplicitDummyStarts=starts, ImplicitDummyEnds=ends,
            ImplicitFillBonus=0.0, ImplicitCoverageBonus=0.0, ImplicitColumnBonus=0.0)
        machine.invoke("InitializeImplicitFirstPass", [rows, cols])
        costs = [[0.0 - value for value in row] for row in matrix]
        machine.state.update(RowMinCost=[min(row) for row in costs],
            RowMinColumn=[row.index(min(row)) + 1 for row in costs],
            RowSecondMinCost=[sorted(row)[1] if len(row) > 1 else 1e20 for row in costs])
    else:
        machine.invoke("Initialize", [[v for row in matrix for v in row], rows, cols])
        machine.invoke("RestrictDummies", [[dummy] * rows])
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    machine.state.update(NativePlannerTrusted=True, NativeCsrReady=not implicit,
                         NativeRowOffsets=offsets, NativeColumns=columns,
                         ImplicitWorkerCount=prefix, MarkerEnabled=enabled,
                         MarkerInfinity=math.inf, MarkerRow=-1,
                         MarkerSeenUsed=0, MarkerPrefixUsed=0, MarkerMarks=0)
    machine.label_epoch = 0


def run_one(graphs, symbol, matrix, limit, enabled, prefix, dummy=False, implicit=False, reuse=None):
    machine = reuse or SolverMachine(graphs, symbol, limit)
    initialize(machine, matrix, enabled, prefix, dummy, implicit)
    work = calls = masks = 0
    trace = []
    while not machine.state["Done"]:
        if machine.state["SolverState"] == 11 and machine.state.get("NativePhase") == 3:
            masks += 1
        previous_state = machine.state["SolverState"]
        previous_row, previous_j0 = machine.state["ActiveRow"], machine.state.get("J0", 0)
        machine.invoke("MarkerAdvance" if enabled else "Advance")
        units = machine.state["LastStepWork"]
        assert 0 < units <= limit
        work += units
        calls += 1
        assert work < 1000000
        if previous_state != 6 and machine.state["SolverState"] == 6:
            if previous_state == 5 and previous_j0 == 0:
                machine.label_epoch = previous_row
            live = ([[j, value] for j, value in enumerate(machine.state["MinV"][:machine.state["Width"] + 1])
                     if not machine.state["Used"][j]] if machine.label_epoch == machine.state["ActiveRow"] else [])
            assert all(math.isfinite(value) for _, value in live)
            trace.append([*[machine.state[name] for name in ("ActiveRow", "I0", "J0", "J1", "Delta")], live])
        if machine.state.get("MarkerMarks", 0):
            for j, used in enumerate(machine.state["Used"][:machine.state["Width"] + 1]):
                # Between row epochs, old labels are deliberately not consumed.
                if machine.state.get("MarkerRow") == machine.state["ActiveRow"] and used:
                    assert math.isinf(machine.state["MinV"][j]) and machine.state["MinV"][j] > 0
    machine.trace = trace
    return machine, work, calls, masks


def compare(reference, actual):
    for name in ("Assignment", "Succeeded", "P", "Way", "U", "V", "Cur"):
        assert equal(reference.get(name, 0), actual.get(name, 0)), (name, reference.get(name, 0), actual.get(name, 0),
            actual.get('Scores'), actual.get('Used'), actual.get('ImplicitWorkerCount'))
    # A final root shortcut does not initialize any labels. Its stale labels,
    # including formerly used markers, are dead; live labels are compared at
    # every selection boundary by the trace instead of mistaking them for state.


def reserve_matrix(matrix, u, v, workers, quality, coverage, column_bonus):
    result = []
    for row, values in enumerate(matrix):
        scores = []
        for column, value in enumerate(values):
            reduced = ((0.0 - value) - u[row + 1]) - v[column + 1]
            if value >= 0.0 and -1e-5 <= reduced <= 1e-5:
                score = quality[column] if row >= workers and column < workers else 0.0
                if column < workers and (row >= workers or row % 2 == 0):
                    score = score + coverage
                if v[column + 1] < -1e-5:
                    score = score + column_bonus
                scores.append(score)
            else:
                scores.append(-1e20)
        result.append(scores)
    return result


def run():
    graphs, symbol = emitted(Path(__file__).with_name("generate_solver.py"))
    candidate = prototype_graphs(graphs, symbol)
    from solver_used_label_marker_prototype import render
    from test_solver_native_relaxation_model import parser, check_structure
    parse, _ = parser()
    for name in ("MarkerAdvance", "MarkerAdvanceNativeRelaxation"):
        reparsed = parse(render(candidate[name], symbol))
        check_structure({name: reparsed})
        assert reparsed == candidate[name], ("editor DSL roundtrip", name)
    matrix = [[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]]
    reference, old_work, _, old_masks = run_one(graphs, symbol, matrix, 1, False, 2)
    actual, new_work, _, new_masks = run_one(candidate, symbol, matrix, 1, True, 2)
    compare(reference.state, actual.state)
    assert actual.state.get("MarkerMarks", 0) > 0, "Used-label marker is not active"
    assert old_masks > 0 and new_masks == 0, (old_masks, new_masks)
    assert new_work < old_work, (old_work, new_work)
    matrices = [matrix, [[math.nan, 0.0]], [[math.inf, 0.0]], [[-math.inf, 0.0]],
        [[-0.0, 0.0, 0.0], [0.0, -0.0, 0.0]],
        [[199999999999999.97, -.09, 99999999999999.92, 200000000000000.06],
         [-.05, 200000000000000.06, 200000000000000.1, -.05],
         [.02, -.05, -.01, -.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]]]
    rng = random.Random(817521)
    for _ in range(70):
        rows, cols = rng.randint(1, 6), rng.randint(1, 9)
        matrices.append([[rng.choice([-1e20, -.09, -0.0, 0.0, .125, 1.03, 7., 1e14+.06])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = total_masks = marks = total_old_work = total_new_work = 0
    for limit in (1, 3, 64):
        reused = reused_reference = None
        for dummy in (False, True):
            for number, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[number % 4]
                reference, old, _, count = run_one(graphs, symbol, matrix, limit, False, prefix, dummy, reuse=reused_reference)
                actual, new, _, new_count = run_one(candidate, symbol, matrix, limit, True, prefix, dummy, reuse=reused)
                compare(reference.state, actual.state)
                assert equal(reference.trace, actual.trace), (limit, dummy, number, "selection trace")
                assert new_count == 0
                if dummy:
                    assert actual.state.get("MarkerMarks", 0) == 0
                comparisons += 1
                total_masks += count
                marks += actual.state.get("MarkerMarks", 0)
                total_old_work += old
                total_new_work += new
                reused = actual
                reused_reference = reference
    from test_solver_cached_trace import benchmark_matrices
    reserve_work = []
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix, quality, coverage, column_bonus = benchmark_matrices(size)
            reference, old, _, count = run_one(graphs, symbol, matrix, limit, False, size, implicit=True)
            actual, new, _, new_count = run_one(candidate, symbol, matrix, limit, True, size, implicit=True)
            compare(reference.state, actual.state)
            assert equal(reference.trace, actual.trace), (limit, size, "implicit selection trace")
            assert new_count == 0
            comparisons += 1
            total_masks += count
            marks += actual.state["MarkerMarks"]
            total_old_work += old
            total_new_work += new
            later = reserve_matrix(matrix, reference.state['U'], reference.state['V'], size,
                                   quality, coverage, column_bonus)
            reference, old, _, count = run_one(graphs, symbol, later, limit, False, size)
            actual, new, _, new_count = run_one(candidate, symbol, later, limit, True, size)
            compare(reference.state, actual.state)
            assert equal(reference.trace, actual.trace), (limit, size, "reserve selection trace")
            assert new_count == 0, (limit, size, old, new)
            reserve_work.append((size, limit, old, new))
            comparisons += 1
            total_masks += count
            marks += actual.state["MarkerMarks"]
    # Cancellation is checked before any marker write or phase dispatch.
    seen = set()
    stopped = SolverMachine(candidate, symbol, 1)
    initialize(stopped, matrices[0], True, 2)
    while not stopped.state["Done"]:
        key = stopped.state["SolverState"], stopped.state.get("NativePhase", 0)
        if key not in seen:
            import copy
            saved = copy.deepcopy(stopped.state)
            stopped.state["Done"] = True
            expected = copy.deepcopy(stopped.state)
            expected["LastStepWork"] = 0
            stopped.invoke("MarkerAdvance")
            assert all(equal(stopped.state[name], value) for name, value in expected.items()), ("cancellation", key)
            stopped.state = saved
            seen.add(key)
            if key == (11, 0):
                stopped.state = copy.deepcopy(saved)
                stopped.state['StepWorkLimit'] = 0
                expected = copy.deepcopy(stopped.state)
                expected.update(Done=True, Succeeded=False, LastStepWork=0)
                stopped.invoke('MarkerAdvance')
                assert all(equal(stopped.state[name], value) for name, value in expected.items()), 'zero budget'
                stopped.state = saved
        stopped.invoke("MarkerAdvance")
    assert total_masks > 0 and marks > 0 and (11, 4) in seen
    assert any(new < old for _, _, old, new in reserve_work), reserve_work
    print(f"WO_USED_LABEL_MARKER_MODEL_PASS comparisons={comparisons} markers={marks} "
          f"removed_mask_calls={total_masks} cancel_states={len(seen)} "
          f"random_and_first_work={total_old_work}->{total_new_work} small_work={old_work}->{new_work} reserve_work={reserve_work}")


if __name__ == "__main__":
    run()
