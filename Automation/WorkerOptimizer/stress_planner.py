"""Exercise strict-tier tie transitions against fresh, adversarial matrices."""

from pathlib import Path
import random
import runpy
import ctypes
import time

import unreal


class ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


def memory():
    counters = ProcessMemory()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    assert kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.WorkingSetSize, counters.PeakWorkingSetSize


def dense_fixture(size, strict):
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C")
    planner = unreal.new_object(cls)
    scores = [100.0 if w == (r + 17) % size else 1.0 for r in range(size) for w in range(size)]
    buildings = [r // 2 for r in range(size)]
    minimum = [r % 2 == 0 for r in range(size)]
    priorities = [b % 5 for b in range(size // 2)]
    before, _ = memory()
    start = time.perf_counter()
    prep = time.perf_counter()
    planner.call_method("StartPlan", args=(scores, buildings, minimum, priorities, size, strict))
    setup_seconds = time.perf_counter() - prep
    calls, compiled_seconds, max_call = 0, 0.0, 0.0
    max_state, solver_setup_max = -1, 0.0
    passes = 6 if strict else 2
    primitive_bound = 100 + 10 * (2 * size + len(priorities)) + len(priorities) * size * (size + 3)
    primitive_bound += passes * (2 * size * size + size * (size + 1) * (6 * size + 10) + 20 * size)
    for _ in range((primitive_bound + 63) // 64 + 1):
        if planner.get_editor_property("PlanDone"):
            break
        state = planner.get_editor_property("State")
        step = time.perf_counter()
        planner.call_method("AdvancePlan")
        elapsed = time.perf_counter() - step
        compiled_seconds += elapsed
        if elapsed > max_call:
            max_call, max_state = elapsed, state
        if state == 4 and planner.get_editor_property("State") == 5:
            solver_setup_max = max(solver_setup_max, elapsed)
        calls += 1
        assert 0 <= planner.get_editor_property("LastStepWork") <= 64
    host_seconds = time.perf_counter() - start
    assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded"), (size, strict, calls)
    assert list(planner.get_editor_property("PlanAssignment")) == [(r + 17) % size for r in range(size)]
    after, peak = memory()
    arrays = {name: len(planner.get_editor_property(name)) for name in (
        "BaseScores", "PassScores", "Scores", "AllowedEdges", "U", "V", "P", "Way", "Used", "MinV")}
    # Logical element payload only: excludes capacity, UObject/VM and allocator overhead.
    payload = 8 * sum(arrays[n] for n in ("BaseScores", "PassScores", "Scores", "U", "V", "MinV"))
    payload += 4 * (arrays["P"] + arrays["Way"]) + arrays["AllowedEdges"] + arrays["Used"]
    unreal.log(f"WO_PLANNER_SIZE: rows={size} workers={size} buildings={len(priorities)} schools=0 reserve=0 strict={strict} "
               f"limit=64 calls={calls} finite_call_bound={(primitive_bound+63)//64+1} host_s={host_seconds:.6f} "
               f"setup_call_s={setup_seconds:.6f} compiled_call_sum_s={compiled_seconds:.6f} compiled_call_max_s={max_call:.6f} "
               f"max_call_start_state={max_state} solver_setup_transition_max_s={solver_setup_max:.6f} "
               f"process_working_set_before={before} after={after} process_lifetime_peak={peak} selected_array_payload_bytes={payload} "
               f"arrays={arrays}; editor call durations include Python/native dispatch, not shipping frame times")


for size in (50, 200, 500, 1000):
    for strict in (False, True):
        dense_fixture(size, strict)

tests = runpy.run_path(str(Path(__file__).with_name("test_planner.py")))
rng = random.Random(981731)
for case in range(1500):
    buildings = [0, 0, 0, 1, 1, 2]
    minimum = [True, False, False, True, False, True]
    priorities = [rng.randrange(5) for _ in range(3)]
    scores = [[rng.choice([-1, 0, 1, 2, 3]) for _ in range(4)] for _ in buildings]
    try:
        result = tests["plan"](scores, buildings, minimum, priorities, True)
        if case < 100:
            assert tests["policy_key"](result, scores, buildings, minimum, priorities, True) == tests["oracle"](scores, buildings, minimum, priorities, True)
    except Exception:
        unreal.log_error(f"WO_STRICT_COUNTEREXAMPLE: case={case}, scores={scores}, priorities={priorities}, minimum={minimum}")
        raise
unreal.log("WO_PLANNER_STRESS_PASS: 1500 tie-heavy strict cases; first 100 exhaustive")
