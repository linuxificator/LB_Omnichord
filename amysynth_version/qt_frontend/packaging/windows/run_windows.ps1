param(
    [switch] $Windowed,
    [switch] $SmokeTest
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$socketDir = Join-Path $env:LOCALAPPDATA "LB_Omnichord"
$socket = Join-Path $socketDir "amy.sock"
New-Item -ItemType Directory -Force -Path $socketDir | Out-Null

$serviceArguments = @("--socket", $socket)
$serviceOutput = $null
$serviceError = $null
$smokeStatus = $null
if ($SmokeTest) {
    $serviceArguments += @("--no-audio", "--once")
    $serviceOutput = Join-Path $env:TEMP "lb-omnichord-amy-smoke.out"
    $serviceError = Join-Path $env:TEMP "lb-omnichord-amy-smoke.err"
    $smokeStatus = Join-Path $env:TEMP "lb-omnichord-frontend-smoke.status"
    Remove-Item -Force -ErrorAction SilentlyContinue `
        $serviceOutput, $serviceError, $smokeStatus
    $service = Start-Process -FilePath (Join-Path $root "amy_service.exe") `
        -ArgumentList $serviceArguments -PassThru -NoNewWindow `
        -RedirectStandardOutput $serviceOutput -RedirectStandardError $serviceError
}
else {
    $service = Start-Process -FilePath (Join-Path $root "amy_service.exe") `
        -ArgumentList $serviceArguments -PassThru -NoNewWindow
}
try {
    for ($i = 0; $i -lt 160; $i++) {
        if ($service.HasExited) { throw "AMY service stopped during startup" }
        if (Test-Path $socket) { break }
        Start-Sleep -Milliseconds 50
    }
    if (-not (Test-Path $socket)) { throw "AMY service did not publish its socket" }

    $arguments = @("--amy-socket", $socket)
    if ($Windowed) { $arguments += "--windowed" }
    if ($SmokeTest) {
        $arguments += "--package-smoke-test"
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:QT_QUICK_BACKEND = "software"
        $env:OMNICHORD_PACKAGE_SMOKE_STATUS = $smokeStatus
        $frontend = Start-Process -FilePath (Join-Path $root "LB_Omnichord.exe") `
            -ArgumentList $arguments -PassThru
        if (-not $frontend.WaitForExit(30000)) {
            $commandLine = (Get-CimInstance Win32_Process `
                -Filter "ProcessId = $($frontend.Id)").CommandLine
            $status = if (Test-Path $smokeStatus) {
                Get-Content -Raw $smokeStatus
            } else { "<no frontend checkpoints>" }
            $serviceLog = if (Test-Path $serviceOutput) {
                Get-Content -Raw $serviceOutput
            } else { "<no service output>" }
            Stop-Process -Id $frontend.Id -Force
            $frontend.WaitForExit()
            throw (
                "Packaged frontend smoke test exceeded its 30 second deadline`n" +
                "Command: $commandLine`nCheckpoints:`n$status`nService:`n$serviceLog"
            )
        }
        $frontend.WaitForExit()
        if ($frontend.ExitCode -ne 0) {
            throw "Packaged frontend smoke test failed with status $($frontend.ExitCode)"
        }
        $status = if (Test-Path $smokeStatus) {
            Get-Content -Raw $smokeStatus
        } else { "" }
        if ($status -notmatch "event-loop-exited") {
            throw "Packaged frontend did not report a clean Qt event-loop exit"
        }
        if (-not $service.WaitForExit(10000)) {
            throw "AMY smoke service did not exit after the frontend disconnected"
        }
        $service.WaitForExit()
        $stdout = if (Test-Path $serviceOutput) {
            Get-Content -Raw $serviceOutput
        } else { "" }
        $stderr = if (Test-Path $serviceError) {
            Get-Content -Raw $serviceError
        } else { "" }
        Write-Output $stdout
        if ($stderr) { Write-Error $stderr }
        if ($service.ExitCode -ne 0) {
            throw "AMY smoke service failed with status $($service.ExitCode)"
        }
        if ($stdout -notmatch "AMY service smoke passed: [1-9][0-9]* wire commands, [1-9][0-9]* nonzero PCM samples") {
            throw "AMY smoke service did not confirm wire parsing and PCM rendering"
        }
        Write-Output "Windows package smoke test passed"
    }
    else {
        & (Join-Path $root "LB_Omnichord.exe") @arguments
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
finally {
    if (-not $service.HasExited) {
        Stop-Process -Id $service.Id -Force
        $service.WaitForExit()
    }
    Remove-Item -Force -ErrorAction SilentlyContinue $socket
    if ($SmokeTest) {
        Remove-Item -Force -ErrorAction SilentlyContinue `
            $serviceOutput, $serviceError, $smokeStatus
    }
}
