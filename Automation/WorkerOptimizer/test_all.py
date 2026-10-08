"""Run all production-Blueprint checks in a fresh editor process."""

from pathlib import Path
import runpy
import sys

import unreal

sys.path.insert(0, str(Path(__file__).parent))

for name in ("test_solver_work.py", "test_planner_tiers.py", "test_search_pruning.py",
             "test_reserve_bound.py", "test_planner_batching.py", "test_solver_row_bound.py",
             "test_planner_validation.py", "test_planner_unfixed_validation.py",
             "test_planner_native_validation.py", "test_planner_fused_matrix.py",
             "test_planner_validated_scores.py", "test_planner_coverage_batching.py",
             "test_planner_coverage_root.py",
             "test_solver_zero_label.py", "test_planner_sparse_pass.py", "test_planner_sparse_refinement.py",
             "test_planner_single_max_template.py",
             "test_planner_implicit_pass.py", "test_planner_deferred_matrix.py",
             "test_planner_refine_certificate.py", "test_solver_relaxation_bound.py",
             "test_solver_native_relaxation.py", "test_solver_real_prefix_skip.py",
             "test_solver_potential_batch.py", "test_solver_native_mask_batch.py",
             "test_solver_first_free_cache.py", "test_solver_dummy_suffix_bound.py", "test_solver_dead_labels.py",
             "test_solver_integer_u_production.py",
             "test_solver_integer_v_production.py",
             "test_solver_integer_minv_production.py",
             "test_solver_dyadic_eighths_production.py",
             "test_solver_zero_epoch_production.py",
             "test_solver_label_upper_bound_production.py",
             "test_planner_refinement_cache.py",
             "test_solver_masked_reuse.py", "test_planner_validation_state.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")

for name in ("test_manual_surface.py", "test_manual_application.py", "test_native_fire_dependencies.py", "test_pinned_incumbents.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")

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
runpy.run_path(str(Path(__file__).with_name("test_gameplay_visibility.py")), run_name="__main__")
for name in ("test_reserve.py", "test_builder_score.py", "test_localization.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_package_setup.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_startup_layout.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_performance.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_fifteen_hundred_baseline_model.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_solver_relaxation_range_model.py")), run_name="__main__")
runpy.run_path(str(Path(__file__).with_name("test_solver_prepare_fusion_model.py")), run_name="__main__")
unreal.log("WO_ALL_TESTS_PASS")
