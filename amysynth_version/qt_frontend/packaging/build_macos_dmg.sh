#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="${OMNICHORD_DMG_BUILD_DIR:-$frontend_dir/build/macos}"
output_dir="${OMNICHORD_DMG_OUTPUT_DIR:-$frontend_dir/dist}"
release_stamp="${OMNICHORD_RELEASE_STAMP:?set OMNICHORD_RELEASE_STAMP to RYYYYMMDDHHMMSS}"

case "$release_stamp" in
    R[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) echo "Invalid OMNICHORD_RELEASE_STAMP: $release_stamp" >&2; exit 2 ;;
esac

pyinstaller_dist="$build_root/pyinstaller-dist"
pyinstaller_work="$build_root/pyinstaller-work"
app_bundle="$pyinstaller_dist/LB_Omnichord.app"
output="$output_dir/LB_Omnichord.${release_stamp}.macOS-arm64.dmg"
qml_evidence="$output.qml-imports.json"
package_audit="$output.package-audit.json"

rm -rf "$build_root"
mkdir -p "$output_dir"

python "$frontend_dir/packaging/qt_runtime_policy.py" \
    --qml-root "$frontend_dir/gui" \
    --output "$qml_evidence"

python -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name LB_Omnichord \
    --osx-bundle-identifier org.linuxificator.LB_Omnichord \
    --target-arch arm64 \
    --distpath "$pyinstaller_dist" \
    --workpath "$pyinstaller_work" \
    --specpath "$build_root" \
    --paths "$frontend_dir/code" \
    --additional-hooks-dir "$frontend_dir/packaging/pyinstaller_hooks" \
    --hidden-import c_amy \
    --collect-all amy \
    --add-data "$frontend_dir/licence.txt:." \
    --add-data "$frontend_dir/config:config" \
    --add-data "$frontend_dir/gui:gui" \
    --add-data "$frontend_dir/instruments:instruments" \
    --add-data "$frontend_dir/music:music" \
    "$frontend_dir/packaging/appimage_entry.py"

plutil -insert NSLocalNetworkUsageDescription \
    -string "LB Omnichord receives OSC control messages from devices and apps on your local network." \
    "$app_bundle/Contents/Info.plist"
plutil -lint "$app_bundle/Contents/Info.plist"
codesign --force --deep --sign - "$app_bundle"
hdiutil create \
    -volname "LB Omnichord" \
    -fs HFS+ \
    -format UDZO \
    -srcfolder "$app_bundle" \
    "$output"
python "$frontend_dir/packaging/package_audit.py" \
    --platform macOS-arm64 \
    --tree "$app_bundle" \
    --package "$output" \
    --output "$package_audit"
printf '%s\n' "$output"
