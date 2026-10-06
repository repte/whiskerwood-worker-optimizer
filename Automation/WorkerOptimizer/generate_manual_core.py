"""Rebuild the approved manual-only surface and native assignment path."""
from pathlib import Path
import runpy

import unreal

for name in (
    "generate_job_eligibility.py", "generate_action_bridge.py",
    "generate_application_runner.py", "generate_action_plan.py",
    "generate_problem_layout.py",
    "generate_score_matrix.py",
    "generate_priority_settings.py", "generate_controller.py",
    "generate_widget.py", "generate_lifecycle.py",
    "test_manual_surface.py", "test_manual_application.py", "test_native_fire_dependencies.py", "test_pinned_incumbents.py",
):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
unreal.log("WO_MANUAL_CORE_GENERATED")
