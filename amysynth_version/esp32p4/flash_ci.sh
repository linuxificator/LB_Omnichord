#!/usr/bin/env bash
set -euo pipefail

REPO="linuxificator/LB_Omnichord"
WORKFLOW="esp32p4-build.yml"
PROFILE="${ESP32P4_PROFILE:-v1}"
ARTIFACT="esp32p4-firmware-$PROFILE"
PORT="${1:-${ESPPORT:-/dev/ttyACM0}}"
BAUD="${2:-${ESPBAUD:-}}"

if ! command -v git >/dev/null 2>&1; then
    echo "error: git is required" >&2
    exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "error: GitHub CLI (gh) is required to download the CI artifact" >&2
    echo "Ubuntu: sudo apt install gh" >&2
    echo "Then authenticate once with: gh auth login" >&2
    exit 2
fi

if ! command -v idf.py >/dev/null 2>&1; then
    echo "error: ESP-IDF is not loaded in this shell" >&2
    echo 'Run: . "$HOME/esp/esp-idf/export.sh"' >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$project_dir" rev-parse --show-toplevel)"
head_sha="$(git -C "$repo_root" rev-parse HEAD)"

if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=no)" ]]; then
    echo "warning: tracked files have local modifications; CI firmware is for committed HEAD $head_sha" >&2
fi

echo "Looking for successful ESP32-P4 CI build of $head_sha ..."
run_id="$(
    gh run list \
        --repo "$REPO" \
        --workflow "$WORKFLOW" \
        --commit "$head_sha" \
        --status success \
        --limit 20 \
        --json databaseId,headSha \
        --jq '.[0].databaseId // empty'
)"

if [[ -z "$run_id" ]]; then
    echo "error: no successful $WORKFLOW run exists for commit $head_sha" >&2
    echo "Check the branch's GitHub Actions run and try again after it succeeds." >&2
    exit 3
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

echo "Downloading artifact '$ARTIFACT' from workflow run $run_id ..."
gh run download "$run_id" \
    --repo "$REPO" \
    --name "$ARTIFACT" \
    --dir "$tmpdir"

build_info="$(find "$tmpdir" -type f -name BUILD_INFO -print -quit)"
if [[ -z "$build_info" ]]; then
    echo "error: artifact does not contain BUILD_INFO" >&2
    exit 4
fi

package_dir="$(dirname "$build_info")"
artifact_sha="$(sed -n 's/^commit=//p' "$build_info" | head -n 1)"
artifact_profile="$(sed -n 's/^profile=//p' "$build_info" | head -n 1)"

if [[ "$artifact_sha" != "$head_sha" ]]; then
    echo "error: artifact commit $artifact_sha does not match checked-out commit $head_sha" >&2
    exit 4
fi

if [[ "$artifact_profile" != "$PROFILE" ]]; then
    echo "error: artifact profile $artifact_profile does not match requested profile $PROFILE" >&2
    exit 4
fi

for required in \
    flash_project_args \
    flasher_args.json \
    amy_p4_test.bin \
    bootloader/bootloader.bin \
    partition_table/partition-table.bin; do
    if [[ ! -f "$package_dir/$required" ]]; then
        echo "error: artifact is missing $required" >&2
        exit 4
    fi
done

idf_version="$(idf.py --version 2>/dev/null || true)"
echo "Local:    ${idf_version:-unknown ESP-IDF version}"
echo "Artifact: $(tr '\n' ' ' < "$build_info")"
echo "Port:     $PORT"

esptool_args=(--chip esp32p4 --port "$PORT")
if [[ -n "$BAUD" ]]; then
    esptool_args+=(--baud "$BAUD")
fi

cd "$package_dir"
python -m esptool "${esptool_args[@]}" write-flash @flash_project_args

echo "Flashed CI firmware for commit $head_sha"
