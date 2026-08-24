# Installation

This document covers the two supported runtime layouts for the AMY version of LB Omnichord:

1. **Raspberry Pi frontend + ESP32-P4 AMY over UART** — the hardware layout used for the instrument.
2. **Local desktop AMY** — the Qt frontend and the supported AMY bus-mixer fork run on the same computer. This path is useful for development and does not need the ESP32-P4.

The Raspberry Pi/UART path has been exercised on the project hardware. The
Linux two-process socket path has also been exercised with working audio,
multibus routing and the ESP32-compatible tiny drum bank. The published x86_64
AppImage was downloaded from GitHub Releases and physically validated with
working UI and audio on Linux on 2026-08-24. Release `R20260824T212125` also
passed native packaged-runtime validation for Linux x64, Linux aarch64 and
macOS arm64. Raspberry Pi and macOS still require physical-device/audio tests;
WSL remains development guidance rather than a validated release recipe.

## Repository layout

All commands below assume the AMY frontend directory:

```text
LB_Omnichord/amysynth_version/qt_frontend
```

The Sonic Pi version is frozen legacy material. It is unrelated to this
installation and must not be modified as part of AMY work.

---

# 1. Raspberry Pi frontend + ESP32-P4 AMY

## UART wiring

Connect only TX and ground:

- Raspberry Pi GPIO14 / TXD, physical pin 8 -> ESP32-P4 GPIO15 / LP-UART RX
- Raspberry Pi GND, physical pin 6 -> ESP32-P4 GND

Both boards use 3.3 V logic. Do not connect their power rails through the UART link.

The frontend sends one complete AMY wire message per LF-delimited UART line. AMY messages themselves are terminated by `Z`.

## Enable the Raspberry Pi UART

Run:

```bash
sudo raspi-config
```

Choose **Interface Options -> Serial Port**:

- disable the login shell on the serial port;
- enable the serial-port hardware.

Reboot, then verify:

```bash
ls -l /dev/serial0
```

The project uses **1,000,000 baud, 8 data bits, no parity, one stop bit, no hardware flow control (8N1)**.

## Install the Qt frontend

From the repository root:

```bash
cd amysynth_version/qt_frontend
sudo apt update
sudo apt install python3-venv python3-pip
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Re-run the requirements command after updating an existing environment.

## Run

Windowed:

```bash
.venv/bin/python code/main.py \
  --serial-port /dev/serial0 \
  --serial-baud 1000000 \
  --windowed
```

Fullscreen:

```bash
.venv/bin/python code/main.py \
  --serial-port /dev/serial0 \
  --serial-baud 1000000 \
  --fullscreen
```

A USB UART can be used instead by supplying its device, for example `/dev/ttyUSB0`.

## Direct UART test

Before debugging Qt, the UART path can be checked directly:

```bash
stty -F /dev/serial0 1000000 raw -echo cs8 -cstopb -parenb -crtscts
printf 'v0w0f440Q0l0.2Z\n' > /dev/serial0
```

## Autostart

`rpi/omnichord_start` starts the frontend fullscreen. It accepts:

```text
OMNICHORD_DIR
OMNICHORD_SERIAL_PORT
OMNICHORD_SERIAL_BAUD
```

The default directory is `$HOME/LB_Omnichord/amysynth_version/qt_frontend`, the default serial device is `/dev/serial0`, and the default baud rate is 1000000.

---

# 2. Local desktop AMY

Local mode consists of two processes. `local_amy_service.py` owns AMY and the
desktop audio device. The Qt application only sends AMY wire packets over a
filesystem `AF_UNIX` `SOCK_SEQPACKET` socket. It does not import AMY or call an
AMY API. This deliberately matches the Android AMY-service boundary.

Start both processes with:

```text
./run_local.sh --windowed
```

Install the bus-mixer/tiny-bank-capable AMY fork into the environment used by
the service. The Qt process remains independent of those modules.
`OMNICHORD_VENV` can override the launcher's
default `../omnichord-env`; `OMNICHORD_AMY_SOCKET` can override
`~/.omnichord/amy.sock`; and `OMNICHORD_AMY_ROOT` can override the expected AMY
checkout at `../amyfork/amy`.

The ESP32-P4 drum mapping uses AMY's tiny PCM bank. Prepare the local AMY fork
with the same bank before first use (and after rebuilding AMY):

```bash
./prepare_local_amy.sh
```

This invokes the fork's `AMY_PCM_BANK=tiny` build option and verifies that the
installed extension does not contain Gamma9001 symbols. Without this explicit
choice, Linux presets 0–18 refer to a different TR-808 table and the same wire
commands produce congas/tones in place of hats and snares.

## Linux

Install a Python development environment and C/C++ compiler. On Debian/Ubuntu systems:

```bash
sudo apt update
sudo apt install git python3-venv python3-pip python3-dev build-essential
```

Create the frontend environment:

```bash
git clone https://github.com/linuxificator/LB_Omnichord.git
cd LB_Omnichord/amysynth_version/qt_frontend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r requirements.txt
```

Place the project AMY fork at `../amyfork/amy` relative to the LB_Omnichord
repository, or set `OMNICHORD_AMY_ROOT`. Then run
`./prepare_local_amy.sh`; a generic upstream/Gamma9001 build is not compatible
with the shipped drum mapping.

Run the frontend:

```bash
cd ../LB_Omnichord/amysynth_version/qt_frontend
./run_local.sh --windowed
```

AMY uses the desktop's default audio device through its current native audio backend.

## macOS

Install Apple's command-line development tools if they are not already installed:

```bash
xcode-select --install
```

Install Python 3 and Git using your normal macOS package source, then:

```bash
git clone https://github.com/linuxificator/LB_Omnichord.git
cd LB_Omnichord/amysynth_version/qt_frontend
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools
.venv/bin/python -m pip install -r requirements.txt
```

Use the same project AMY fork and `prepare_local_amy.sh` process described for
Linux. The fork must support the bus count and `AMY_PCM_BANK=tiny`; installing a
generic Gamma9001 build changes the drum preset meanings.

Then run:

```bash
cd ../LB_Omnichord/amysynth_version/qt_frontend
./run_local.sh --windowed
```

The upstream AMY Python build links the macOS CoreAudio/CoreMIDI frameworks itself.

## Windows

### Current upstream limitation

The Omnichord local mode requires AMY's Python extension (`amy` plus `c_amy`). Current upstream AMY explicitly supports a native Windows **C** build, but its current Python `setup.py` still assumes a Unix-like Python environment (`os.uname()`) and explicitly selects `gcc`/`g++`. For that reason the native-Windows Python installation is not presented here as a known-working path.

The practical Windows development route is currently **WSL2 + WSLg** on Windows 11. This provides a Linux Python/compiler environment while WSLg supplies GUI and audio integration.

Install WSL/Ubuntu from an elevated PowerShell if it is not already present:

```powershell
wsl --install -d Ubuntu
```

After reboot/setup, open the Ubuntu terminal and use the Linux instructions above:

```bash
sudo apt update
sudo apt install git python3-venv python3-pip python3-dev build-essential
```

Keep the repositories in the WSL Linux filesystem (for example under `~/src`) rather than under `/mnt/c` for better build performance. Then install both the frontend and AMY in one virtual environment exactly as in the Linux section and run:

```bash
./run_local.sh --windowed
```

On a normal Windows 11 WSLg installation the Qt window and AMY audio should be forwarded to the Windows desktop. This project has not yet validated that path.

For reference, upstream AMY's native Windows C example instead requires Visual
Studio Build Tools 2022 with the C++ workload and can be built from
`amy/windows`; that native C executable is not the separate Python-backed AMY
service used by `run_local.sh`.

---

# Reverb and runtime notes

The complete application uses eleven isolated AMY buses: four for OMNI, six
for the individual MIDI instruments and one for MIDI drums. See
`../design/architecture.md` for the authoritative mapping.

OMNI and MIDI each have independent header reverb state. Within either section,
`DRM` decides whether that section's drum bus receives the same room.

# Linux MIDI input

The frontend reads ALSA raw-MIDI devices matching `/dev/snd/midiC*D*` by
default. Check them with `amidi -l`. VMPK is normally an ALSA Sequencer-only
source and therefore needs a virtual raw bridge for the current backend:

```bash
sudo modprobe snd-virmidi
amidi -l
aconnect -lio
```

Select a Virtual Raw MIDI ALSA output in VMPK, then start/restart Omnichord.
Direct ALSA Sequencer subscription is not implemented.

# Automated tests

Use the same Python environment as the frontend:

```bash
python tests/run_tests.py --list
python tests/run_tests.py
python tests/run_tests.py --suite all
```

The command without `--suite` runs all automatically discovered unit tests.
`all` additionally needs Linux PTY/local-socket support, PySide6, pyserial and
the LB Omnichord AMY bus-mixer fork. Native suites start AMY with 11 buses and
336 oscillators; an ordinary four-bus upstream build is deliberately rejected
instead of silently routing extra buses to bus 0. Run `./prepare_local_amy.sh`
first when the supported fork is not installed. The full suite and CI layout
are documented in `../design/testing.md`.

## Install a released Linux x86_64 AppImage

Download `LB_Omnichord.R<date><time>.Linux-x86_64.AppImage` and its `.sha256` file from the
[GitHub Releases page](https://github.com/linuxificator/LB_Omnichord/releases),
then run:

```bash
sha256sum --check LB_Omnichord.R*.Linux-x86_64.AppImage.sha256
chmod +x LB_Omnichord.R*.Linux-x86_64.AppImage
./LB_Omnichord.R*.Linux-x86_64.AppImage --windowed
```

The x86_64 AppImage already contains PySide6 and the compatible AMY service; a
separate Python environment or AMY checkout is not needed. AMY still runs as a
separate child process and communicates with the frontend over a private local
socket. The release is built on Ubuntu 22.04 for use on contemporary x86_64
Linux distributions. Release `R20260824T204611` is the first artifact confirmed
after download to start and produce working UI/audio; newer releases remain
discoverable through GitHub Releases and must pass the same automated gate.

## Install the Raspberry Pi 4/5 AppImage

Use a 64-bit Raspberry Pi OS installation. Download the
`RaspberryPi-aarch64.AppImage` asset and checksum, then run:

```bash
sha256sum --check LB_Omnichord.R*.RaspberryPi-aarch64.AppImage.sha256
chmod +x LB_Omnichord.R*.RaspberryPi-aarch64.AppImage
./LB_Omnichord.R*.RaspberryPi-aarch64.AppImage --windowed
```

One Pi 4 baseline is used for both Pi 4 and Pi 5; no separate Pi 5 build is
needed. Pi 3 and older are not supported by this package. This packaged path is
separate from the Raspberry Pi + ESP32-P4 UART deployment described above.

## Install the macOS DMG

Download `LB_Omnichord.R<date><time>.macOS-arm64.dmg` and verify it with:

```bash
shasum -a 256 -c LB_Omnichord.R*.macOS-arm64.dmg.sha256
```

Open the DMG and copy `LB_Omnichord.app` to Applications. The first macOS
package targets Apple Silicon only. It is ad-hoc signed but not notarized with
an Apple Developer ID, so Gatekeeper may require Control-click **Open** and an
explicit confirmation on first launch. Intel Macs are not supported by this
DMG.

# Troubleshooting

## No local AMY module

If local mode reports that `amy` or `c_amy` cannot be imported, verify the package in the frontend virtual environment:

```bash
.venv/bin/python -c 'import amy, c_amy; print(amy.__file__)'
```

Then reinstall from the upstream AMY checkout using that exact Python interpreter.

## No Raspberry Pi serial output

Confirm that `/dev/serial0` exists, the console login is disabled, and the ESP32-P4 is configured for the same 1,000,000-baud 8N1 transport.

## Test installation without fullscreen

Use `--windowed` first. Fullscreen and automatic scaling can be enabled after audio and input are working.
