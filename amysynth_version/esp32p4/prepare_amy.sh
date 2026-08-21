#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPONENT_DIR="$PROJECT_DIR/components/amy"
AMY_REPO="${AMY_REPO:-https://github.com/shorepine/amy.git}"
AMY_REF="${AMY_REF:-main}"

rm -rf "$COMPONENT_DIR"
mkdir -p "$(dirname "$COMPONENT_DIR")"

echo "Fetching AMY from $AMY_REPO ($AMY_REF)"
if [[ "$AMY_REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
    git clone --filter=blob:none --no-checkout "$AMY_REPO" "$COMPONENT_DIR"
    git -C "$COMPONENT_DIR" fetch --depth 1 origin "$AMY_REF"
    git -C "$COMPONENT_DIR" checkout --detach FETCH_HEAD
else
    git clone --depth 1 --branch "$AMY_REF" "$AMY_REPO" "$COMPONENT_DIR"
fi

python3 - "$COMPONENT_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"expected exactly one occurrence in {path}: {old!r}; found {count}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# The P4 target is intentionally 48 kHz with a 128-sample render block.
amy_h = root / "src" / "amy.h"
replace_once(amy_h, "#define AMY_BLOCK_SIZE 256", "#define AMY_BLOCK_SIZE 128")
replace_once(amy_h, "#define BLOCK_SIZE_BITS 8 // log2 of BLOCK_SIZE", "#define BLOCK_SIZE_BITS 7 // log2 of BLOCK_SIZE")
replace_once(amy_h, "#define AMY_SAMPLE_RATE 44100 ", "#define AMY_SAMPLE_RATE 48000 ")

# PCM5102A uses Philips I2S timing. Keep the DMA queue deliberately short;
# 2 x 64 frames matches the 128-sample AMY block used by this firmware.
i2s = root / "src" / "i2s.c"
text = i2s.read_text(encoding="utf-8")
text = text.replace(
    "I2S_STD_MSB_SLOT_DEFAULT_CONFIG",
    "I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG",
)
needle = "    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);\n"
if text.count(needle) != 1:
    raise SystemExit(f"generic ESP I2S channel anchor changed; found {text.count(needle)}")
text = text.replace(
    needle,
    needle
    + "    chan_cfg.dma_desc_num = 2;\n"
    + "    chan_cfg.dma_frame_num = AMY_BLOCK_SIZE / 2;\n",
    1,
)
replace_old = "void esp_fill_audio_buffer_task() {"
if replace_old in text:
    text = text.replace(
        replace_old,
        "void esp_fill_audio_buffer_task(void *pvParameters) {\n    (void)pvParameters;",
        1,
    )
i2s.write_text(text, encoding="utf-8")

midi = root / "src" / "amy_midi.c"
text = midi.read_text(encoding="utf-8")
replace_old = "void run_midi_task() {"
if replace_old in text:
    text = text.replace(
        replace_old,
        "void run_midi_task(void *pvParameters) {\n    (void)pvParameters;",
        1,
    )
midi.write_text(text, encoding="utf-8")
PY

cat > "$COMPONENT_DIR/CMakeLists.txt" <<'CMAKE'
idf_component_register(
    SRCS
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
    INCLUDE_DIRS
        "src"
    REQUIRES
        esp_driver_i2s
        esp_driver_uart
        esp_timer
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -Wno-strict-aliasing
    -Wno-unused-parameter
)
CMAKE

echo "Prepared AMY component: $(git -C "$COMPONENT_DIR" rev-parse HEAD)"
