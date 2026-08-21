# ESP32-P4 AMY firmware

This directory is a standalone ESP-IDF project for the AMY-based LB Omnichord target running on the Waveshare ESP32-P4 Pico M.

The project builds AMY for the ESP32-P4, outputs stereo I2S to an external PCM5102A DAC, and receives native AMY wire-protocol messages on the ESP32-P4 low-power UART. The LP core receives the UART bytes and forwards complete AMY messages to the high-performance cores through the LP mailbox.

The repository intentionally does **not** vendor ESP-IDF, AMY, or build output. `prepare_amy.sh` fetches current upstream AMY and applies the small target-specific changes required by this firmware. The same script is used locally and by GitHub Actions.

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

AMY follows current upstream `shorepine/amy` `main` by default. To build against a specific AMY commit, set `AMY_REF` before running `prepare_amy.sh`.

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
2. clones current upstream AMY;
3. changes AMY to a 128-sample block at 48 kHz;
4. selects Philips I2S framing for the PCM5102A;
5. uses two DMA descriptors with 64 frames each;
6. fixes the FreeRTOS task entry-point signatures required by current ESP-IDF;
7. writes the ESP-IDF component `CMakeLists.txt` used by this project;
8. prints the exact AMY commit that was prepared.

To build a specific AMY commit instead of current `main`:

```bash
AMY_REF=<40-character-commit-sha> bash prepare_amy.sh
```

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

The firmware currently deliberately differs from stock upstream AMY in these areas:

### 48 kHz, 128-sample blocks

Stock AMY normally builds with 256-sample blocks at 44.1 kHz on this path. `prepare_amy.sh` changes it to:

```text
AMY_SAMPLE_RATE = 48000
AMY_BLOCK_SIZE  = 128
BLOCK_SIZE_BITS = 7
```

### I2S

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

### LP-core UART

The low-power core receives the 1 Mbaud serial stream on GPIO15. Complete messages are placed into a shared ring and signalled to the HP side through the ESP32-P4 LP mailbox. A high-priority HP FreeRTOS task then calls `amy_add_message()`.

The UART forwarding task runs one priority below AMY's render task, so audio rendering can preempt command forwarding.

## Reverb/delay memory note

AMY exposes a separate `ram_caps_delay` allocator for echo/reverb delay lines. This is important on the ESP32-P4 because multiple reverb instances allocate large delay buffers.

At the time this README was introduced, the checked-in `sdkconfig` still had ESP PSRAM disabled, so AMY's generic ESP-IDF default uses normal/default-capability RAM for delay lines. If the firmware is configured to use multiple independent AMY bus reverbs, that can exhaust internal memory and produce messages such as:

```text
unable to alloc delay line of 4096 samples
init_stereo_reverb: allocation failed, reverb disabled
```

The runtime reverb-memory configuration should therefore be treated as a separate target configuration issue rather than worked around in the Qt frontend. Once PSRAM is enabled for this board, large AMY delay allocations can be explicitly placed in PSRAM while keeping render-critical state in internal RAM.

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

Because the project follows current upstream AMY, refreshing it is simply:

```bash
bash prepare_amy.sh
idf.py build
```

If upstream changes one of the source locations that this project patches, `prepare_amy.sh` deliberately fails instead of silently producing a differently configured firmware. Update the preparation script and CI together when that happens.
