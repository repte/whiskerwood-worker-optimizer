"""Exercise strict-tier tie transitions against fresh, adversarial matrices."""

from pathlib import Path
import random
import runpy

import unreal

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
