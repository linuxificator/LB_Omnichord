#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sc_dir="$(cd -- "$frontend_dir/../supercollider" && pwd)"
runtime_app="${OMNICHORD_SC_RUNTIME_APP:?set OMNICHORD_SC_RUNTIME_APP to SuperCollider.app}"
build_root="${OMNICHORD_DMG_BUILD_DIR:-$frontend_dir/build/macos-sc}"
output_dir="${OMNICHORD_DMG_OUTPUT_DIR:-$frontend_dir/dist}"
release_stamp="${OMNICHORD_RELEASE_STAMP:?set OMNICHORD_RELEASE_STAMP to RYYYYMMDDHHMMSS}"

case "$release_stamp" in
    R[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) echo "Invalid OMNICHORD_RELEASE_STAMP: $release_stamp" >&2; exit 2 ;;
esac
for required in \
    "$runtime_app/Contents/MacOS/sclang" \
    "$runtime_app/Contents/Resources/scsynth" \
    "$runtime_app/Contents/Resources/supernova" \
    "$runtime_app/Contents/Resources/SCClassLibrary" \
    "$runtime_app/Contents/Resources/plugins"; do
    [[ -e "$required" ]] || { echo "Missing SC runtime input: $required" >&2; exit 2; }
done

pyinstaller_dist="$build_root/pyinstaller-dist"
pyinstaller_work="$build_root/pyinstaller-work"
app_bundle="$pyinstaller_dist/LB_Omnichord_SC.app"
output="$output_dir/LB_Omnichord.SC.${release_stamp}.macOS-arm64.dmg"
qml_evidence="$output.qml-imports.json"
package_audit="$output.package-audit.json"

rm -rf "$build_root"
mkdir -p "$output_dir"
python "$frontend_dir/packaging/qt_runtime_policy.py" \
    --qml-root "$frontend_dir/gui" --output "$qml_evidence"

python -m PyInstaller \
    --noconfirm --clean --windowed \
    --name LB_Omnichord_SC \
    --osx-bundle-identifier org.linuxificator.LB_Omnichord \
    --target-arch arm64 \
    --distpath "$pyinstaller_dist" \
    --workpath "$pyinstaller_work" \
    --specpath "$build_root" \
    --paths "$frontend_dir/code" \
    --additional-hooks-dir "$frontend_dir/packaging/pyinstaller_hooks" \
    --collect-all zeroconf \
    --hidden-import ifaddr \
    --copy-metadata zeroconf \
    --copy-metadata ifaddr \
    --add-data "$frontend_dir/licence.txt:." \
    --add-data "$frontend_dir/THIRD_PARTY_NOTICES.md:." \
    --add-data "$frontend_dir/config:config" \
    --add-data "$frontend_dir/gui:gui" \
    --add-data "$frontend_dir/instruments:instruments" \
    --add-data "$frontend_dir/music:music" \
    --add-data "$sc_dir:supercollider" \
    "$frontend_dir/packaging/sc_appimage_entry.py"

mkdir -p "$app_bundle/Contents/Resources/sc-runtime"
cp -a "$runtime_app" "$app_bundle/Contents/Resources/sc-runtime/SuperCollider.app"
plutil -insert NSLocalNetworkUsageDescription \
    -string "LB Omnichord receives OSC control messages from devices and apps on your local network." \
    "$app_bundle/Contents/Info.plist"
plutil -insert NSBonjourServices -json '["_osc._udp"]' \
    "$app_bundle/Contents/Info.plist"
plutil -lint "$app_bundle/Contents/Info.plist"
codesign --force --deep --sign - "$app_bundle"
"$app_bundle/Contents/MacOS/LB_Omnichord_SC" --verify-package
hdiutil create -volname "LB Omnichord SC" -fs HFS+ -format UDZO \
    -srcfolder "$app_bundle" "$output"
python "$frontend_dir/packaging/package_audit.py" \
    --platform macOS-arm64 --tree "$app_bundle" --package "$output" \
    --forbidden-runtime-exempt-prefix "Contents/Resources/sc-runtime" \
    --max-package-bytes 600000000 --output "$package_audit"
printf '%s\n' "$output"
