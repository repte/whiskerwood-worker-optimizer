"""Exact 1000-worker cases; persist all results before enforcing the time target."""

import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(__file__).parent))
from benchmark_large_settlement import run_fixture


def run():
    size = 1000
    varied = [0.0] * size
    for row in range(size):
        varied[(row + 17) % size] = float(10000 + row if row % 2 == 0 else row // 2 + 1)
    global_leaders = sorted(range(size), key=lambda worker: varied[worker], reverse=True)[:3]
    assert all(((worker - 17) % size) % 2 == 0 for worker in global_leaders)
    assert sum(varied[worker] for worker in global_leaders) == 32988.0
    cases = [
        ("unique_reserve1_equal", 1, None, "unique", 1.0),
        ("unique_reserve3_equal", 3, None, "unique", 3.0),
        ("unique_reserve3_varied", 3, varied, "unique", 1497.0),
        ("ties_reserve3_varied", 3, varied, "ties", 32988.0),
    ]
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ThousandWorkerBenchmark.json")
    report = {
        "target_seconds": 15.0,
        "timing_scope": "Editor planner execution including Python calls; excludes fixture matrix generation, editor startup, world scoring and application.",
        "approximation": False,
        "results": [],
    }
    for name, reserve, qualities, mode, expected_builder in cases:
        started = time.perf_counter()
        try:
            result = run_fixture(size, True, uniform=True, reserve=reserve,
                                 builder_quality=qualities, mode=mode)
            result["case"] = name
            assert result["objective"]["builder"] == expected_builder, (result["objective"], expected_builder)
            if name == "unique_reserve3_varied":
                assert result["objective"]["builder"] < result["builder_unconstrained_upper_bound"], "The loose reserve bound must not be reported as achievable"
        except Exception as exc:
            result = {"case": name, "workers": size, "reserve": reserve, "mode": mode,
                      "exact_objective_verified": False, "under_15_seconds": False,
                      "attempt_seconds": time.perf_counter() - started,
                      "error": f"{type(exc).__name__}: {exc}"}
            unreal.log_error("WO_THOUSAND_CASE_FAILED " + json.dumps(result))
        report["results"].append(result)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        unreal.log("WO_THOUSAND_RESULT " + json.dumps({key: value for key, value in result.items() if key != "stages"}))
    failures = [result["case"] for result in report["results"]
                if not result["exact_objective_verified"] or not result["under_15_seconds"]]
    unreal.log("WO_THOUSAND_BENCHMARK_SAVED " + str(output))
    assert not failures, f"1000-worker exactness or under-15-second target failed: {failures}; all results saved to {output}"
    unreal.log("WO_THOUSAND_BENCHMARK_PASS: four exact 1000-worker reserve/tie cases below 15 seconds each")


if __name__ == "__main__":
    run()
