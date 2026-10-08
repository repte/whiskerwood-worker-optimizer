"""Measure the compiled planner at the reported scale, with an exact known optimum."""

import hashlib
import json
import math
from pathlib import Path
import time

import unreal


def expected_objective(size, priorities, reserve, builder_quality, mode):
    coverage = [priorities.count(tier) for tier in range(5)]
    counts = [2 * value for value in coverage]
    builder = 0.0
    remaining = reserve
    # Every mandatory row retains its unique best worker. Only optional rows
    # at the lowest available priority can be omitted at the primary optimum.
    for tier in range(5):
        optional = [row for row in range(1, size, 2) if priorities[row // 2] == tier]
        omitted = min(remaining, len(optional))
        counts[tier] -= omitted
        remaining -= omitted
        if mode == "unique":
            qualities = sorted((builder_quality[(row + 17) % size] for row in optional), reverse=True)
            builder += sum(qualities[:omitted])
    assert remaining == 0, "The fixture must leave every mandatory crew staffed"
    if mode == "ties":
        builder = sum(sorted(builder_quality, reverse=True)[:reserve])
    return {"coverage": coverage, "counts": counts,
            "quality": [100.0 * value for value in counts], "builder": builder}


def run_fixture(size, strict, uniform=False, reserve=3, builder_quality=None, mode="unique",
                configure_unfixed=False):
    assert size > 0 and size % 2 == 0, "Two slots per building require a positive even size"
    assert isinstance(reserve, int) and 0 <= reserve <= size // 2
    assert mode in ("unique", "ties"), mode
    rows = workers = size
    buildings = size // 2
    builder_quality = [1.0] * workers if builder_quality is None else list(builder_quality)
    assert len(builder_quality) == workers
    assert all(math.isfinite(value) and 0 <= value <= 1000000 for value in builder_quality)
    scores = [float(100 if mode == "ties" or worker == (row + 17) % workers else 1)
              for row in range(rows) for worker in range(workers)]
    priorities = [2 if uniform else building % 5 for building in range(buildings)]
    expected = expected_objective(size, priorities, reserve, builder_quality, mode)
    planner = unreal.new_object(unreal.load_class(
        None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C"))
    planner.set_editor_property("StepWorkLimit", 64)
    started = time.perf_counter()
    planner.call_method("StartPlan", args=(scores, [r // 2 for r in range(rows)],
                                          [r % 2 == 0 for r in range(rows)], priorities,
                                          workers, strict))
    if configure_unfixed:
        assert planner.call_method("RequireFixedSlots", args=([-1] * rows,))[-1]
    assert planner.call_method("KeepUnassigned", args=(reserve, workers, builder_quality))[-1]
    stages, calls, compiled_seconds, work = {}, 0, 0., 0
    next_progress = started + 15
    while not planner.get_editor_property("PlanDone"):
        state = int(planner.get_editor_property("State"))
        solver_state = int(planner.get_editor_property("SolverState")) if state == 5 else -1
        key = f"planner:{state}/solver:{solver_state}"
        before = time.perf_counter()
        planner.call_method("AdvancePlan")
        elapsed = time.perf_counter() - before
        units = int(planner.get_editor_property("LastStepWork"))
        assert 0 < units <= 64, (key, units)
        item = stages.setdefault(key, {"calls": 0, "seconds": 0., "work": 0, "max_seconds": 0.})
        item["calls"] += 1
        item["seconds"] += elapsed
        item["work"] += units
        item["max_seconds"] = max(item["max_seconds"], elapsed)
        calls += 1
        compiled_seconds += elapsed
        work += units
        now = time.perf_counter()
        if now >= next_progress:
            unreal.log(f"WO_LARGE_PROGRESS workers={workers} strict={strict} reserve={reserve} mode={mode} calls={calls} work={work} state={key} seconds={now-started:.2f}")
            next_progress = now + 15
        if now - started > 300:
            raise AssertionError(f"{workers}-worker planner exceeded 300 seconds: {key}, calls={calls}, work={work}")
    assert planner.get_editor_property("PlanSucceeded")
    assignment = list(planner.get_editor_property("PlanAssignment"))
    assert len(assignment) == rows
    chosen = [worker for worker in assignment if worker >= 0]
    assert len(chosen) == len(set(chosen)) == workers - reserve
    assert all(worker < workers for worker in chosen)
    assert all(assignment[row] >= 0 for row in range(0, rows, 2)), "A mandatory crew lost its worker"
    counts, quality, coverage = [0] * 5, [0.] * 5, [0] * 5
    for building in range(buildings):
        tier = priorities[building]
        occupied = [r for r in (2 * building, 2 * building + 1) if assignment[r] >= 0]
        coverage[tier] += bool(occupied)
        counts[tier] += len(occupied)
        quality[tier] += sum(scores[r * workers + assignment[r]] for r in occupied)
    assert coverage == expected["coverage"], (coverage, expected)
    assert counts == expected["counts"], (counts, expected)
    assert quality == expected["quality"], (quality, expected)
    builder = float(planner.get_editor_property("BuilderTotal"))
    idle = set(range(workers)) - set(chosen)
    assert builder == sum(builder_quality[worker] for worker in idle), "Reported builder quality disagrees with unassigned workers"
    assert builder == expected["builder"], (builder, expected)
    host_seconds = time.perf_counter() - started
    result = {"workers": workers, "rows": rows, "buildings": buildings, "strict": strict,
              "reserve": reserve, "uniform_priority": uniform, "mode": mode, "calls": calls, "work": work,
              "fixed_slots_configured": configure_unfixed,
              "host_seconds": host_seconds, "under_15_seconds": host_seconds < 15.0,
              "compiled_call_sum_seconds": compiled_seconds, "stages": stages,
              "objective": {"coverage": coverage, "counts": counts, "quality": quality, "builder": builder},
              "expected_objective": expected,
              "builder_unconstrained_upper_bound": sum(sorted(builder_quality, reverse=True)[:reserve]),
              "exact_objective_verified": True,
              "assignment_sha256": hashlib.sha256(json.dumps(assignment).encode("ascii")).hexdigest()}
    unreal.log("WO_LARGE_RESULT " + json.dumps({k: v for k, v in result.items() if k != "stages"}))
    return result


if __name__ == "__main__":
    results = []
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-LargeSettlementBenchmark.json")
    for size, strict, uniform in ((600, True, True), (200, False, False),
                                 (200, True, False), (600, False, False), (600, True, False)):
        results.append(run_fixture(size, strict, uniform))
        output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    unreal.log("WO_LARGE_BENCHMARK_PASS: known optimal coverage, counts, productivity and reserve; editor timings, not shipping frame times")
