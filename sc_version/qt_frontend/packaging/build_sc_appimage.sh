#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sc_dir="$(cd -- "$frontend_dir/../supercollider" && pwd)"
runtime_prefix="${OMNICHORD_SC_RUNTIME_PREFIX:?set OMNICHORD_SC_RUNTIME_PREFIX}"
build_root="${OMNICHORD_SC_APPIMAGE_BUILD_DIR:-$frontend_dir/build/sc-appimage}"
output_dir="${OMNICHORD_SC_APPIMAGE_OUTPUT_DIR:-$frontend_dir/dist}"
release_stamp="${OMNICHORD_RELEASE_STAMP:?set OMNICHORD_RELEASE_STAMP to RYYYYMMDDHHMMSS}"
appimage_tool="${APPIMAGETOOL:-appimagetool}"
runtime_file="${APPIMAGE_RUNTIME_FILE:-}"
appimage_arch="${OMNICHORD_SC_APPIMAGE_ARCH:-x86_64}"
platform_name="${OMNICHORD_SC_APPIMAGE_PLATFORM:-Linux-x86_64}"

case "$release_stamp" in
    R[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) echo "Invalid OMNICHORD_RELEASE_STAMP: $release_stamp" >&2; exit 2 ;;
esac
for required in \
    "$runtime_prefix/bin/sclang" \
    "$runtime_prefix/bin/scsynth" \
    "$runtime_prefix/bin/supernova" \
    "$runtime_prefix/share/SuperCollider/SCClassLibrary" \
    "$runtime_prefix/lib/SuperCollider/plugins"; do
    [[ -e "$required" ]] || { echo "Missing SC runtime input: $required" >&2; exit 2; }
done

app_dir="$build_root/AppDir"
pyinstaller_dist="$build_root/pyinstaller-dist"
pyinstaller_work="$build_root/pyinstaller-work"
output="$output_dir/LB_Omnichord.SC.${release_stamp}.${platform_name}.AppImage"
qml_evidence="$output.qml-imports.json"
package_audit="$output.package-audit.json"

mkdir -p \
    "$app_dir/usr/lib/LB_Omnichord" \
    "$app_dir/usr/share/applications" \
    "$output_dir"

python "$frontend_dir/packaging/qt_runtime_policy.py" \
    --qml-root "$frontend_dir/gui" \
    --output "$qml_evidence"

python -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name LB_Omnichord_SC \
    --distpath "$pyinstaller_dist" \
    --workpath "$pyinstaller_work" \
    --specpath "$build_root" \
    --paths "$frontend_dir/code" \
    --additional-hooks-dir "$frontend_dir/packaging/pyinstaller_hooks" \
    --collect-all zeroconf \
    --hidden-import ifaddr \
    --copy-metadata zeroconf \
    --copy-metadata ifaddr \
    --copy-metadata dulwich \
    --copy-metadata urllib3 \
    --add-data "$frontend_dir/licence.txt:." \
    --add-data "$frontend_dir/THIRD_PARTY_NOTICES.md:." \
    --add-data "$frontend_dir/config:config" \
    --add-data "$frontend_dir/gui:gui" \
    --add-data "$frontend_dir/instruments:instruments" \
    --add-data "$frontend_dir/music:music" \
    --add-data "$sc_dir:supercollider" \
    "$frontend_dir/packaging/sc_appimage_entry.py"

cp -a "$pyinstaller_dist/LB_Omnichord_SC/." "$app_dir/usr/lib/LB_Omnichord/"
cp -a "$runtime_prefix" "$app_dir/usr/lib/LB_Omnichord/sc-runtime"
python "$frontend_dir/packaging/bundle_sc_elf_dependencies.py" \
    "$app_dir/usr/lib/LB_Omnichord/sc-runtime"

# Raspberry Pi OS must provide the C++ runtime used by its Mesa/V3D stack.
# The SC edition contains a PyInstaller runtime and a separately bundled SC
# runtime, so remove the Ubuntu-builder copy from both locations. This is the
# same host-graphics compatibility rule as the regular Raspberry Pi AppImage.
if [[ "$platform_name" == "RaspberryPi-aarch64" ]]; then
    rm -f -- \
        "$app_dir/usr/lib/LB_Omnichord/_internal/libstdc++.so.6" \
        "$app_dir/usr/lib/LB_Omnichord/sc-runtime/lib/libstdc++.so.6"
fi

install -Dm755 /dev/stdin "$app_dir/AppRun" <<'EOF'
#!/usr/bin/env bash
set -e
app_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
exec "$app_dir/usr/lib/LB_Omnichord/LB_Omnichord_SC" "$@"
EOF
install -Dm644 \
    "$frontend_dir/packaging/org.linuxificator.LB_Omnichord.desktop" \
    "$app_dir/org.linuxificator.LB_Omnichord.desktop"
install -Dm644 "$frontend_dir/gui/tuba_watermark.png" \
    "$app_dir/LB_Omnichord.png"
ln -s ../../../org.linuxificator.LB_Omnichord.desktop \
    "$app_dir/usr/share/applications/org.linuxificator.LB_Omnichord.desktop"

runtime_args=()
if [[ -n "$runtime_file" ]]; then
    runtime_args=(--runtime-file "$runtime_file")
fi
ARCH="$appimage_arch" "$appimage_tool" "${runtime_args[@]}" "$app_dir" "$output"
chmod +x "$output"
python "$frontend_dir/packaging/package_audit.py" \
    --platform "$platform_name" \
    --tree "$app_dir" \
    --package "$output" \
    --max-package-bytes 240000000 \
    --output "$package_audit"
printf '%s\n' "$output"
