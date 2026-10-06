param([string]$ArtifactDirectory = (Join-Path $PSScriptRoot '..\..\Saved\WorkerOptimizerUI'))

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$manifestPath = Join-Path $ArtifactDirectory 'render-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$tokens = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'ui_tokens.json') -Raw | ConvertFrom-Json
$statusColors = @{}
foreach ($entry in @{ completed='ok'; problems='warn'; error='err'; aborted='abort' }.GetEnumerator()) {
    $statusColors[$entry.Key] = [System.Drawing.ColorTranslator]::FromHtml($tokens.farben.($entry.Value).hex)
}
if (-not $manifest.synthetic_editor_fixture -or $manifest.simulated_slate_scale -ne 1.25 -or -not $manifest.native_editor_culture_per_frame) {
    throw 'Expected the explicitly identified synthetic native-UMG render fixture at simulated 1.25 scale.'
}
foreach ($frame in $manifest.frames) {
    if (($frame.native_editor_culture -split '-')[0] -ne $frame.language) { throw "Native culture mismatch: $($frame.file)" }
}
if ($manifest.frames.Count -ne 52) { throw 'Incomplete native render matrix; expected the existing 48 frames plus four HUD outcome frames.' }
foreach ($state in @('completed','problems','error','aborted')) {
    $outcome = @($manifest.frames | Where-Object { $_.hud_state -eq $state })
    if ($outcome.Count -ne 1 -or $outcome[0].file -ne "de-general-1920x1080-hud-$state.png") { throw "Missing bounded HUD outcome frame: $state" }
    foreach ($regionName in @('hud-action','hud-badge')) {
        if (@($outcome[0].regions | Where-Object { $_.name -eq $regionName }).Count -ne 1) { throw "Missing native HUD region: $state/$regionName" }
    }
}
$stress = @($manifest.frames | Where-Object { $_.history_stress })
if ($stress.Count -ne 1 -or $stress[0].elapsed_render_ms -le 0) { throw 'Missing timed native history stress frame.' }
$stressRuns = @($stress[0].virtualization | Where-Object { $_.widget -eq 'RunRows' })
if ($stressRuns.Count -ne 1 -or $stressRuns[0].source_items -ne 500 -or $stressRuns[0].displayed_entries -le 0 -or $stressRuns[0].displayed_entries -ge 500) { throw 'History stress did not demonstrate native 500-item virtualization.' }
foreach ($language in @('de','ja','zh','ko','ru')) {
    foreach ($tab in @('general','priorities','logbook')) {
        foreach ($dimensions in @('1280x720','1920x1080','2560x1080')) {
            $expected = "$language-$tab-$dimensions.png"
            if (@($manifest.frames | Where-Object { $_.file -eq $expected }).Count -ne 1) { throw "Missing or duplicated render: $expected" }
        }
    }
}

function Assert-Contained($inner, $outer, [string]$context) {
    $tolerance = 2.0
    if ($inner.width -le 0 -or $inner.height -le 0 -or
        $inner.x -lt ($outer.x - $tolerance) -or $inner.y -lt ($outer.y - $tolerance) -or
        ($inner.x + $inner.width) -gt ($outer.x + $outer.width + $tolerance) -or
        ($inner.y + $inner.height) -gt ($outer.y + $outer.height + $tolerance)) {
        throw "Native geometry leaves its container: $context"
    }
}

function Measure-Paint($bitmap, $region, [int]$stride = 4, [System.Drawing.Color]$expectedColor = [System.Drawing.Color]::Empty) {
    $left = [Math]::Max(0, [int][Math]::Ceiling($region.x))
    $top = [Math]::Max(0, [int][Math]::Ceiling($region.y))
    $right = [Math]::Min($bitmap.Width, [int][Math]::Floor($region.x + $region.width))
    $bottom = [Math]::Min($bitmap.Height, [int][Math]::Floor($region.y + $region.height))
    $painted = 0
    $bright = 0
    $samples = 0
    $statusPixels = 0
    for ($y = $top; $y -lt $bottom; $y += $stride) {
        for ($x = $left; $x -lt $right; $x += $stride) {
            $pixel = $bitmap.GetPixel($x, $y)
            $samples++
            if ($pixel.A -gt 128) {
                $painted++
                if (($pixel.R + $pixel.G + $pixel.B) -gt 330) { $bright++ }
            }
            # Ignore antialiased edges and the underlying gold action arrow.
            if (-not $expectedColor.IsEmpty -and $pixel.A -ge 240 -and
                [Math]::Abs([int]$pixel.R - [int]$expectedColor.R) -le 8 -and
                [Math]::Abs([int]$pixel.G - [int]$expectedColor.G) -le 8 -and
                [Math]::Abs([int]$pixel.B - [int]$expectedColor.B) -le 8) {
                $statusPixels++
            }
        }
    }
    return @{ Samples=$samples; Painted=$painted; Bright=$bright; StatusPixels=$statusPixels }
}

foreach ($frame in $manifest.frames) {
    $path = Join-Path $ArtifactDirectory $frame.file
    $bitmap = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $path).Path)
    try {
        if ($bitmap.Width -ne $frame.width -or $bitmap.Height -ne $frame.height) { throw "Wrong image dimensions: $path" }
        $image = @{ x=0; y=0; width=$bitmap.Width; height=$bitmap.Height }
        $panel = @($frame.regions | Where-Object { $_.name -eq 'panel' })[0]
        if (-not $panel) { throw "Missing measured panel geometry: $path" }
        Assert-Contained $panel $image $path
        $panelPaint = Measure-Paint $bitmap $panel
        if ($panelPaint.Samples -lt 200 -or ($panelPaint.Painted / [double]$panelPaint.Samples) -lt 0.7) { throw "Native panel is blank or mostly transparent: $path" }
        foreach ($region in $frame.regions) {
            if ($region.name -like 'hud-*') { Assert-Contained $region $image "$($frame.file):$($region.name)" }
            else { Assert-Contained $region $panel "$($frame.file):$($region.name)" }
            if ($region.name -eq 'hud-badge') {
                if (-not $statusColors.ContainsKey($frame.hud_state)) { throw "Unknown HUD badge state: $($frame.hud_state)" }
                $paint = Measure-Paint $bitmap $region 1 $statusColors[$frame.hud_state]
                $minimum = [Math]::Max(8, [Math]::Ceiling($paint.Samples * 0.08))
                if ($paint.StatusPixels -lt $minimum) {
                    throw "Missing $($frame.hud_state) badge-colored pixels: $($frame.file), $($paint.StatusPixels)/$($paint.Samples), required $minimum"
                }
                "WO_WIDGET_BADGE_PIXELS_PASS $($frame.hud_state): $($paint.StatusPixels)/$($paint.Samples) status-colored pixels"
            }
            else {
                $paint = Measure-Paint $bitmap $region
                if ($paint.Bright -lt 5) { throw "No readable text/icon paint in measured native region: $($frame.file):$($region.name)" }
            }
        }
        foreach ($font in $frame.fonts) {
            if ($font.size_su -lt 13) { throw "Font below 13 SU: $($frame.file):$($font.name)" }
        }
        foreach ($list in $frame.virtualization) {
            if ($list.displayed_entries -le 0 -or $list.displayed_entries -gt $list.source_items) { throw "Invalid native entry counts: $($frame.file):$($list.widget)" }
            if ($list.widget -ne 'DetailRows' -and $list.displayed_entries -ge $list.source_items) { throw "Long list instantiated every source row: $($frame.file):$($list.widget)" }
        }
        if ($frame.tab -eq 'logbook') {
            $left = @($frame.regions | Where-Object { $_.name -eq 'history-list' })[0]
            $right = @($frame.regions | Where-Object { $_.name -eq 'history-details' })[0]
            $intersectionWidth = [Math]::Min($left.x+$left.width,$right.x+$right.width)-[Math]::Max($left.x,$right.x)
            $intersectionHeight = [Math]::Min($left.y+$left.height,$right.y+$right.height)-[Math]::Max($left.y,$right.y)
            if ($intersectionWidth -gt 2 -and $intersectionHeight -gt 2) { throw "History list and details overlap: $($frame.file)" }
        }
        "WO_WIDGET_PIXELS_FRAME_PASS $($frame.file)"
    }
    finally { $bitmap.Dispose() }
}
"WO_WIDGET_HISTORY_STRESS_PASS:500 source items, $($stressRuns[0].displayed_entries) native visible entries, $($stress[0].elapsed_render_ms) ms two-pass render. Stored history remains 50."
'WO_WIDGET_PIXELS_PASS:52 native UMG frames; measured bounds, status-specific HUD badge pixels, minimum fonts, visible paint and bounded entry counts. Glyph shape quality and gameplay input still require visual/runtime acceptance.'
