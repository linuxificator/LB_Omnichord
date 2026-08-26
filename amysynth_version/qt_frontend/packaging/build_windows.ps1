$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$frontend = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $frontend "build\windows"
$dist = Join-Path $frontend "dist"
$stamp = if ($env:OMNICHORD_RELEASE_STAMP) { $env:OMNICHORD_RELEASE_STAMP } else { "RDEV" }
$amyRoot = if ($env:OMNICHORD_AMY_ROOT) { $env:OMNICHORD_AMY_ROOT } else { Join-Path $buildRoot "amy" }

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $buildRoot, $dist
New-Item -ItemType Directory -Force -Path $buildRoot, $dist | Out-Null

$cmakeHelp = cmake --help
$generator = @("Visual Studio 18 2026", "Visual Studio 17 2022") |
    Where-Object { $cmakeHelp -match [regex]::Escape($_) } |
    Select-Object -First 1
if (-not $generator) {
    throw "No supported Visual Studio CMake generator is installed"
}

cmake -S (Join-Path $frontend "packaging\windows") -B (Join-Path $buildRoot "amy-build") `
    -G $generator -A x64 "-DAMY_ROOT=$amyRoot"
cmake --build (Join-Path $buildRoot "amy-build") --config Release

$pyDist = Join-Path $buildRoot "pyinstaller"
python -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name LB_Omnichord --distpath $pyDist --workpath (Join-Path $buildRoot "pyinstaller-work") `
    --specpath $buildRoot --paths (Join-Path $frontend "code") `
    --add-data "$(Join-Path $frontend 'licence.txt');." `
    --add-data "$(Join-Path $frontend 'config');config" `
    --add-data "$(Join-Path $frontend 'gui');gui" `
    --add-data "$(Join-Path $frontend 'instruments');instruments" `
    --add-data "$(Join-Path $frontend 'music');music" `
    (Join-Path $frontend "code\main.py")

$packageRoot = Join-Path $buildRoot "LB_Omnichord"
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $pyDist "LB_Omnichord\*") $packageRoot
Copy-Item -Force (Join-Path $buildRoot "amy-build\Release\amy_service.exe") $packageRoot
Copy-Item -Force (Join-Path $PSScriptRoot "windows\run_windows.ps1") $packageRoot
$zip = Join-Path $dist "LB_Omnichord.$stamp.Windows-x86_64.zip"
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zip
Get-FileHash $zip -Algorithm SHA256 | ForEach-Object {
    "$($_.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($zip))"
} | Set-Content -Encoding ascii "$zip.sha256"
Write-Output $zip
