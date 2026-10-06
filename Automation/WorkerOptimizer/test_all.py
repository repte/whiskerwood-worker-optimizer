"""Run all production-Blueprint checks in a fresh editor process."""

from pathlib import Path
import runpy

import unreal

runpy.run_path(str(Path(__file__).with_name("test_flexible_minimum.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_auto_assignment.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_failure_diagnostics.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_run_report.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_logbook.py")), run_name="__main__")
for name in ("test_settings_model.py", "test_settings_panel.py", "test_logbook_view.py", "test_priorities_view.py", "test_ui_design_contract.py", "test_ui_notifications.py", "test_ui_materials.py", "test_ui_frame.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")

for name in ("test_solver.py", "test_planner.py", "test_workplace.py", "test_snapshot.py", "test_native_bridge_authoring.py", "test_action_bridge.py", "test_job_scorer.py", "test_job_eligibility.py", "test_teacher_profiles.py", "test_action_confirmation.py", "test_application_runner.py", "test_action_plan.py", "test_priority_settings.py", "test_definition_catalog.py", "test_score_matrix.py", "test_grouped_matrix.py", "test_plan_search.py", "test_grouped_search.py", "test_controller.py", "test_startup.py", "test_lifecycle.py", "test_hotkey.py", "test_widget.py", "test_ui_lifecycle.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_compatibility.py")), run_name="__main__")
for name in ("test_reserve.py", "test_builder_score.py", "test_localization.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_package_setup.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_startup_layout.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_performance.py")), run_name="__main__")
unreal.log("WO_ALL_TESTS_PASS")
