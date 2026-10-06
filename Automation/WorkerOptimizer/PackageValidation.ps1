function Assert-WorkerOptimizerEntries {
    param(
        [AllowEmptyCollection()][object[]]$Entries,
        [Parameter(Mandatory)][string[]]$ExpectedAssets
    )
    if (-not $Entries -or -not $ExpectedAssets) { throw 'Empty mod package or asset inventory' }
    $nonRuntimeNamePart = '(^|_)(Editor|Tests?|Probes?)(_|$)'
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $assets = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($entry in $Entries) {
        $path = [string]$entry.Filename
        if ($path -cnotmatch '^\.\./\.\./\.\./Whiskerwood/Content/Mods/WorkerOptimizer/([A-Za-z0-9_]+)\.(uasset|uexp|ubulk|uptnl)$') {
            throw "File outside mod asset boundary: $path"
        }
        $name, $extension = $Matches[1], $Matches[2]
        # Check semantic name parts even when the source inventory includes a fixture.
        $nameParts = [regex]::Replace($name, '([A-Z]+)([A-Z][a-z])', '$1_$2')
        $nameParts = [regex]::Replace($nameParts, '([a-z0-9])([A-Z])', '$1_$2')
        if ($name -imatch $nonRuntimeNamePart -or $nameParts -imatch $nonRuntimeNamePart) {
            throw "Non-runtime asset in mod package: $path"
        }
        if ($name -cnotin $ExpectedAssets) { throw "Unexpected asset: $path" }
        if (-not $seen.Add($path)) { throw "Duplicate entry: $path" }
        $size = 0L
        if (-not [long]::TryParse(([string]$entry.Size).Trim(), [ref]$size) -or $size -le 0) {
            throw "Invalid size: $path"
        }
        if (([string]$entry.Deleted).Trim() -cne 'false') { throw "Deleted or invalid entry: $path" }
        if ($extension -ceq 'uasset') { [void]$assets.Add($name) }
    }
    foreach ($name in $ExpectedAssets) {
        if (-not $assets.Contains($name)) { throw "Missing cooked asset: $name" }
    }
}
