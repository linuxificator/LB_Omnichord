$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$frontend = Split-Path -Parent $PSScriptRoot
$scDir = Resolve-Path (Join-Path $frontend "..\supercollider")
$buildRoot = Join-Path $frontend "build\windows-sc"
$dist = Join-Path $frontend "dist"
$stamp = if ($env:OMNICHORD_RELEASE_STAMP) { $env:OMNICHORD_RELEASE_STAMP } else { throw "OMNICHORD_RELEASE_STAMP is required" }
$releaseName = if ($env:OMNICHORD_RELEASE_NAME) { $env:OMNICHORD_RELEASE_NAME } else { throw "OMNICHORD_RELEASE_NAME is required" }
$runtimeRoot = if ($env:OMNICHORD_SC_RUNTIME_ROOT) { $env:OMNICHORD_SC_RUNTIME_ROOT } else { throw "OMNICHORD_SC_RUNTIME_ROOT is required" }
$zip = Join-Path $dist "LB_Omnichord.SC.$stamp.Windows-x86_64.zip"
$releaseIdentity = Join-Path $buildRoot "release_identity.json"

if ($stamp -notmatch '^R[0-9]{14}$') { throw "Invalid OMNICHORD_RELEASE_STAMP: $stamp" }
@("sclang.exe", "scsynth.exe", "supernova.exe", "SCClassLibrary", "plugins") | ForEach-Object {
    if (-not (Test-Path (Join-Path $runtimeRoot $_))) { throw "Missing SC runtime input: $_" }
}

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $buildRoot
New-Item -ItemType Directory -Force -Path $buildRoot, $dist | Out-Null
python (Join-Path $frontend "packaging\qt_runtime_policy.py") `
    --qml-root (Join-Path $frontend "gui") --output "$zip.qml-imports.json"
python (Join-Path $frontend "code\release_identity.py") `
    --write $releaseIdentity $releaseName

$pyDist = Join-Path $buildRoot "pyinstaller"
python -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name LB_Omnichord_SC --distpath $pyDist `
    --workpath (Join-Path $buildRoot "pyinstaller-work") `
    --specpath $buildRoot --paths (Join-Path $frontend "code") `
    --additional-hooks-dir (Join-Path $frontend "packaging\pyinstaller_hooks") `
    --collect-all zeroconf --hidden-import ifaddr `
    --copy-metadata zeroconf --copy-metadata ifaddr `
    --add-data "$(Join-Path $frontend 'licence.txt');." `
    --add-data "$(Join-Path $frontend 'THIRD_PARTY_NOTICES.md');." `
    --add-data "$(Join-Path $frontend 'config');config" `
    --add-data "$(Join-Path $frontend 'gui');gui" `
    --add-data "$(Join-Path $frontend 'instruments');instruments" `
    --add-data "$(Join-Path $frontend 'music');music" `
    --add-data "$scDir;supercollider" `
    --add-data "$releaseIdentity;." `
    (Join-Path $frontend "packaging\sc_appimage_entry.py")

$packageRoot = Join-Path $buildRoot "LB_Omnichord_SC"
Copy-Item -Recurse -Force (Join-Path $pyDist "LB_Omnichord_SC") $packageRoot
Copy-Item -Recurse -Force $runtimeRoot (Join-Path $packageRoot "sc-runtime")
& (Join-Path $packageRoot "LB_Omnichord_SC.exe") --verify-package
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zip -Force
Get-FileHash $zip -Algorithm SHA256 | ForEach-Object {
    "$($_.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($zip))"
} | Set-Content -Encoding ascii "$zip.sha256"
python (Join-Path $frontend "packaging\package_audit.py") `
    --platform Windows-x86_64 --tree $packageRoot --package $zip `
    --output "$zip.package-audit.json"
Write-Output $zip
