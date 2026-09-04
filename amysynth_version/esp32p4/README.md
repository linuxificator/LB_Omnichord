# ESP32-P4 AMY firmware

This standalone ESP-IDF project builds the AMY service used by LB Omnichord on
a Waveshare ESP32-P4 Pico M. The high-performance cores synthesize stereo audio
and the low-power core receives newline-framed native AMY wire commands from a
Raspberry Pi at 1 Mbaud. The frontend and synth remain fully separated: the
firmware has no Omnichord UI or musical-policy API.

The image includes:

- the pinned Omnichord AMY release with sequencer groups;
- the complete Gamma9001 PCM bank;
- 336 oscillators and 16 Karplus-Strong buffers;
- 11 independent AMY buses;
- 1024 stored sequence groups, 64 local event tags per group and 40 concurrent
  executions;
- a 48 kHz, 64-sample AMY render block and 2 x 32-frame I2S DMA ring.

Large persistent AMY pools use PSRAM. Render/DMA scratch remains in internal
RAM. Startup aborts clearly when less than 8 MB PSRAM is available.

## Hardware defaults

The defaults preserve the previously proven wiring:

| Function | ESP32-P4 pin | Other side |
| --- | ---: | --- |
| I2S LRCK / WS | GPIO16 | PCM5102A LRCK/LCK |
| I2S data out | GPIO17 | PCM5102A DIN |
| I2S bit clock | GPIO18 | PCM5102A BCK |
| LP UART receive | GPIO15 | Raspberry Pi GPIO14/TXD, physical pin 8 |
| Ground | GND | common ground |

Tie PCM5102A SCK to ground. No MCLK is used. The UART format is 1,000,000 baud,
8 data bits, no parity and one stop bit at 3.3 V. Each AMY request ends in `Z`;
the serial transport appends LF, for example `v0w0f440Q0l0.2Z\n`.

These are build defaults, not application constants. `main/Kconfig.projbuild`
owns the firmware settings and `build_firmware.sh` accepts these environment
overrides:

```text
ESP32P4_I2S_LRCK_GPIO
ESP32P4_I2S_DOUT_GPIO
ESP32P4_I2S_BCLK_GPIO
ESP32P4_UART_RX_GPIO
ESP32P4_UART_BAUD
ESP32P4_BOARD_LABEL
```

For example:

```bash
ESP32P4_I2S_LRCK_GPIO=20 \
ESP32P4_I2S_DOUT_GPIO=21 \
ESP32P4_I2S_BCLK_GPIO=22 \
ESP32P4_UART_RX_GPIO=23 \
ESP32P4_BOARD_LABEL=my-p4-carrier \
./build_firmware.sh --profile v1
```

## Silicon profiles

ESP-IDF treats ESP32-P4 revisions before v3.0 and revisions v3.0 or later as
binary-incompatible. One image cannot support both families.

- `v1` supports revisions 1.0 through 1.99. The connected board reported chip
  revision 1.3, so this is the default target. Its wiring and low-latency audio
  geometry were proven by the earlier firmware; this new complete image still
  requires the acceptance run below.
- `v3` targets revision 3.1 and later. It compiles in local and CI builds, but
  remains hardware-unverified until the newer board is tested.

Always select the profile from the chip revision, not from a marketing board
revision printed on a carrier PCB.

## Exact dependencies

The build uses ESP-IDF 6.0.2. `prepare_amy.sh` reads the repository, immutable
commit and immutable release branch from
`../qt_frontend/packaging/release_inputs.json`, verifies that the branch tip is
the requested commit, generates Gamma9001 from its source dataset and creates
the ignored ESP-IDF AMY component. It does not patch AMY source files.

For local AMY development, all three values may be overridden together:

```bash
AMY_REPO=/path/to/amy \
AMY_RELEASE_BRANCH=rework/esp32p4 \
AMY_REF=<40-character-commit> \
./build_firmware.sh --profile v1
```

## Local build

Install and activate ESP-IDF 6.0.2, then run from this directory:

```bash
. "$HOME/esp/esp-idf/export.sh"
./build_firmware.sh --profile v1
```

Use `--profile v3` for newer silicon. Each profile has an independent,
incremental build directory:

```text
build/v1/merged-flash.bin
build/v3/merged-flash.bin
```

`--skip-prepare` reuses an already prepared AMY component while iterating on
firmware code. A normal reproducible build prepares AMY again.

Build parameters are written only to the selected build directory; tracked
profile defaults remain unchanged. The generated 32 MB flash image contains an
8 MB factory application partition, which leaves roughly 42% headroom after
linking Gamma9001 with the current build.

## Standalone CI build

The `ESP32-P4 firmware build` workflow is independent of the full application
release. Run it manually with profile `v1`, `v3`, or `all`. Pull requests that
touch the firmware build both ABIs. Each successful job publishes a portable
artifact named `esp32p4-firmware-v1` or `esp32p4-firmware-v3` containing:

- a directly flashable merged image;
- application, bootloader and partition-table images;
- portable esptool argument files;
- ELF and map files for diagnosis;
- SHA-256 checksums and exact source/AMY/profile metadata.

The full Omnichord release calls the same workflow for the `v1` profile that
matches the observed revision-1.3 board and publishes its firmware zip,
checksum and build-provenance
attestation beside the five application packages.

## Flash

For a local build:

```bash
idf.py -B build/v1 -p /dev/ttyACM0 flash monitor
```

For the exact CI artifact matching the checked-out commit:

```bash
ESP32P4_PROFILE=v1 ./flash_ci.sh /dev/ttyACM0
```

See [CI_FLASH.md](CI_FLASH.md) for manual artifact flashing.

## Verification boundary

CI compiles both incompatible silicon profiles and verifies the flash size,
partition fit, Gamma9001 symbols, AMY release pin, capacities, checksums and
portable flash metadata. AMY's host tests separately cover the wire protocol,
legacy sequencer compatibility and sequence-group behavior.

There is no useful full-system emulator test for this image today. Espressif's
P4 emulator does not model the LP core, while this firmware deliberately uses
that core for UART reception; I2S output is also a physical integration
boundary. Adding a special emulator-only firmware path would stop testing the
production topology. A physical v1.3 acceptance run must therefore confirm:

1. PSRAM initialization and the printed board/chip profile;
2. clean 48 kHz I2S output with the 64-sample / 2 x 32 profile;
3. sustained 1 Mbaud LP-UART command reception without ring overflow;
4. distinct Gamma9001 kick, snare, tom and cymbal presets;
5. independent routing across all 11 buses;
6. preloading the full rhythm catalogue within 1024 groups;
7. starting, replacing, gating and stopping sequence-group executions;
8. no audio underruns or overload reset under realistic maximum rhythm load.

Do not describe the v3 profile as hardware-supported until the same test has
been completed on the newer board.
