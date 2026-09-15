$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScVersion = "3.14.1"
$SourceSha256 = "ee640c68777ae697682066ce5c4a8b7e56c5b223e76c79c13b5be5387ee55bb2"
$SourceUrl = "https://github.com/supercollider/supercollider/releases/download/Version-$ScVersion/SuperCollider-$ScVersion-Source.tar.bz2"
$AsioSha256 = "d5ebf0c20dd2c5f43771fd0c1418f4b361bf52434ee670097cfa6b3a335e2eca"
$AsioUrl = "https://www.steinberg.net/asiosdk"
$BuildRoot = if ($env:OMNICHORD_SC_BUILD_ROOT) {
    $env:OMNICHORD_SC_BUILD_ROOT
} else {
    Join-Path $PWD "build\supercollider-$ScVersion"
}
$InstallPrefix = if ($env:OMNICHORD_SC_INSTALL_PREFIX) {
    $env:OMNICHORD_SC_INSTALL_PREFIX
} else {
    Join-Path $BuildRoot "install"
}
$Archive = Join-Path $BuildRoot "SuperCollider-$ScVersion-Source.tar.bz2"
$SourceRoot = Join-Path $BuildRoot "SuperCollider-$ScVersion-Source"
$AsioArchive = Join-Path $BuildRoot "asiosdk.zip"
$VcpkgRoot = $env:VCPKG_INSTALLATION_ROOT
if (-not $VcpkgRoot) {
    throw "VCPKG_INSTALLATION_ROOT is required for the Windows runtime build"
}
$Triplet = "x64-windows-release"
$VcpkgBin = Join-Path $VcpkgRoot "installed\$Triplet\bin"

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
if (-not (Test-Path $Archive)) {
    Invoke-WebRequest $SourceUrl -OutFile $Archive
}
if ((Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SourceSha256) {
    throw "SuperCollider source checksum mismatch"
}
if (-not (Test-Path (Join-Path $SourceRoot "CMakeLists.txt"))) {
    tar -xjf $Archive -C $BuildRoot
}

if (-not (Test-Path $AsioArchive)) {
    Invoke-WebRequest $AsioUrl -OutFile $AsioArchive
}
if ((Get-FileHash $AsioArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $AsioSha256) {
    throw "ASIO SDK checksum mismatch"
}
$PortaudioRoot = Join-Path $SourceRoot "external_libraries\portaudio"
$AsioRoot = Join-Path $PortaudioRoot "asiosdk"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $AsioRoot
Expand-Archive $AsioArchive $PortaudioRoot -Force
$ExtractedAsio = Join-Path $PortaudioRoot "ASIOSDK"
if (-not (Test-Path $ExtractedAsio)) {
    throw "ASIO SDK archive has no ASIOSDK root directory"
}

& (Join-Path $VcpkgRoot "vcpkg.exe") install `
    "libsndfile[core]:$Triplet" "fftw3:$Triplet"

$CmakeRoot = Join-Path $BuildRoot "cmake"
cmake -S $SourceRoot -B $CmakeRoot --fresh `
    "-DCMAKE_BUILD_TYPE=Release" `
    "-DCMAKE_INSTALL_PREFIX=$InstallPrefix" `
    "-DCMAKE_TOOLCHAIN_FILE=$(Join-Path $VcpkgRoot 'scripts\buildsystems\vcpkg.cmake')" `
    "-DVCPKG_TARGET_TRIPLET=$Triplet" `
    "-DFFTW3F_LIBRARY_DIR=$VcpkgBin" `
    "-DSNDFILE_LIBRARY_DIR=$VcpkgBin" `
    "-DSC_QT=OFF" `
    "-DSC_IDE=OFF" `
    "-DNO_X11=ON" `
    "-DSC_HIDAPI=OFF" `
    "-DSC_ABLETON_LINK=OFF" `
    "-DSUPERNOVA=ON" `
    "-DSCLANG_SERVER=OFF" `
    "-DINSTALL_HELP=OFF" `
    "-DENABLE_TESTSUITE=OFF" `
    "-DNO_AVAHI=ON" `
    "-DSYSTEM_PORTAUDIO=OFF" `
    "-DPA_USE_ASIO=ON"
cmake --build $CmakeRoot --config Release --target install --parallel 2

$RuntimeRoot = Join-Path $InstallPrefix "SuperCollider"
@("sclang.exe", "scsynth.exe", "supernova.exe", "SCClassLibrary", "plugins") |
    ForEach-Object {
        if (-not (Test-Path (Join-Path $RuntimeRoot $_))) {
            throw "Windows headless runtime is missing $_"
        }
    }
cmake "-DRUNTIME_ROOT=$RuntimeRoot" "-DDEPENDENCY_DIRS=$VcpkgBin" `
    -P (Join-Path $ScriptRoot "fixup_supercollider_windows.cmake")
$LicenseRoot = Join-Path $RuntimeRoot "licenses"
New-Item -ItemType Directory -Force -Path $LicenseRoot | Out-Null
Copy-Item (Join-Path $ExtractedAsio "LICENSE.txt") `
    (Join-Path $LicenseRoot "ASIO-SDK-LICENSE.txt")
if (Get-ChildItem $RuntimeRoot -Recurse -File | Where-Object {
    $_.Name -match '^Qt(5|6)|WebEngine|scide'
}) {
    throw "Qt or the SuperCollider IDE leaked into the Windows headless runtime"
}
@("sclang.exe", "scsynth.exe", "supernova.exe") | ForEach-Object {
    $Output = & (Join-Path $RuntimeRoot $_) -v 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $Output -notmatch [regex]::Escape($ScVersion)) {
        throw "Runtime verification failed for $_`: $Output"
    }
}
Write-Output $RuntimeRoot
