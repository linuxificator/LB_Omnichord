#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$project_dir" rev-parse --show-toplevel)"
profile="${1:-v1}"
build_dir="$project_dir/build/$profile"
package_dir="${2:-$project_dir/ci-flash/$profile}"

case "$profile" in
    v1|v3) ;;
    *) echo "unsupported ESP32-P4 profile: $profile" >&2; exit 2 ;;
esac

for required in \
    amy_p4_test.bin \
    amy_p4_test.elf \
    amy_p4_test.map \
    bootloader/bootloader.bin \
    partition_table/partition-table.bin \
    flash_project_args \
    flash_app_args \
    flash_bootloader_args \
    flasher_args.json \
    merged-flash.bin \
    sdkconfig; do
    [[ -f "$build_dir/$required" ]] || {
        echo "build output is missing $required" >&2
        exit 3
    }
done

grep -q '^CONFIG_ESPTOOLPY_FLASHSIZE="32MB"$' "$build_dir/sdkconfig"
grep -q '^CONFIG_SPIRAM=y$' "$build_dir/sdkconfig"
grep -q '^CONFIG_OMNICHORD_P4_MAX_OSCS=336$' "$build_dir/sdkconfig"
grep -q '^CONFIG_OMNICHORD_P4_MAX_BUSES=11$' "$build_dir/sdkconfig"
grep -q '^CONFIG_OMNICHORD_P4_MAX_SEQUENCE_GROUPS=1024$' "$build_dir/sdkconfig"
grep -q '^CONFIG_OMNICHORD_P4_MAX_SEQUENCE_GROUP_TAGS=64$' "$build_dir/sdkconfig"
grep -q '^CONFIG_OMNICHORD_P4_MAX_SEQUENCE_GROUP_EXECUTIONS=40$' "$build_dir/sdkconfig"
grep -q 'gamma9001_pcm_data' "$build_dir/amy_p4_test.map"
grep -q 'amy_set_gamma9001_pcm' "$build_dir/amy_p4_test.map"

if [[ "$profile" == v1 ]]; then
    grep -q '^CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y$' "$build_dir/sdkconfig"
    grep -q '^CONFIG_ESP32P4_REV_MIN_FULL=100$' "$build_dir/sdkconfig"
    grep -q '^CONFIG_ESP32P4_REV_MAX_FULL=199$' "$build_dir/sdkconfig"
    revision_range="1.0-1.99 (observed target hardware: 1.3)"
else
    grep -q '^# CONFIG_ESP32P4_SELECTS_REV_LESS_V3 is not set$' "$build_dir/sdkconfig"
    grep -q '^CONFIG_ESP32P4_REV_MIN_FULL=301$' "$build_dir/sdkconfig"
    grep -q '^CONFIG_ESP32P4_REV_MAX_FULL=399$' "$build_dir/sdkconfig"
    revision_range=">=3.1 (compile-tested only)"
fi

rm -rf "$package_dir"
mkdir -p "$package_dir/bootloader" "$package_dir/partition_table"
cp "$build_dir/amy_p4_test.bin" "$package_dir/"
cp "$build_dir/amy_p4_test.elf" "$package_dir/"
cp "$build_dir/amy_p4_test.map" "$package_dir/"
cp "$build_dir/bootloader/bootloader.bin" "$package_dir/bootloader/"
cp "$build_dir/partition_table/partition-table.bin" "$package_dir/partition_table/"
cp "$build_dir/flash_project_args" "$package_dir/"
cp "$build_dir/flash_app_args" "$package_dir/"
cp "$build_dir/flash_bootloader_args" "$package_dir/"
cp "$build_dir/flasher_args.json" "$package_dir/"
cp "$build_dir/merged-flash.bin" "$package_dir/"
cp "$build_dir/merged-flash.bin" \
    "$package_dir/LB_Omnichord-ESP32P4-${profile}-merged.bin"
if [[ -f "$build_dir/flash_args" ]]; then
    cp "$build_dir/flash_args" "$package_dir/"
fi

source_sha="${GITHUB_SHA:-$(git -C "$repo_root" rev-parse HEAD)}"
amy_branch="$(python3 "$project_dir/../qt_frontend/packaging/release_inputs.py" amy-values --field release_branch)"
amy_commit="$(python3 "$project_dir/../qt_frontend/packaging/release_inputs.py" amy-values --field commit)"
board_label="$(sed -n 's/^CONFIG_OMNICHORD_P4_BOARD_PROFILE="\(.*\)"$/\1/p' "$build_dir/sdkconfig")"

printf '%s\n' \
    "repository=${GITHUB_REPOSITORY:-linuxificator/LB_Omnichord}" \
    "commit=$source_sha" \
    "workflow_run=${GITHUB_RUN_ID:-local}" \
    "esp_idf=v6.0.2" \
    "target=esp32p4" \
    "profile=$profile" \
    "board=$board_label" \
    "supported_silicon=$revision_range" \
    "amy_release_branch=$amy_branch" \
    "amy_commit=$amy_commit" \
    "pcm_bank=gamma9001" \
    "max_oscs=336" \
    "max_buses=11" \
    "max_sequence_groups=1024" \
    > "$package_dir/BUILD_INFO"

(
    cd "$package_dir"
    sha256sum \
        amy_p4_test.bin \
        bootloader/bootloader.bin \
        partition_table/partition-table.bin \
        merged-flash.bin \
        "LB_Omnichord-ESP32P4-${profile}-merged.bin" \
        > SHA256SUMS
    sha256sum --check SHA256SUMS
)

echo "Packaged ESP32-P4 $profile firmware: $package_dir"
