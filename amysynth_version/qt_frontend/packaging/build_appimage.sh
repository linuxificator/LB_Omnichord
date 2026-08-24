#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="${OMNICHORD_APPIMAGE_BUILD_DIR:-$frontend_dir/build/appimage}"
output_dir="${OMNICHORD_APPIMAGE_OUTPUT_DIR:-$frontend_dir/dist}"
release_stamp="${OMNICHORD_RELEASE_STAMP:?set OMNICHORD_RELEASE_STAMP to RYYYYMMDDHHMMSS}"
appimage_tool="${APPIMAGETOOL:-appimagetool}"
runtime_file="${APPIMAGE_RUNTIME_FILE:-}"
appimage_arch="${OMNICHORD_APPIMAGE_ARCH:-x86_64}"
platform_name="${OMNICHORD_APPIMAGE_PLATFORM:-Linux-x86_64}"

case "$release_stamp" in
    R[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) echo "Invalid OMNICHORD_RELEASE_STAMP: $release_stamp" >&2; exit 2 ;;
esac
case "$appimage_arch" in
    x86_64|aarch64) ;;
    *) echo "Unsupported AppImage architecture: $appimage_arch" >&2; exit 2 ;;
esac
case "$platform_name" in
    Linux-x86_64|RaspberryPi-aarch64) ;;
    *) echo "Unsupported AppImage platform name: $platform_name" >&2; exit 2 ;;
esac

app_dir="$build_root/AppDir"
pyinstaller_dist="$build_root/pyinstaller-dist"
pyinstaller_work="$build_root/pyinstaller-work"
output="$output_dir/LB_Omnichord.${release_stamp}.${platform_name}.AppImage"

rm -rf "$build_root"
mkdir -p \
    "$app_dir/usr/lib/LB_Omnichord" \
    "$app_dir/usr/share/applications" \
    "$output_dir"

python -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name LB_Omnichord \
    --distpath "$pyinstaller_dist" \
    --workpath "$pyinstaller_work" \
    --specpath "$build_root" \
    --paths "$frontend_dir/code" \
    --hidden-import c_amy \
    --collect-all amy \
    --add-data "$frontend_dir/licence.txt:." \
    --add-data "$frontend_dir/config:config" \
    --add-data "$frontend_dir/gui:gui" \
    --add-data "$frontend_dir/instruments:instruments" \
    --add-data "$frontend_dir/music:music" \
    "$frontend_dir/packaging/appimage_entry.py"

cp -a "$pyinstaller_dist/LB_Omnichord/." "$app_dir/usr/lib/LB_Omnichord/"
install -Dm755 /dev/stdin "$app_dir/AppRun" <<'EOF'
#!/usr/bin/env bash
set -e
app_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
exec "$app_dir/usr/lib/LB_Omnichord/LB_Omnichord" "$@"
EOF
install -Dm644 \
    "$frontend_dir/packaging/org.linuxificator.LB_Omnichord.desktop" \
    "$app_dir/org.linuxificator.LB_Omnichord.desktop"
install -Dm644 \
    "$frontend_dir/packaging/org.linuxificator.LB_Omnichord.appdata.xml" \
    "$app_dir/usr/share/metainfo/org.linuxificator.LB_Omnichord.appdata.xml"
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
printf '%s\n' "$output"
