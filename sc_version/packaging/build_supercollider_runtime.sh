#!/usr/bin/env bash
set -euo pipefail

sc_version=3.14.1
source_sha256=ee640c68777ae697682066ce5c4a8b7e56c5b223e76c79c13b5be5387ee55bb2
source_url="https://github.com/supercollider/supercollider/releases/download/Version-${sc_version}/SuperCollider-${sc_version}-Source.tar.bz2"
build_root="${OMNICHORD_SC_BUILD_ROOT:-$PWD/build/supercollider-${sc_version}}"
install_prefix="${OMNICHORD_SC_INSTALL_PREFIX:-$build_root/install}"
archive="${OMNICHORD_SC_SOURCE_ARCHIVE:-$build_root/SuperCollider-${sc_version}-Source.tar.bz2}"
source_root="$build_root/SuperCollider-${sc_version}-Source"

mkdir -p "$build_root"
if [[ ! -f "$archive" ]]; then
    curl -L --fail --silent --show-error "$source_url" -o "$archive"
fi
echo "$source_sha256  $archive" | sha256sum --check --strict
if [[ ! -f "$source_root/CMakeLists.txt" ]]; then
    tar -xjf "$archive" -C "$build_root"
fi

cmake -S "$source_root" -B "$build_root/cmake" --fresh -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$install_prefix" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DSC_QT=OFF \
    -DSC_IDE=OFF \
    -DNO_X11=ON \
    -DSC_HIDAPI=OFF \
    -DSC_ABLETON_LINK=OFF \
    -DSUPERNOVA=OFF \
    -DSCLANG_SERVER=OFF \
    -DINSTALL_HELP=OFF \
    -DENABLE_TESTSUITE=OFF \
    -DNO_AVAHI=ON \
    -DNATIVE=OFF
cmake --build "$build_root/cmake" --parallel "${OMNICHORD_BUILD_JOBS:-$(nproc)}"
cmake --install "$build_root/cmake"

"$install_prefix/bin/sclang" -v | grep -F "$sc_version"
"$install_prefix/bin/scsynth" -v | grep -F "$sc_version"
printf '%s\n' "$install_prefix"
