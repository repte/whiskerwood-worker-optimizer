param([string]$EngineRoot = 'D:\WWEngine')

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$editor = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$uat = Join-Path $EngineRoot 'Engine\Build\BatchFiles\RunUAT.bat'
$project = Join-Path $projectRoot 'Whiskerwood.uproject'
$id = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$output = Join-Path $projectRoot "Saved\WorkerOptimizerBuilds\$id"
$logs = Join-Path $projectRoot 'Saved\Logs'
[void](New-Item -ItemType Directory -Path $logs -Force)
$setupLog = Join-Path $logs "WorkerOptimizer-PackageSetup-$id.log"
& $editor $project ("-ExecutePythonScript=" + (Join-Path $PSScriptRoot 'prepare_package.py')) `
    -unattended -nullrhi -nosound -culture=en ("-abslog=$setupLog") -stdout -FullStdOutLogOutput `
    *> (Join-Path $logs "WorkerOptimizer-PackageSetup-$id-console.log")
if ($LASTEXITCODE -ne 0) { throw "Package setup failed: $setupLog" }
$setupText = Get-Content -LiteralPath $setupLog -Raw
if ($setupText -notmatch 'WO_PACKAGE_SETUP_TESTS_PASS' -or $setupText -match 'LogPython: Error:|LogEditorPythonExecuter: Error:') {
    throw "Package setup not verified: $setupLog"
}
foreach ($marker in @('WO_UI_MATERIALS_READY', 'WO_UI_MATERIALS_TESTS_PASS')) {
    if ($setupText -notmatch $marker) { throw "Missing $marker in package setup: $setupLog" }
}
$setup = Get-Content -LiteralPath (Join-Path $projectRoot 'Saved\WorkerOptimizer-PackageSetup.json') -Raw | ConvertFrom-Json
if ($setup.mod -cne 'WorkerOptimizer' -or $setup.chunk -lt 1 -or $setup.chunk -gt 300) { throw 'Invalid chunk metadata' }
& (Join-Path $PSScriptRoot 'Test-Mod.ps1') -EngineRoot $EngineRoot
& (Join-Path $PSScriptRoot 'Test-PackageValidation.ps1')

$cookLog = Join-Path $logs "WorkerOptimizer-Build-$id.log"
# Full cooks avoid stale unversioned Blueprint data after native/reflection changes.
& $uat BuildCookRun ("-project=$project") -platform=Win64 -clientconfig=Shipping `
    -build -cook -stage -pak -archive ("-archivedirectory=$output") `
    -nocompileeditor -installed -nop4 -utf8output -unattended -WaitForUATMutex *> $cookLog
if ($LASTEXITCODE -ne 0) { throw "Cook/package failed: $cookLog" }
if ((Get-Content -LiteralPath $cookLog -Raw) -notmatch 'BUILD SUCCESSFUL') {
    throw "Build success marker missing: $cookLog"
}
$chunkPak = Join-Path $output ("Windows\Whiskerwood\Content\Paks\pakchunk" + $setup.chunk + '-Windows.pak')
$verification = & (Join-Path $PSScriptRoot 'Test-Package.ps1') -PakPath $chunkPak -EngineRoot $EngineRoot
$deliveryRoot = Join-Path $output 'Delivery'
$modDir = Join-Path $deliveryRoot 'WorkerOptimizer'
[void](New-Item -ItemType Directory -Path $modDir)
Copy-Item -LiteralPath $chunkPak -Destination (Join-Path $modDir 'WorkerOptimizer.pak')
Copy-Item -LiteralPath (Join-Path $projectRoot 'Content\Mods\WorkerOptimizer\WorkerOptimizer.uplugin') -Destination $modDir
$copiedHash = (Get-FileHash -LiteralPath (Join-Path $modDir 'WorkerOptimizer.pak') -Algorithm SHA256).Hash
if ($copiedHash -cne $verification.SHA256) { throw 'Delivery copy hash mismatch' }
$verification | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $deliveryRoot 'package-verification.json') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $projectRoot 'Docs\WorkerOptimizer\SPIELTEST.md') -Destination $deliveryRoot
Write-Output "WO_BUILD_MOD_PASS: $modDir"
Write-Output 'Development package only. No installation, gameplay verification or Workshop publication performed.'
