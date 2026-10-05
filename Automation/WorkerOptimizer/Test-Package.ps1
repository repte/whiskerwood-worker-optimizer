param(
    [Parameter(Mandatory)][string]$PakPath,
    [string]$EngineRoot = 'D:\WWEngine'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PackageValidation.ps1')
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pak = (Resolve-Path -LiteralPath $PakPath).Path
$unrealPak = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealPak.exe'
$logs = Join-Path $projectRoot 'Saved\Logs'
$id = [guid]::NewGuid().ToString('N')
$csv = Join-Path $logs "WorkerOptimizer-Pak-$id.csv"
$listLog = Join-Path $logs "WorkerOptimizer-Pak-$id-list.log"
$integrityLog = Join-Path $logs "WorkerOptimizer-Pak-$id-integrity.log"
& $unrealPak $pak -List -ExtractToMountPoint ("-CSV=$csv") -unattended *> $listLog
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $csv)) { throw "Pak listing failed: $listLog" }
$entries = @(Get-Content -LiteralPath $csv | Select-Object -Skip 1 | ConvertFrom-Csv -Header Filename,Offset,Size,Hash,Deleted,Compressed,CompressionMethod)
$expected = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'Content\Mods\WorkerOptimizer') -Filter '*.uasset' |
    Where-Object { $_.BaseName -ne 'PAL_WorkerOptimizer' } | Select-Object -ExpandProperty BaseName)
Assert-WorkerOptimizerEntries -Entries $entries -ExpectedAssets $expected
& $unrealPak $pak -Verify -unattended *> $integrityLog
if ($LASTEXITCODE -ne 0) { throw "Pak integrity check failed: $integrityLog" }
$integrity = Get-Content -LiteralPath $integrityLog -Raw
if ($integrity -notmatch 'Pak file .* healthy' -or $integrity -match 'LogPakFile: Error:') {
    throw "Pak integrity success not confirmed: $integrityLog"
}
[pscustomobject]@{
    Result = 'WO_PACKAGE_TESTS_PASS'
    Pak = $pak
    Assets = $expected.Count
    Entries = $entries.Count
    Bytes = (Get-Item -LiteralPath $pak).Length
    SHA256 = (Get-FileHash -LiteralPath $pak -Algorithm SHA256).Hash
    Inventory = $csv
    IntegrityLog = $integrityLog
}
