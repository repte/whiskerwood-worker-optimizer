"""Compiled exact planner acceptance cases for 1500 workers and a five-second target."""

import json
from pathlib import Path
import sys
import time

import unreal

sys.path.insert(0, str(Path(__file__).parent))
from benchmark_large_settlement import run_fixture


# Frozen from the compiled ProductionBaseline run, before the 1500-worker work.
BASELINE_ASSIGNMENTS = {
    'unique_reserve1_equal': '2825dca173cdfa700ce2dd1bee8a0928cb4182c46238e56f96325951c9e61273',
    'unique_reserve3_equal': 'cc17bf9442ae1f2ddb4bc69fa821d7f53cb5c49623a76cf0af83208fb2695883',
    'unique_reserve3_varied': '19b65f7f612990fb864f2987f81c10e75be2fdd69d7e5a6c333bd5f6b15bf712',
    'ties_reserve3_varied': '0316be603135f5528652a1f963e3684117b61b5351ee6e2cd67fd7102363208b',
    'mixed_priorities_strict': 'c02a8f0e35a408d4097722bb1886a83ff6aa6062e1b275c09dc88eb123cf585a',
    'mixed_priorities_weighted': 'c02a8f0e35a408d4097722bb1886a83ff6aa6062e1b275c09dc88eb123cf585a',
}


def verify_baseline_assignment(case, result):
    actual = result['assignment_sha256']
    expected = BASELINE_ASSIGNMENTS[case]
    assert actual == expected, ('assignment differs from ProductionBaseline', case, actual, expected)
    result['baseline_assignment_verified'] = True


def run(repetitions=1, label="measurement"):
    assert isinstance(repetitions, int) and repetitions > 0
    size = 1500
    varied = [0.0] * size
    for row in range(size):
        varied[(row + 17) % size] = float(10000 + row if row % 2 == 0 else row // 2 + 1)
    mixed = {
        "coverage": [150, 150, 150, 150, 150],
        "counts": [297, 300, 300, 300, 300],
        "quality": [29700.0, 30000.0, 30000.0, 30000.0, 30000.0],
        "builder": 3.0,
    }
    cases = [
        ("unique_reserve1_equal", True, True, 1, None, "unique", 1.0),
        ("unique_reserve3_equal", True, True, 3, None, "unique", 3.0),
        ("unique_reserve3_varied", True, True, 3, varied, "unique", 2247.0),
        ("ties_reserve3_varied", True, True, 3, varied, "ties", 34488.0),
        ("mixed_priorities_strict", True, False, 3, None, "unique", 3.0),
        ("mixed_priorities_weighted", False, False, 3, None, "unique", 3.0),
    ]
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-FifteenHundredBenchmark.json")
    report = {
        "label": label,
        "workers": size,
        "target_seconds": 5.0,
        "acceptance_metric": "host_seconds",
        "timing_scope": "Planner initialization including RequireFixedSlots (all unpinned), compiled AdvancePlan calls and Python observation/result validation; excludes fixture generation, editor startup, world scoring, school search, frame scheduling and application.",
        "approximation": False,
        "repetitions": repetitions,
        "results": [],
    }
    for repetition in range(repetitions):
        for name, strict, uniform, reserve, qualities, mode, expected_builder in cases:
            started = time.perf_counter()
            try:
                result = run_fixture(size, strict, uniform=uniform, reserve=reserve,
                                     builder_quality=qualities, mode=mode,
                                     configure_unfixed=True)
                assert result["objective"]["builder"] == expected_builder
                if not uniform:
                    assert result["objective"] == mixed, (result["objective"], mixed)
                if name == "unique_reserve3_varied":
                    assert result["objective"]["builder"] < result["builder_unconstrained_upper_bound"]
                verify_baseline_assignment(name, result)
                result.pop("under_15_seconds", None)
                result["under_5_seconds"] = result["host_seconds"] < 5.0
            except Exception as exc:
                result = {"workers": size, "exact_objective_verified": False,
                          "under_5_seconds": False,
                          "attempt_seconds": time.perf_counter() - started,
                          "error": f"{type(exc).__name__}: {exc}"}
                unreal.log_error("WO_1500_CASE_FAILED " + json.dumps(result))
            result.update(case=name, repetition=repetition + 1)
            report["results"].append(result)
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            unreal.log("WO_1500_RESULT " + json.dumps({
                key: value for key, value in result.items() if key != "stages"}))
    failures = [f"{result['case']}#{result['repetition']}" for result in report["results"]
                if not result["exact_objective_verified"] or not result["under_5_seconds"]]
    report["passed"] = not failures
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    unreal.log("WO_1500_BENCHMARK_SAVED " + str(output))
    assert not failures, f"1500-worker exactness or under-five-second target failed: {failures}"
    unreal.log("WO_1500_BENCHMARK_PASS: all exact planner cases below five seconds")
    return report


if __name__ == "__main__":
    run()
