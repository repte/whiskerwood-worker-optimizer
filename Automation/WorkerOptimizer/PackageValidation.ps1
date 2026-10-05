function Assert-WorkerOptimizerEntries {
    param(
        [AllowEmptyCollection()][object[]]$Entries,
        [Parameter(Mandatory)][string[]]$ExpectedAssets
    )
    if (-not $Entries -or -not $ExpectedAssets) { throw 'Empty mod package or asset inventory' }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $assets = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($entry in $Entries) {
        $path = [string]$entry.Filename
        if ($path -cnotmatch '^\.\./\.\./\.\./Whiskerwood/Content/Mods/WorkerOptimizer/([A-Za-z0-9_]+)\.(uasset|uexp|ubulk|uptnl)$') {
            throw "File outside mod asset boundary: $path"
        }
        $name, $extension = $Matches[1], $Matches[2]
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
