$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PackageValidation.ps1')

$prefix = '../../../Whiskerwood/Content/Mods/WorkerOptimizer/'
$expected = @('BP_Startup', 'BP_MapLoad', 'T_WorkerOptimizerFrame', 'T_WorkerOptimizerShadow',
    'T_WorkerOptimizerStatusCompleted', 'T_WorkerOptimizerStatusProblems',
    'T_WorkerOptimizerStatusError', 'T_WorkerOptimizerStatusAborted',
    'T_WorkerOptimizerPriorityOwn', 'T_WorkerOptimizerPriorityInherited')
$valid = @($expected | ForEach-Object {
    [pscustomobject]@{ Filename = ($prefix + $_ + '.uasset'); Size = '100'; Deleted = 'false' }
})
Assert-WorkerOptimizerEntries -Entries $valid -ExpectedAssets $expected

function Assert-Rejected($Entries, [string]$Case, [string[]]$ExpectedAssets = $expected) {
    $rejected = $false
    try { Assert-WorkerOptimizerEntries -Entries $Entries -ExpectedAssets $ExpectedAssets }
    catch { $rejected = $true }
    if (-not $rejected) { throw "Accepted invalid package: $Case" }
}

Assert-Rejected @() 'empty'
Assert-Rejected @($valid[0]) 'missing entry point'
foreach ($texture in @($expected | Where-Object { $_ -clike 'T_*' })) {
    Assert-Rejected @($valid | Where-Object { $_.Filename -cne ($prefix + $texture + '.uasset') }) "missing $texture"
}
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
)) { Assert-Rejected (@($valid | Where-Object { $_.Filename -cne ($prefix + 'BP_MapLoad.uasset') }) + @($entry)) 'invalid metadata' }
foreach ($name in @('WBP_UIEntryProbe', 'BP_TestFixture', 'BP_WorkerOptimizerEditor',
    'BP_WorkerOptimizerTests', 'WBP_EditorProbe', 'BP_fixture_tEsT', 'WBP_pRoBe', 'BP_eDiToR_inputs')) {
    $entry = [pscustomobject]@{ Filename = ($prefix + $name + '.uasset'); Size = '100'; Deleted = 'false' }
    Assert-Rejected ($valid + @($entry)) "non-runtime asset included in source inventory: $name" ($expected + @($name))
}
foreach ($name in @('BP_ContestResults', 'BP_LatestRun', 'BP_ProblemLayout', 'BP_ProbeableState')) {
    $entry = [pscustomobject]@{ Filename = ($prefix + $name + '.uasset'); Size = '100'; Deleted = 'false' }
    Assert-WorkerOptimizerEntries -Entries ($valid + @($entry)) -ExpectedAssets ($expected + @($name))
}
Write-Output 'WO_PACKAGE_VALIDATION_TESTS_PASS: valid entries, boundaries, completeness, duplicates, metadata and non-runtime asset rejection'
