"""Exact 1000-worker mixed-priority cases, separate from uniform-priority timings."""

import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(__file__).parent))
from benchmark_large_settlement import run_fixture


def run():
    size, reserve = 1000, 3
    expected = {
        "coverage": [100, 100, 100, 100, 100],
        "counts": [197, 200, 200, 200, 200],
        "quality": [19700.0, 20000.0, 20000.0, 20000.0, 20000.0],
        "builder": 3.0,
    }
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ThousandPriorityBenchmark.json")
    report = {
        "target_seconds": 15.0,
        "timing_scope": "Editor planner execution including Python calls; excludes fixture matrix generation, editor startup, world scoring and application.",
        "fixture_scope": "1000 workers, 500 two-slot buildings distributed evenly across priorities 0 through 4, three reserved workers of equal quality.",
        "approximation": False,
        "expected_objective": expected,
        "results": [],
    }
    for strict in (True, False):
        name = "mixed_priorities_strict" if strict else "mixed_priorities_weighted"
        started = time.perf_counter()
        try:
            result = run_fixture(size, strict, uniform=False, reserve=reserve,
                                 builder_quality=None)
            result["case"] = name
            assert result["objective"] == expected, (result["objective"], expected)
            assert result["expected_objective"] == expected
        except Exception as exc:
            result = {"case": name, "workers": size, "reserve": reserve,
                      "strict": strict, "uniform_priority": False, "mode": "unique",
                      "exact_objective_verified": False, "under_15_seconds": False,
                      "attempt_seconds": time.perf_counter() - started,
                      "error": f"{type(exc).__name__}: {exc}"}
            unreal.log_error("WO_THOUSAND_PRIORITY_CASE_FAILED " + json.dumps(result))
        report["results"].append(result)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        unreal.log("WO_THOUSAND_PRIORITY_RESULT " + json.dumps({
            key: value for key, value in result.items() if key != "stages"}))
    failures = [result["case"] for result in report["results"]
                if not result["exact_objective_verified"] or not result["under_15_seconds"]]
    unreal.log("WO_THOUSAND_PRIORITY_BENCHMARK_SAVED " + str(output))
    assert not failures, f"Mixed-priority exactness or under-15-second target failed: {failures}; both results saved to {output}"
    unreal.log("WO_THOUSAND_PRIORITY_BENCHMARK_PASS: strict and weighted mixed-priority fixtures below 15 seconds each; not full-world timings")


if __name__ == "__main__":
    run()
