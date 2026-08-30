# ESP32-P4 AMY firmware

This directory is a standalone ESP-IDF project for the AMY-based LB Omnichord target running on the Waveshare ESP32-P4 Pico M.

The project builds AMY for the ESP32-P4, outputs stereo I2S to an external PCM5102A DAC, and receives native AMY wire-protocol messages on the ESP32-P4 low-power UART. The LP core receives the UART bytes and forwards complete AMY messages to the high-performance cores through the LP mailbox.

The repository intentionally does **not** vendor ESP-IDF, AMY, or build output.
`prepare_amy.sh` fetches the exact pinned AMY fork release and applies the small
target-specific changes required by this firmware. The same script is used
locally and by GitHub Actions.

## Hardware

### ESP32-P4 board

Current target: Waveshare ESP32-P4 Pico M.

### PCM5102A

The known-good wiring is:

| ESP32-P4 | PCM5102A |
| --- | --- |
| GPIO16 | LRCK / LCK |
| GPIO17 | DIN |
| GPIO18 | BCK |
| GND | GND |
| — | SCK tied to GND |

AMY is configured for stereo I2S output. The PCM5102A does not require MCLK in this setup.

### AMY command UART

The Qt frontend sends native AMY wire protocol over a one-way UART connection:

| Raspberry Pi | ESP32-P4 |
| --- | --- |
| GPIO14 / TXD, physical pin 8 | GPIO15 / LP-UART RX |
| GND | GND |

Serial format:

```text
1,000,000 baud
8 data bits
no parity
1 stop bit
3.3 V logic
```

Each native AMY command ends in `Z`; the transport adds LF after the AMY message. Example:

```text
v0w0f440Q0l0.2Z\n
```

## Repository layout

```text
esp32p4/
├── CMakeLists.txt
├── README.md
├── sdkconfig
├── prepare_amy.sh
├── main/
│   ├── CMakeLists.txt
│   ├── main.c
│   └── lp_core/
│       ├── main.c
│       └── amy_uart_shared.h
└── components/
    └── amy/              generated, ignored by git
```

`build/` and `components/amy/` are intentionally ignored.

## Versions

The checked-in project configuration was generated with ESP-IDF **6.0.2**. The CI build is pinned to the official Espressif `v6.0.2` environment.

AMY is pinned to our immutable Omnichord fork release
`releases/amy_omnichord_R20260830T220021` at commit
`32f3a68861a68979ceb715cf32e0322e8614365b`. That release contains the nested
sequencer API used by this firmware. `prepare_amy.sh` verifies that the branch
tip and requested commit match, so it cannot silently compile against
incompatible Shorepine `main`.

The short-DMA scheduling fix from upstream AMY PR #1119 is required by this target. `prepare_amy.sh` checks that the selected AMY revision contains that merged fix; it does **not** carry the older local workaround that removed `vTaskDelay()`.

## Ubuntu: install ESP-IDF 6.0.2

The following is the normal native development setup.

Install the Ubuntu packages required by ESP-IDF:

```bash
sudo apt update
sudo apt install -y \
    git wget flex bison gperf \
    python3 python3-pip python3-venv \
    cmake ninja-build ccache \
    libffi-dev libssl-dev \
    dfu-util libusb-1.0-0
```

Install ESP-IDF 6.0.2 under `~/esp`:

```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive --branch v6.0.2 \
    https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32p4
```

Load the IDF environment in each shell before using `idf.py`:

```bash
. "$HOME/esp/esp-idf/export.sh"
```

An optional shell alias is convenient:

```bash
echo "alias get_idf='. \$HOME/esp/esp-idf/export.sh'" >> ~/.bashrc
. ~/.bashrc
```

Then a new terminal can simply use:

```bash
get_idf
```

Check the installation:

```bash
idf.py --version
```

It should report ESP-IDF 6.0.2.

## Clone and prepare the firmware

Clone this repository and enter the firmware project:

```bash
git clone https://github.com/linuxificator/LB_Omnichord.git
cd LB_Omnichord/amysynth_version/esp32p4
```

Fetch and patch AMY:

```bash
bash prepare_amy.sh
```

The script:

1. removes any previously generated `components/amy/` tree;
2. clones and verifies the pinned Omnichord AMY fork release;
3. changes AMY to a 128-sample block at 48 kHz;
4. selects Philips I2S framing for the PCM5102A;
5. uses two DMA descriptors with 64 frames each;
6. verifies that the selected AMY contains the merged #1119 short-DMA scheduling fix;
7. fixes FreeRTOS task entry-point signatures when required by the selected upstream revision;
8. enables the P4-only shared-aux-reverb implementation;
9. writes the ESP-IDF component `CMakeLists.txt` used by this project;
10. prints the exact AMY commit that was prepared.

To deliberately test another release, override the repository, release branch
and exact commit together:

```bash
AMY_REPO=<amy-fork-url> \
AMY_RELEASE_BRANCH=<release-branch> \
AMY_REF=<40-character-commit-sha> \
bash prepare_amy.sh
```

A deliberately old commit from before AMY PR #1119 will be rejected because its render-task scheduling is not compatible with the short 2×64 DMA ring used here.

## Build

Load ESP-IDF if necessary:

```bash
get_idf
```

Then, from `amysynth_version/esp32p4`:

```bash
idf.py build
```

The generated files are placed under `build/` and are ignored by git.

For a completely clean rebuild:

```bash
idf.py fullclean
bash prepare_amy.sh
idf.py build
```

Do **not** run `idf.py set-target` as part of the normal build procedure. The checked-in `sdkconfig` is the project configuration and should remain authoritative unless the target configuration is deliberately being changed.

## Flash and monitor

Connect the ESP32-P4 board over USB and make sure your user can access the serial device.

On Ubuntu, add your account to `dialout` if necessary:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership.

With the IDF environment loaded:

```bash
idf.py flash monitor
```

If several serial ports exist, specify the port explicitly, for example:

```bash
idf.py -p /dev/ttyACM0 flash monitor
```

Exit the IDF monitor with `Ctrl-]`.

Expected startup output includes the AMY sample rate/block size, AMY startup, LP UART initialization, and the final message that GPIO15 is ready for native AMY commands.

## Build with Docker instead of installing ESP-IDF

Espressif publishes an official IDF Docker image. This is useful for a clean build or on a machine where ESP-IDF is not installed natively.

From this directory:

```bash
bash prepare_amy.sh

docker run --rm \
    -v "$PWD:/project" \
    -w /project \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    espressif/idf:v6.0.2 \
    idf.py build
```

The Docker image is large, but it contains the complete Espressif toolchain and IDF environment. Build output is written into the local ignored `build/` directory.

## GitHub Actions build

`.github/workflows/esp32p4-build.yml` performs the same firmware build automatically when ESP32-P4 project files change.

It uses Espressif's official `esp-idf-ci-action@v1`, pinned to ESP-IDF `v6.0.2` and target `esp32p4`. The action runs the build inside the official Espressif IDF container.

The CI command is intentionally the same sequence as a local build:

```bash
bash prepare_amy.sh
idf.py build
```

Successful CI runs upload the generated firmware `.bin`, `.elf`, `.map`, bootloader, partition table and flash arguments as a short-lived GitHub Actions artifact.

The workflow has concurrency cancellation enabled, so a newer commit to the same PR cancels an obsolete in-progress firmware build instead of producing another full set of redundant jobs/notifications.

## Current AMY target modifications

The firmware deliberately differs from the pinned Omnichord AMY release only
in target-specific areas. `prepare_amy.sh` applies these changes after checking
out that exact release commit.

### 48 kHz, 128-sample blocks

Stock AMY normally builds with 256-sample blocks at 44.1 kHz on this path. This target uses:

```text
AMY_SAMPLE_RATE = 48000
AMY_BLOCK_SIZE  = 128
BLOCK_SIZE_BITS = 7
```

This 128-sample block size is intentional: it is the best performance/latency operating point established by the ESP32-P4 tests for this project.

### I2S and DMA

The external PCM5102A uses Philips I2S framing. The firmware uses:

```text
GPIO16 = LRCK
GPIO17 = DOUT
GPIO18 = BCLK
no MCLK
```

The DMA configuration is explicitly:

```text
dma_desc_num  = 2
dma_frame_num = AMY_BLOCK_SIZE / 2 = 64
```

Current upstream AMY contains the merged #1119 fix that only yields the max-priority audio task when rendering really exceeds the block budget and I2S did not block. That upstream logic is retained unchanged.

### Shared aux reverb

This section records the proven four-bus OMNI-only ESP32-P4 baseline. The full
Qt OMNI+MIDI design now requires eleven buses and independent OMNI/MIDI reverb
state as specified in `../design/architecture.md`. In particular, this
single-shared-room build cannot independently retain both sections' liveness
and damping; target-side multibus/effect work and hardware validation are still
required before claiming feature parity with the Linux service.

The Omnichord keeps four separate dry AMY buses for role isolation:

```text
bus 0 = drums
bus 1 = bass
bus 2 = strum
bus 3 = chords
```

EQ, chorus, echo, bus volume, and patch isolation therefore remain per bus. Reverb is different: the P4 target compiles AMY with `AMY_SHARED_REVERB=1` and uses **one** stereo room reverb as an aux effect for all four buses.

The native AMY wire syntax is unchanged:

```text
yNh<level>,<liveness>,<damping>Z
```

On this P4 build:

- `N` still selects the source bus;
- `level` is that bus's send gain into the shared room;
- `liveness` and `damping` configure the single shared room;
- the Qt frontend sends the user reverb level to bass, strum, and chord buses;
- the drum send is zero when DRM is off and follows the same user level when DRM is on.

The audio path is:

```text
bus EQ/chorus/echo
        |
        +-------------------------------> dry final mix
        |
        +-- post-fader reverb send --\
        +-- post-fader reverb send ---+--> one stereo reverb --> wet return
        +-- post-fader reverb send ---+
        +-- DRM-gated drum send ------/
```

The send is formed after each bus's volume scaling, so lowering a role volume also lowers the amount of that role entering the room. AMY runs the reverb engine exactly once per 128-sample block and adds only its wet return to the normal dry mix. Reverb tails continue to run when the current input block is silent.

This removes the previous failure mode where enabling reverb on several buses attempted to allocate several complete reverb delay networks. One AMY stereo reverb contains 27,648 delay samples (about 111 kB of sample storage when `SAMPLE` is 32-bit), plus small state/scratch allocations; four independent instances would require roughly four times the delay storage and four reverb DSP passes per audio block.

### LP-core UART

The low-power core receives the 1 Mbaud serial stream on GPIO15. Complete messages are placed into a shared ring and signalled to the HP side through the ESP32-P4 LP mailbox. A high-priority HP FreeRTOS task then calls `amy_add_message()`.

The UART forwarding task runs one priority below AMY's render task, so audio rendering can preempt command forwarding.

## Delay memory / PSRAM note

AMY exposes a separate `ram_caps_delay` allocator for echo and reverb delay lines. The checked-in `sdkconfig` currently has ESP PSRAM disabled, so the generic ESP-IDF AMY defaults allocate these delay lines from normal/default-capability RAM.

The shared-reverb design means room reverb no longer needs one large allocation per musical bus. This should make the current internal-RAM configuration practical for the room effect while preserving the four-bus architecture.

PSRAM can still be enabled later and selected for large delay/effect storage if measurements show that echo, chorus, future effects, or sample caching need more memory. Render-critical AMY state can remain in internal RAM while bulk delay/sample storage uses PSRAM.

## Cleaning generated files

Normal cleanup:

```bash
idf.py fullclean
rm -rf components/amy
```

The following are generated and must not be committed:

```text
build/
components/amy/
managed_components/
sdkconfig.old*
compile_commands.json
*.elf
*.map
*.bin
```

The project-local `.gitignore` enforces these rules.

## Updating AMY

To regenerate the component from the pinned release:

```bash
bash prepare_amy.sh
idf.py build
```

When adopting a newer fork release, update the repository, branch and commit
pin together. If that AMY revision changes one of the source locations patched
for the P4 target, `prepare_amy.sh` deliberately fails instead of silently
producing a differently configured firmware. Update the preparation script and
CI together when that happens.
