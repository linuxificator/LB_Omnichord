param(
    [switch] $Windowed,
    [string] $CaptureScreenshotsDir
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $env:LOCALAPPDATA "LB_Omnichord"
$readyFile = Join-Path $runtimeDir "amy.pipe"
$pipeName = "LB_Omnichord_AMY_" + [guid]::NewGuid().ToString("N")
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue $readyFile

$quotedReadyFile = '"' + $readyFile + '"'
$serviceArguments = @(
    "--pipe-name", $pipeName, "--ready-file", $quotedReadyFile
)
if ($CaptureScreenshotsDir) {
    # Screenshot capture is an ordinary non-interactive frontend feature. Its
    # service can render offline and stop when the frontend disconnects.
    $serviceArguments += @("--no-audio", "--once")
}
$service = Start-Process -FilePath (Join-Path $root "amy_service.exe") `
    -ArgumentList $serviceArguments -PassThru -NoNewWindow
try {
    for ($i = 0; $i -lt 160; $i++) {
        if ($service.HasExited) { throw "AMY service stopped during startup" }
        if (Test-Path $readyFile) { break }
        Start-Sleep -Milliseconds 50
    }
    if (-not (Test-Path $readyFile)) { throw "AMY service did not publish its pipe" }

    $publishedPipeName = (Get-Content -Raw $readyFile).Trim()
    if ($publishedPipeName -ne $pipeName) {
        throw "AMY service published invalid pipe name: $publishedPipeName"
    }
    Remove-Item -Force $readyFile

    $arguments = @("--amy-local-name", $pipeName)
    if ($Windowed) { $arguments += "--windowed" }
    if ($CaptureScreenshotsDir) {
        $arguments += @("--capture-screenshots-dir", $CaptureScreenshotsDir)
    }
    & (Join-Path $root "LB_Omnichord.exe") @arguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    if (-not $service.HasExited) {
        Stop-Process -Id $service.Id -Force
        $service.WaitForExit()
    }
    Remove-Item -Force -ErrorAction SilentlyContinue $readyFile
}
