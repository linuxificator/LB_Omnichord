# ESP32-P4 complete firmware handover

Status: implemented and build-verified; physical acceptance remains open
Owner: ESP32-P4 firmware and release integration
Last verified: 2026-09-04

## Goal and result

LB Omnichord now owns a reproducible ESP32-P4 firmware build rather than a
manually patched local AMY experiment. The image remains a separate synth
component: the Qt application sends ordinary, LF-framed AMY wire requests over
serial and contains no target-side synthesis implementation.

The firmware contains the same capabilities used by the application packages:

- Gamma9001 PCM data;
- sequencer groups and immutable active executions;
- 336 oscillators and 16 Karplus-Strong buffers;
- 11 independent buses;
- 1024 stored groups, 64 local event tags per group and 40 concurrent group
  executions;
- 48 kHz rendering in 128-sample blocks with a 2 x 64-frame I2S DMA ring.

The old four-bus/Tiny image and source-patching preparation flow are superseded.
They remain history, not an alternate product profile.

## Branch and immutable AMY input

The implementation branches are both named `rework/esp32p4`:

- `linuxificator/LB_Omnichord` contains the firmware project, workflows and
  product documentation;
- `linuxificator/amy` contains only generic embedded configuration support.

The AMY work adds compile-time overrides for render-block/sample-rate geometry
and ESP-IDF I2S DMA geometry while leaving all upstream defaults unchanged. It
also corrects ESP-IDF task entry signatures to their actual `void (*)(void *)`
contract. No Omnichord terminology, board pins, Gamma policy, bus count or
sequence capacity is embedded in AMY.

The immutable integration release is:

```text
repository:     https://github.com/linuxificator/amy.git
release branch: releases/amy_omnichord_R20260904T130059
commit:         7d66ae637f75a53d45cc5ffb3392c07f1d6ff876
PCM bank:       gamma9001
```

`qt_frontend/packaging/release_inputs.json` is the machine authority. The P4
preparation script reads it through `release_inputs.py`, checks out the exact
commit, proves that the declared release branch points at it, generates the
Gamma9001 C blob and constructs an ignored ESP-IDF component without modifying
the checked-out AMY source.

## Hardware and build configuration

The defaults preserve the working carrier wiring:

| Function | Default |
| --- | ---: |
| I2S LRCK / WS | GPIO16 |
| I2S data out | GPIO17 |
| I2S bit clock | GPIO18 |
| LP UART receive | GPIO15 |
| LP UART | 1,000,000 baud, 8N1 |

The PCM5102A uses no MCLK; SCK is tied to ground. Pins, baud and the diagnostic
board label are Kconfig values and can be overridden through the documented
`ESP32P4_*` build environment variables. They are never frontend constants.

ESP-IDF 6.0.2 treats silicon before v3.0 and silicon v3.0-or-later as
incompatible ABIs. `build_firmware.sh --profile v1` supports 1.0 through 1.99
and matches the connected chip that reported v1.3. `--profile v3` targets v3.1
or later. Each has its own build directory and artifact; never use one binary
for both. The v3 profile is compile-tested only.

Gamma9001 makes the application image roughly 4.8 MB. The firmware therefore
uses 32 MB flash, an 8 MB factory application partition and requires at least
8 MB initialized PSRAM. Large persistent AMY pools allocate from PSRAM, while
render and DMA scratch follow AMY/ESP-IDF's realtime allocation paths. This
profile must not be used as a reason to change hosted packages back to Tiny.

## Build and release paths

Local, profile-isolated builds use:

```bash
./build_firmware.sh --profile v1
./build_firmware.sh --profile v3
```

The independently dispatchable `ESP32-P4 firmware build` workflow accepts
`v1`, `v3` or `all`; firmware pull requests compile both ABIs. It packages a
merged image at offset zero, the component images and portable esptool argument
files, ELF/map diagnostics, exact build metadata and SHA-256 checksums.

The complete application release reuses that workflow for v1. It publishes the
P4 zip and checksum beside, but not as one of, the five hosted application
packages. Application SBOM/provenance rules remain unchanged; the firmware has
its own signed build-provenance attestation. This separation avoids pretending
that MCU firmware is a Python/Qt application package while still making it an
ordinary release deliverable.

## Tests and evidence

The AMY branch passes its C suite and C-API compatibility check. Dedicated AMY
tests prove that default geometry is unchanged and that supported embedded
block overrides remain internally consistent.

The LB static firmware suite checks the immutable Gamma release, frontend/P4
capacity agreement, retired pattern vocabulary, generated Gamma symbols,
PSRAM/partition sizing, configurable pins, separate silicon profiles,
standalone/reusable workflow and full-release publication path.

Both profiles have built locally with ESP-IDF 6.0.2 using the most recently
physically tested 128-sample / 2 x 64-frame audio geometry. Each image fits its 8 MB partition with
about 42 percent free space, contains the Gamma registration/data symbols and
packages successfully.

## Emulator boundary

No emulator currently supplies meaningful end-to-end proof for this topology.
Espressif's maintained QEMU support does not list ESP32-P4. The newer
`esp-emulator` project can model some P4 execution but explicitly does not model
the LP core, which is the production UART receiver here. It also cannot prove
physical PCM5102A I2S timing or audio quality. An emulator-only input path would
test different firmware and is deliberately not added.

References:

- https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-guides/host-apps.html
- https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/README.md
- https://github.com/espressif/esp-emulator/blob/main/README.md

## Remaining physical acceptance

Before describing the new image as hardware-validated, flash v1 on the observed
revision-1.3 board and verify the checklist in `../esp32p4/README.md`: startup
and PSRAM, I2S audio, sustained LP UART at 1 Mbaud, distinct Gamma percussion,
all buses, complete group preload, group execution/gating and worst-case
underrun behavior. Repeat it separately for the newer board with the v3 image.

Do not hide a physical failure with an untested render geometry or task delay.
The 128-sample geometry and AMY's conditional upstream short-DMA scheduling
fix are the current performance contract; the older 64-sample documentation
was stale. Any proposed change requires new latency and distortion evidence.
