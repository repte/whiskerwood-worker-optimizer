"""Regenerate coupled reserve/settings assets sequentially to avoid package locks."""

from pathlib import Path
import runpy

for name in ("generate_priority_settings.py", "test_plan_search.py", "generate_controller.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
