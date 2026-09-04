#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
component_dir="$project_dir/components/amy"
release_inputs="$project_dir/../qt_frontend/packaging/release_inputs.py"

amy_repo="${AMY_REPO:-$(python3 "$release_inputs" amy-values --field repository)}"
amy_branch="${AMY_RELEASE_BRANCH:-$(python3 "$release_inputs" amy-values --field release_branch)}"
amy_ref="${AMY_REF:-$(python3 "$release_inputs" amy-values --field commit)}"

if [[ ! "$amy_ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "AMY_REF must be an immutable 40-character commit SHA" >&2
    exit 1
fi

rm -rf "$component_dir"
mkdir -p "$(dirname "$component_dir")"

echo "Fetching AMY from $amy_repo ($amy_ref)"
git clone --filter=blob:none --no-checkout "$amy_repo" "$component_dir"
git -C "$component_dir" fetch --depth 1 origin "$amy_ref"
git -C "$component_dir" checkout --detach FETCH_HEAD
git -C "$component_dir" fetch --depth 1 origin \
    "refs/heads/$amy_branch:refs/remotes/origin/$amy_branch"

checked_out="$(git -C "$component_dir" rev-parse HEAD)"
branch_tip="$(git -C "$component_dir" rev-parse "origin/$amy_branch")"
if [[ "$checked_out" != "$amy_ref" || "$branch_tip" != "$amy_ref" ]]; then
    echo "AMY release branch and immutable commit do not match" >&2
    exit 1
fi

# Generate Gamma9001 inside the ignored component checkout. This keeps the
# source dataset authoritative and avoids committing a multi-megabyte C file.
(
    cd "$component_dir"
    python3 -m amy.headers gamma9001-blob-c drums_bin.c
)

cat > "$component_dir/CMakeLists.txt" <<'CMAKE'
idf_component_register(
    SRCS
        "drums_bin.c"
        "src/algorithms.c"
        "src/amy.c"
        "src/api.c"
        "src/custom.c"
        "src/cv_trigger.c"
        "src/delay.c"
        "src/envelope.c"
        "src/examples.c"
        "src/filters.c"
        "src/instrument.c"
        "src/interp_partials.c"
        "src/i2s.c"
        "src/log2_exp2.c"
        "src/midi_mappings.c"
        "src/amy_midi.c"
        "src/oscillators.c"
        "src/parse.c"
        "src/patches.c"
        "src/pcm.c"
        "src/sequencer.c"
        "src/transfer.c"
    INCLUDE_DIRS "src"
    REQUIRES esp_driver_i2s esp_driver_uart esp_timer
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    AMY_BLOCK_SIZE=64
    AMY_SAMPLE_RATE=48000
    AMY_ESP_I2S_PHILIPS_FORMAT=1
    AMY_ESP_I2S_DMA_DESC_NUM=2
    AMY_ESP_I2S_DMA_FRAME_NUM=32
    AMY_WAVETABLE=1
    GAMMA9001=1
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -O3
    -Wno-strict-aliasing
    -Wno-unused-parameter
    -Wno-float-conversion
)
CMAKE

echo "Prepared AMY component: $checked_out"
