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


def replace_text_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"expected exactly one occurrence for {label}: {old!r}; found {count}"
        )
    return text.replace(old, new, 1)


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

# AMY PR #1119 is now upstream and is required for the short 2x64 DMA ring.
# Do not restore the old target-side vTaskDelay removal; fail loudly if an
# AMY revision predating that upstream fix is requested accidentally.
yield_fix = "if (busy_us >= AMY_BLOCK_US && blocked_us < 150) vTaskDelay(1);"
if yield_fix not in text:
    raise SystemExit(
        "selected AMY revision does not contain the merged short-DMA yield fix "
        "from shorepine/amy#1119"
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

# The Omnichord keeps four AMY buses for role isolation, but room reverb is a
# single shared aux effect. Existing yNh... wire commands retain their format:
# each bus's h-level becomes its send gain; liveness/damping configure the one
# shared room. This keeps bass/strum/chord separate while DRM can gate only the
# drum send, and avoids allocating/running one full reverb per bus.
amy_c = root / "src" / "amy.c"
text = amy_c.read_text(encoding="utf-8")

shared_helpers_anchor = "void config_reverb(uint16_t bus, float level, float liveness, float damping, float xover_hz) {\n"
shared_helpers = r'''#ifdef AMY_SHARED_REVERB
static reverb_params_t *amy_shared_reverb = NULL;
static SAMPLE *amy_shared_reverb_input = NULL;
static SAMPLE *amy_shared_reverb_output = NULL;

static bool alloc_shared_reverb(void) {
    if (amy_shared_reverb != NULL &&
        amy_shared_reverb_input != NULL &&
        amy_shared_reverb_output != NULL) {
        return true;
    }

    const size_t scratch_bytes =
        sizeof(SAMPLE) * AMY_BLOCK_SIZE * AMY_NCHANS;

    SAMPLE *input = (SAMPLE *)malloc_caps(
        scratch_bytes, amy_global.config.ram_caps_synth);
    SAMPLE *output = (SAMPLE *)malloc_caps(
        scratch_bytes, amy_global.config.ram_caps_synth);
    reverb_params_t *rev = (reverb_params_t *)malloc_caps(
        sizeof(reverb_params_t), amy_global.config.ram_caps_synth);

    if (input == NULL || output == NULL || rev == NULL) {
        free(input);
        free(output);
        free(rev);
        amy_oom("unable to alloc shared reverb state/scratch\n");
        return false;
    }

    bzero(rev, sizeof(reverb_params_t));
    if (!init_stereo_reverb(rev)) {
        free(input);
        free(output);
        free(rev);
        return false;
    }

    amy_shared_reverb_input = input;
    amy_shared_reverb_output = output;
    amy_shared_reverb = rev;
    return true;
}

static void dealloc_shared_reverb(void) {
    if (amy_shared_reverb != NULL) {
        deinit_stereo_reverb(amy_shared_reverb);
        free(amy_shared_reverb);
        amy_shared_reverb = NULL;
    }
    free(amy_shared_reverb_input);
    free(amy_shared_reverb_output);
    amy_shared_reverb_input = NULL;
    amy_shared_reverb_output = NULL;
}
#endif

'''
text = replace_text_once(
    text,
    shared_helpers_anchor,
    shared_helpers + shared_helpers_anchor,
    "shared reverb helper insertion",
)

config_anchor = (
    "    if (AMY_IS_UNSET(xover_hz)) xover_hz = amy_global.bus[bus]->reverb.xover_hz;\n"
)
config_shared = r'''    if (AMY_IS_UNSET(xover_hz)) xover_hz = amy_global.bus[bus]->reverb.xover_hz;
#ifdef AMY_SHARED_REVERB
    // In shared mode the per-bus level is an aux-send gain.  The room itself
    // is global, so any h command can update its liveness/damping/crossover.
    if (level < 0) level = 0;
    if (level > 0) {
        if (!alloc_shared_reverb()) {
            amy_global.bus[bus]->reverb.level = 0;
            return;
        }
        config_stereo_reverb(amy_shared_reverb, liveness, xover_hz, damping);
    } else if (amy_shared_reverb != NULL) {
        config_stereo_reverb(amy_shared_reverb, liveness, xover_hz, damping);
    }
    amy_global.bus[bus]->reverb.level = F2S(level);
    amy_global.bus[bus]->reverb.liveness = liveness;
    amy_global.bus[bus]->reverb.damping = damping;
    amy_global.bus[bus]->reverb.xover_hz = xover_hz;
    return;
#endif
'''
text = replace_text_once(
    text,
    config_anchor,
    config_shared,
    "shared reverb config semantics",
)

oscs_deinit_anchor = "void oscs_deinit() {\n"
oscs_deinit_shared = r'''void oscs_deinit() {
#ifdef AMY_SHARED_REVERB
    dealloc_shared_reverb();
#endif
'''
text = replace_text_once(
    text,
    oscs_deinit_anchor,
    oscs_deinit_shared,
    "shared reverb deinit",
)

stock_reverb_block = r'''        if(AMY_HAS_REVERB) {
            // apply per-bus reverb.
            if(amy_global.bus[bus]->reverb.level > 0 && amy_global.bus[bus]->reverb.rev != NULL && amy_global.bus[bus]->reverb.rev->delay_1 != NULL) {
                if(AMY_NCHANS == 1) {
                    stereo_reverb(amy_global.bus[bus]->reverb.rev, fbl[0][bus], NULL, fbl[0][bus], NULL, AMY_BLOCK_SIZE, amy_global.bus[bus]->reverb.level);
                } else {
                    stereo_reverb(amy_global.bus[bus]->reverb.rev, fbl[0][bus], fbl[0][bus] + AMY_BLOCK_SIZE, fbl[0][bus], fbl[0][bus] + AMY_BLOCK_SIZE, AMY_BLOCK_SIZE, amy_global.bus[bus]->reverb.level);
                }
            }
        }
'''
shared_reverb_block = r'''#ifndef AMY_SHARED_REVERB
        if(AMY_HAS_REVERB) {
            // apply per-bus reverb.
            if(amy_global.bus[bus]->reverb.level > 0 && amy_global.bus[bus]->reverb.rev != NULL && amy_global.bus[bus]->reverb.rev->delay_1 != NULL) {
                if(AMY_NCHANS == 1) {
                    stereo_reverb(amy_global.bus[bus]->reverb.rev, fbl[0][bus], NULL, fbl[0][bus], NULL, AMY_BLOCK_SIZE, amy_global.bus[bus]->reverb.level);
                } else {
                    stereo_reverb(amy_global.bus[bus]->reverb.rev, fbl[0][bus], fbl[0][bus] + AMY_BLOCK_SIZE, fbl[0][bus], fbl[0][bus] + AMY_BLOCK_SIZE, AMY_BLOCK_SIZE, amy_global.bus[bus]->reverb.level);
                }
            }
        }
#endif
'''
text = replace_text_once(
    text,
    stock_reverb_block,
    shared_reverb_block,
    "disable stock per-bus reverb in shared mode",
)

volume_anchor = r'''    for (int bus = 0; bus <= amy_global.highest_bus; ++bus)
        volume_scale[bus] = MUL4_SS(F2S(0.1f), F2S(amy_global.volume[bus]));
'''
volume_shared = r'''    for (int bus = 0; bus <= amy_global.highest_bus; ++bus)
        volume_scale[bus] = MUL4_SS(F2S(0.1f), F2S(amy_global.volume[bus]));
#ifdef AMY_SHARED_REVERB
    bool shared_reverb_active =
        AMY_HAS_REVERB &&
        amy_shared_reverb != NULL &&
        amy_shared_reverb_input != NULL &&
        amy_shared_reverb_output != NULL;
    if (shared_reverb_active) {
        const int shared_samples = AMY_BLOCK_SIZE * AMY_NCHANS;
        for (int i = 0; i < shared_samples; ++i)
            amy_shared_reverb_input[i] = 0;

        // Form one post-fader aux input.  reverb.level is the bus send gain;
        // volume_scale keeps the wet contribution tracking each role's volume
        // exactly as the old in-bus reverb did.
        for (int bus = 0; bus <= amy_global.highest_bus; ++bus) {
            SAMPLE send_level = amy_global.bus[bus]->reverb.level;
            if (send_level <= 0) continue;
            SAMPLE send_gain = MUL8_SS(volume_scale[bus], send_level);
            for (int i = 0; i < shared_samples; ++i) {
                amy_shared_reverb_input[i] +=
                    MUL8_SS(send_gain, fbl[0][bus][i]);
            }
        }

        // Run the room exactly once per AMY block.  stereo_reverb() returns
        // dry+wet; the final mixer subtracts the saved aux input so only the
        // wet return is added to the normal dry bus mix.  Processing an all-
        // zero input is intentional so an existing reverb tail can ring out.
        if (AMY_NCHANS == 1) {
            stereo_reverb(
                amy_shared_reverb,
                amy_shared_reverb_input,
                NULL,
                amy_shared_reverb_output,
                NULL,
                AMY_BLOCK_SIZE,
                F2S(1.0f));
        } else {
            stereo_reverb(
                amy_shared_reverb,
                amy_shared_reverb_input,
                amy_shared_reverb_input + AMY_BLOCK_SIZE,
                amy_shared_reverb_output,
                amy_shared_reverb_output + AMY_BLOCK_SIZE,
                AMY_BLOCK_SIZE,
                F2S(1.0f));
        }
    }
#endif
'''
text = replace_text_once(
    text,
    volume_anchor,
    volume_shared,
    "shared reverb aux mix",
)

final_mix_anchor = r'''            for (int bus = 0; bus <= amy_global.highest_bus; ++bus) {
                // Convert the mixed sample into the int16 range, applying overall gain.
                fsample += MUL8_SS(volume_scale[bus], fbl[0][bus][i + c * AMY_BLOCK_SIZE]);
            }
'''
final_mix_shared = r'''            for (int bus = 0; bus <= amy_global.highest_bus; ++bus) {
                // Convert the mixed sample into the int16 range, applying overall gain.
                fsample += MUL8_SS(volume_scale[bus], fbl[0][bus][i + c * AMY_BLOCK_SIZE]);
            }
#ifdef AMY_SHARED_REVERB
            if (shared_reverb_active) {
                const int shared_index = i + c * AMY_BLOCK_SIZE;
                fsample += amy_shared_reverb_output[shared_index]
                    - amy_shared_reverb_input[shared_index];
            }
#endif
'''
text = replace_text_once(
    text,
    final_mix_anchor,
    final_mix_shared,
    "shared reverb wet return",
)

amy_c.write_text(text, encoding="utf-8")
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

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    AMY_SHARED_REVERB=1
)

target_compile_options(${COMPONENT_LIB} PRIVATE
    -Wno-strict-aliasing
    -Wno-unused-parameter
)
CMAKE

echo "Prepared AMY component: $(git -C "$COMPONENT_DIR" rev-parse HEAD)"
