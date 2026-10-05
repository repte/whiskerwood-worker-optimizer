param(
    [string]$Source = (Join-Path $PSScriptRoot '..\docs\assets\worker-optimizer.png'),
    [string]$Output = (Join-Path $PSScriptRoot 'preview.jpg')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$image = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $Source).Path)
try {
    $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
        Where-Object MimeType -eq 'image/jpeg'
    $parameters = [System.Drawing.Imaging.EncoderParameters]::new(1)
    try {
        $parameters.Param[0] = [System.Drawing.Imaging.EncoderParameter]::new(
            [System.Drawing.Imaging.Encoder]::Quality, [long]90)
        $image.Save([IO.Path]::GetFullPath($Output), $codec, $parameters)
    }
    finally { $parameters.Dispose() }
    if ((Get-Item -LiteralPath $Output).Length -ge 1000000) {
        throw 'Preview exceeds the uploader size limit'
    }
    [pscustomobject]@{File=$Output; Width=$image.Width; Height=$image.Height; Bytes=(Get-Item -LiteralPath $Output).Length}
}
finally { $image.Dispose() }
