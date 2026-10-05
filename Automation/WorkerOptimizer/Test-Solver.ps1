param([string]$EngineRoot = 'D:\WWEngine')

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
if (-not (Test-Path -LiteralPath $editor -PathType Leaf)) {
    throw "Custom editor not found: $editor"
}
$log = Join-Path $projectRoot 'Saved\Logs\WorkerOptimizer-Tests.log'
$consoleLog = Join-Path $projectRoot 'Saved\Logs\WorkerOptimizer-Tests-console.log'
$arguments = @(
    (Join-Path $projectRoot 'Whiskerwood.uproject'),
    ('-ExecutePythonScript=' + (Join-Path $PSScriptRoot 'test_solver.py')),
    '-unattended', '-nullrhi', '-nosound', '-culture=en',
    ('-abslog=' + $log), '-stdout', '-FullStdOutLogOutput'
)
& $editor @arguments *> $consoleLog
if ($LASTEXITCODE -ne 0) { throw "Editor exited with $LASTEXITCODE; see $log" }
$text = Get-Content -LiteralPath $log -Raw
if ($text -match 'LogPython: Error:|LogEditorPythonExecuter: Error:|LogBlueprint: Error:|LogScript: (Error|Warning):') {
    throw "Editor reported a test/runtime error; see $log"
}
$pass = Select-String -LiteralPath $log -Pattern 'WO_SOLVER_TESTS_PASS:'
if (-not $pass) { throw "No solver test pass marker; see $log" }
$pass.Line
