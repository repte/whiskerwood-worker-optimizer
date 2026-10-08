param([string]$EngineRoot = 'D:\WWEngine')

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) {
    throw "Custom editor not found: $editor"
}
$log = Join-Path $projectRoot 'Saved\Logs\WorkerOptimizer-AllTests.log'
$consoleLog = Join-Path $projectRoot 'Saved\Logs\WorkerOptimizer-AllTests-console.log'
$arguments = @(
    (Join-Path $projectRoot 'Whiskerwood.uproject'),
    ('-ExecutePythonScript=' + (Join-Path $PSScriptRoot 'test_all.py')),
    '-unattended', '-nullrhi', '-nosound', '-culture=en',
    ('-abslog=' + $log), '-stdout', '-FullStdOutLogOutput'
)
& $editor @arguments *> $consoleLog
if ($LASTEXITCODE -ne 0) { throw "Editor exited with $LASTEXITCODE; see $log" }
$text = Get-Content -LiteralPath $log -Raw
foreach ($marker in @('WO_SOLVER_ZERO_LABEL_TESTS_PASS', 'WO_PLANNER_SPARSE_PASS_TESTS_PASS', 'WO_PLANNER_SPARSE_REFINEMENT_TESTS_PASS', 'WO_PLANNER_IMPLICIT_PASS_TESTS_PASS', 'WO_PLANNER_DEFERRED_MATRIX_TESTS_PASS', 'WO_PLANNER_REFINE_CERTIFICATE_TESTS_PASS', 'WO_SOLVER_RELAXATION_BOUND_TESTS_PASS', 'WO_NATIVE_SOLVER_TESTS_PASS', 'WO_PLANNER_REFINEMENT_CACHE_TESTS_PASS', 'WO_NATIVE_MASK_REUSE_TESTS_PASS', 'WO_PLANNER_VALIDATION_STATE_TESTS_PASS')) {
    if ($text -notmatch $marker) { throw "Missing $marker; see $log" }
}
if ($text -match 'LogPython: Error:|LogEditorPythonExecuter: Error:|LogBlueprint: Error:|LogScript: (Error|Warning):') {
    throw "Editor reported a test/runtime error; see $log"
}
foreach ($marker in @('WO_SOLVER_WORK_TESTS_PASS', 'WO_PLANNER_TIERS_TESTS_PASS', 'WO_SEARCH_PRUNING_TESTS_PASS', 'WO_RESERVE_BOUND_TESTS_PASS', 'WO_PLANNER_BATCHING_TESTS_PASS', 'WO_SOLVER_ROW_BOUND_TESTS_PASS', 'WO_PLANNER_VALIDATION_TESTS_PASS', 'WO_PLANNER_FUSED_MATRIX_TESTS_PASS', 'WO_PLANNER_VALIDATED_SCORES_PASS', 'WO_PLANNER_COVERAGE_BATCHING_TESTS_PASS')) {
    $pass = Select-String -LiteralPath $log -Pattern $marker
    if (-not $pass) { throw "Missing $marker; see $log" }
    $pass.Line
}
foreach ($marker in @('WO_MANUAL_SURFACE_TESTS_PASS', 'WO_MANUAL_APPLICATION_TESTS_PASS', 'WO_SOLVER_TESTS_PASS', 'WO_PLANNER_TESTS_PASS', 'WO_WORKPLACE_TESTS_PASS', 'WO_SNAPSHOT_TESTS_PASS', 'WO_NATIVE_BRIDGE_AUTHORING_PASS', 'WO_ACTION_BRIDGE_TESTS_PASS', 'WO_JOB_SCORER_TESTS_PASS', 'WO_JOB_ELIGIBILITY_TESTS_PASS', 'WO_TEACHER_PROFILES_TESTS_PASS', 'WO_ACTION_CONFIRMATION_TESTS_PASS', 'WO_APPLICATION_RUNNER_TESTS_PASS', 'WO_ACTION_PLAN_TESTS_PASS', 'WO_PRIORITY_SETTINGS_TESTS_PASS', 'WO_DEFINITION_CATALOG_TESTS_PASS', 'WO_SCORE_MATRIX_TESTS_PASS', 'WO_GROUPED_MATRIX_TESTS_PASS', 'WO_PLAN_SEARCH_TESTS_PASS', 'WO_GROUPED_SEARCH_TESTS_PASS', 'WO_CONTROLLER_TESTS_PASS', 'WO_STARTUP_TESTS_PASS', 'WO_LIFECYCLE_TESTS_PASS', 'WO_HOTKEY_TESTS_PASS', 'WO_WIDGET_TESTS_PASS', 'WO_UI_LIFECYCLE_TESTS_PASS', 'WO_ALL_TESTS_PASS')) {
    $pass = Select-String -LiteralPath $log -Pattern $marker
    if (-not $pass) { throw "Missing $marker; see $log" }
    $pass.Line
}
$packageSetup = Select-String -LiteralPath $log -Pattern 'WO_PACKAGE_SETUP_TESTS_PASS'
if ($text -notmatch 'WO_GAMEPLAY_VISIBILITY_TESTS_PASS') { throw "Missing gameplay visibility checks; see $log" }
if ($text -notmatch 'WO_NATIVE_FIRE_DEPENDENCIES_TESTS_PASS') { throw "Missing native fire dependency checks; see $log" }
if ($text -notmatch 'WO_PINNED_INCUMBENTS_TESTS_PASS') { throw "Missing pinned incumbent checks; see $log" }
if (-not $packageSetup) { throw "Missing WO_PACKAGE_SETUP_TESTS_PASS; see $log" }
$packageSetup.Line
$compatibility = Select-String -LiteralPath $log -Pattern 'WO_COMPATIBILITY_TESTS_PASS'
if (-not $compatibility) { throw "Missing WO_COMPATIBILITY_TESTS_PASS; see $log" }
$compatibility.Line
foreach ($marker in @('WO_RESERVE_TESTS_PASS', 'WO_BUILDER_SCORE_TESTS_PASS', 'WO_LOCALIZATION_TESTS_PASS', 'WO_STARTUP_LAYOUT_TESTS_PASS', 'WO_PERFORMANCE_TESTS_PASS', 'WO_FLEXIBLE_MINIMUM_TESTS_PASS', 'WO_POLICY_INPUT_BOUNDARY_TESTS_PASS', 'WO_AUTO_ASSIGNMENT_TESTS_PASS', 'WO_RUN_REPORT_TESTS_PASS', 'WO_LOGBOOK_TESTS_PASS', 'WO_SETTINGS_MODEL_TESTS_PASS', 'WO_SETTINGS_PANEL_TESTS_PASS', 'WO_LOGBOOK_VIEW_TESTS_PASS', 'WO_FAILURE_DIAGNOSTICS_TESTS_PASS')) {
    $pass = Select-String -LiteralPath $log -Pattern $marker
    if (-not $pass) { throw "Missing $marker; see $log" }
    $pass.Line
}
$frozenQuality = Select-String -LiteralPath $log -Pattern 'WO_FROZEN_QUALITY_TESTS_PASS'
if (-not $frozenQuality) { throw "Missing WO_FROZEN_QUALITY_TESTS_PASS; see $log" }
$frozenQuality.Line
foreach ($marker in @('WO_PRIORITIES_VIEW_TESTS_PASS', 'WO_UI_DESIGN_CONTRACT_PASS', 'WO_UI_NOTIFICATIONS_NATIVE_PASS', 'WO_UI_MATERIALS_TESTS_PASS', 'WO_UI_FRAME_ASSETS_PASS', 'WO_UI_STATUS_ICONS_NATIVE_PASS')) {
    $pass = Select-String -LiteralPath $log -Pattern $marker
    if (-not $pass) { throw "Missing $marker; see $log" }
    $pass.Line
}
