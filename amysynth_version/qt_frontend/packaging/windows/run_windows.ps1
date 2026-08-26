param(
    [switch] $Windowed
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$socketDir = Join-Path $env:LOCALAPPDATA "LB_Omnichord"
$socket = Join-Path $socketDir "amy.sock"
New-Item -ItemType Directory -Force -Path $socketDir | Out-Null

$service = Start-Process -FilePath (Join-Path $root "amy_service.exe") `
    -ArgumentList @("--socket", $socket) -PassThru -NoNewWindow
try {
    for ($i = 0; $i -lt 160; $i++) {
        if ($service.HasExited) { throw "AMY service stopped during startup" }
        if (Test-Path $socket) { break }
        Start-Sleep -Milliseconds 50
    }
    if (-not (Test-Path $socket)) { throw "AMY service did not publish its socket" }

    $arguments = @("--amy-socket", $socket)
    if ($Windowed) { $arguments += "--windowed" }
    & (Join-Path $root "LB_Omnichord.exe") @arguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    if (-not $service.HasExited) {
        Stop-Process -Id $service.Id -Force
        $service.WaitForExit()
    }
    Remove-Item -Force -ErrorAction SilentlyContinue $socket
}
