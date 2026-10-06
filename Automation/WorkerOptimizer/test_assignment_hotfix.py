"""Focused compiled regressions for assignment recovery and terminal feedback."""
from pathlib import Path
import runpy
import traceback

import unreal

failures = []
for name in ("test_failure_diagnostics.py", "test_controller.py", "test_widget.py", "test_logbook_view.py"):
    try:
        runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
    except Exception as error:
        failures.append((name, str(error)))
        unreal.log_warning(f"WO_HOTFIX_REGRESSION_FAILED: {name}: {error}")
        unreal.log_warning(traceback.format_exc())
assert not failures, failures
unreal.log("WO_ASSIGNMENT_HOTFIX_TESTS_PASS")
