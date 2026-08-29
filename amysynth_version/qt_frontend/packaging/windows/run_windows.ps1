param(
    [switch] $Windowed,
    [switch] $SmokeTest
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
            $serviceErrors = if (Test-Path $serviceError) {
                Get-Content -Raw $serviceError
            } else { "<no service errors>" }
            Stop-Process -Id $frontend.Id -Force
            $frontend.WaitForExit()
            throw (
                "Packaged frontend smoke test exceeded its 30 second deadline`n" +
                "Command: $commandLine`nCheckpoints:`n$status`n" +
                "Service:`n$serviceLog`nService errors:`n$serviceErrors"
            )
        }
        $frontend.WaitForExit()
        if ($frontend.ExitCode -ne 0) {
            $status = if (Test-Path $smokeStatus) {
                Get-Content -Raw $smokeStatus
            } else { "<no frontend checkpoints>" }
            $serviceLog = if (Test-Path $serviceOutput) {
                Get-Content -Raw $serviceOutput
            } else { "<no service output>" }
            $serviceErrors = if (Test-Path $serviceError) {
                Get-Content -Raw $serviceError
            } else { "<no service errors>" }
            throw (
                "Packaged frontend smoke test failed with status " +
                "$($frontend.ExitCode)`nCheckpoints:`n$status`n" +
                "Service:`n$serviceLog`nService errors:`n$serviceErrors"
            )
        }
        $status = if (Test-Path $smokeStatus) {
            Get-Content -Raw $smokeStatus
        } else { "" }
        $requiredCheckpoints = @(
            "qml-root-ready",
            "qml-chord-press-observed",
            "active-chord-visible",
            "qml-chord-tap-released",
            "qml-chord-hold-promoted",
            "qml-chord-hold-released",
            "event-loop-exited"
        )
        foreach ($checkpoint in $requiredCheckpoints) {
            if ($status -notmatch [regex]::Escape($checkpoint)) {
                throw "Packaged frontend missed smoke checkpoint: $checkpoint"
            }
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
    Remove-Item -Force -ErrorAction SilentlyContinue $readyFile
    if ($SmokeTest) {
        Remove-Item -Force -ErrorAction SilentlyContinue `
            $serviceOutput, $serviceError, $smokeStatus
    }
}
