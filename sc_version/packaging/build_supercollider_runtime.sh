#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
sc_version=3.14.1
source_sha256=ee640c68777ae697682066ce5c4a8b7e56c5b223e76c79c13b5be5387ee55bb2
source_url="https://github.com/supercollider/supercollider/releases/download/Version-${sc_version}/SuperCollider-${sc_version}-Source.tar.bz2"
build_root="${OMNICHORD_SC_BUILD_ROOT:-$PWD/build/supercollider-${sc_version}}"
install_prefix="${OMNICHORD_SC_INSTALL_PREFIX:-$build_root/install}"
archive="${OMNICHORD_SC_SOURCE_ARCHIVE:-$build_root/SuperCollider-${sc_version}-Source.tar.bz2}"
source_root="$build_root/SuperCollider-${sc_version}-Source"
host_system="$(uname -s)"

verify_sha256() {
    if [[ "$host_system" != "Darwin" ]] && command -v sha256sum >/dev/null 2>&1; then
        echo "$source_sha256  $archive" | sha256sum --check --strict
    else
        actual="$(shasum -a 256 "$archive" | awk '{print $1}')"
        [[ "$actual" == "$source_sha256" ]] || {
            echo "SuperCollider source checksum mismatch" >&2
            exit 2
        }
    fi
}

build_jobs="${OMNICHORD_BUILD_JOBS:-}"
if [[ -z "$build_jobs" ]]; then
    if command -v nproc >/dev/null 2>&1; then
        build_jobs="$(nproc)"
    else
        build_jobs="$(sysctl -n hw.ncpu)"
    fi
fi

mkdir -p "$build_root"
if [[ ! -f "$archive" ]]; then
    curl -L --fail --silent --show-error "$source_url" -o "$archive"
fi
verify_sha256
if [[ ! -f "$source_root/CMakeLists.txt" ]]; then
    tar -xjf "$archive" -C "$build_root"
fi

platform_flags=()
if [[ "$host_system" == "Darwin" ]]; then
    # The Qt IDE normally links Foundation transitively. A Qt-free sclang still
    # uses SC's Objective-C filesystem helpers, so declare that native framework
    # directly instead of retaining Qt solely for an incidental link edge.
    platform_flags+=(
        -DCMAKE_OSX_ARCHITECTURES=arm64
        -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0
        "-DCMAKE_EXE_LINKER_FLAGS=-framework Foundation"
        -DAUDIOAPI=portaudio
        -DSYSTEM_PORTAUDIO=OFF
    )
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
    -DSUPERNOVA=ON \
    -DSCLANG_SERVER=OFF \
    -DINSTALL_HELP=OFF \
    -DENABLE_TESTSUITE=OFF \
    -DNO_AVAHI=ON \
    -DNATIVE=OFF \
    "${platform_flags[@]}"
cmake --build "$build_root/cmake" --parallel "$build_jobs"
cmake --install "$build_root/cmake"

if [[ "$host_system" == "Darwin" ]]; then
    runtime_root="$install_prefix/SuperCollider/SuperCollider.app"
    resources="$runtime_root/Contents/Resources"
    cp "$script_dir/headless-macos-Info.plist" "$runtime_root/Contents/Info.plist"
    mkdir -p "$resources/SCClassLibrary"
    rsync -a \
        --exclude='GUI/' \
        --exclude='Ableton/' \
        --exclude='scide_scqt/' \
        "$source_root/SCClassLibrary/" "$resources/SCClassLibrary/"
    executables=(
        "$runtime_root/Contents/MacOS/sclang"
        "$resources/scsynth"
        "$resources/supernova"
    )
    [[ -d "$resources/plugins" ]] || {
        echo "SuperCollider plugins are missing from macOS runtime" >&2
        exit 2
    }
    if find "$runtime_root" -iname '*QtWebEngine*' -print -quit | grep -q .; then
        echo "QtWebEngine is forbidden in the headless macOS runtime" >&2
        exit 2
    fi
    brew_prefix="$(brew --prefix)"
    cmake \
        -DRUNTIME_APP="$runtime_root" \
        -DDEPENDENCY_DIRS="$brew_prefix/lib;$(brew --prefix libsndfile)/lib;$(brew --prefix readline)/lib" \
        -P "$script_dir/fixup_supercollider_macos.cmake"
    codesign --force --deep --sign - "$runtime_root"
else
    runtime_root="$install_prefix"
    executables=(
        "$runtime_root/bin/sclang"
        "$runtime_root/bin/scsynth"
        "$runtime_root/bin/supernova"
    )
fi

for executable in "${executables[@]}"; do
    "$executable" -v | grep -F "$sc_version"
done
printf '%s\n' "$runtime_root"
