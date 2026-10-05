param([string]$ArtifactDirectory = (Join-Path $PSScriptRoot '..\..\Saved\WorkerOptimizerUI'))

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
foreach ($width in @(1920, 1280, 800)) {
    $height = @{1920 = 1080; 1280 = 720; 800 = 600}[$width]
    foreach ($state in @('idle', 'settings')) {
        $path = Join-Path $ArtifactDirectory "$state-$width.png"
        $bitmap = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $path).Path)
        try {
            if ($bitmap.Width -ne $width -or $bitmap.Height -ne $height) { throw "Wrong render size: $path" }
            foreach ($region in @(@{Name='action'; X=26; Y=($height-68); W=32; H=32}, @{Name='settings'; X=74; Y=($height-56); W=16; H=16})) {
                $xs = [System.Collections.Generic.HashSet[int]]::new()
                $ys = [System.Collections.Generic.HashSet[int]]::new()
                for ($y = $region.Y; $y -lt ($region.Y + $region.H); $y++) {
                    for ($x = $region.X; $x -lt ($region.X + $region.W); $x++) {
                        $pixel = $bitmap.GetPixel($x, $y)
                        if ($pixel.A -gt 128 -and $pixel.R -gt 210 -and $pixel.G -gt 210 -and $pixel.B -gt 210) {
                            [void]$xs.Add($x)
                            [void]$ys.Add($y)
                        }
                    }
                }
                if ($xs.Count -lt 7 -or $ys.Count -lt 7) { throw "Missing or compressed $($region.Name) icon: $path ($($xs.Count)x$($ys.Count))" }
            }
            $panel = $bitmap.GetPixel(22, $height - 168)
            if ($state -eq 'idle' -and $panel.A -ne 0) { throw "Collapsed settings panel still paints: $path" }
            if ($state -eq 'settings' -and $panel.A -lt 128) { throw "Settings panel is missing: $path" }
            "WO_WIDGET_PIXELS_PASS $state ${width}x$height"
        }
        finally { $bitmap.Dispose() }
    }
}
