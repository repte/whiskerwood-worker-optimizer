$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PackageValidation.ps1')

$prefix = '../../../Whiskerwood/Content/Mods/WorkerOptimizer/'
$expected = @('BP_Startup', 'BP_MapLoad')
$valid = @($expected | ForEach-Object {
    [pscustomobject]@{ Filename = ($prefix + $_ + '.uasset'); Size = '100'; Deleted = 'false' }
})
Assert-WorkerOptimizerEntries -Entries $valid -ExpectedAssets $expected

function Assert-Rejected($Entries, [string]$Case) {
    $rejected = $false
    try { Assert-WorkerOptimizerEntries -Entries $Entries -ExpectedAssets $expected }
    catch { $rejected = $true }
    if (-not $rejected) { throw "Accepted invalid package: $Case" }
}

Assert-Rejected @() 'empty'
Assert-Rejected @($valid[0]) 'missing entry point'
Assert-Rejected ($valid + @($valid[0])) 'duplicate'
foreach ($name in @(
    '../../../Whiskerwood/Content/UI/Icon.uasset',
    '../../../Whiskerwood/Binaries/Win64/WorkerOptimizerEditor.dll',
    ($prefix + '../OtherMod/BP_Startup.uasset'),
    ($prefix + 'PAL_WorkerOptimizer.uasset'),
    ($prefix + 'authoring.py'),
    ($prefix + 'BP_MapLoad.uasset/extra'),
    ($prefix + 'Unknown.uasset')
)) {
    Assert-Rejected ($valid + @([pscustomobject]@{ Filename = $name; Size = '100'; Deleted = 'false' })) $name
}
foreach ($entry in @(
    [pscustomobject]@{ Filename = ($prefix + 'BP_MapLoad.uasset'); Size = '100'; Deleted = 'true' },
    [pscustomobject]@{ Filename = ($prefix + 'BP_MapLoad.uasset'); Size = '0'; Deleted = 'false' },
    [pscustomobject]@{ Filename = ($prefix + 'BP_MapLoad.uasset'); Size = 'invalid'; Deleted = 'false' }
)) { Assert-Rejected @($valid[0], $entry) 'invalid metadata' }
Write-Output 'WO_PACKAGE_VALIDATION_TESTS_PASS: valid entries, boundaries, completeness, duplicates and metadata'
