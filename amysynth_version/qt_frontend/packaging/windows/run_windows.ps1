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
        $quotedCaptureDir = '"' + $CaptureScreenshotsDir + '"'
        $arguments += @("--capture-screenshots-dir", $quotedCaptureDir)
    }
    # Windows PowerShell does not necessarily wait when invoking a GUI-
    # subsystem executable with `&`. Keep the launcher, its AMY service and
    # the frontend in one explicit lifetime by owning the frontend process.
    $frontend = Start-Process -FilePath (Join-Path $root "LB_Omnichord.exe") `
        -ArgumentList $arguments -PassThru
    $frontend.WaitForExit()
    if ($frontend.ExitCode -ne 0) { exit $frontend.ExitCode }
}
finally {
    if ($CaptureScreenshotsDir -and -not $service.HasExited) {
        # The one-shot service exits itself after frontend disconnect. Let it
        # flush its final audio/session record before using forced cleanup.
        $service.WaitForExit(5000) | Out-Null
    }
    if (-not $service.HasExited) {
        Stop-Process -Id $service.Id -Force
        $service.WaitForExit()
    }
    Remove-Item -Force -ErrorAction SilentlyContinue $readyFile
}
