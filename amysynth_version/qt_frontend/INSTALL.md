# Installation

This document covers the two supported runtime layouts for the AMY version of LB Omnichord:

1. **Raspberry Pi frontend + ESP32-P4 AMY over UART** — the hardware layout used for the instrument.
2. **Local desktop AMY** — the Qt frontend and the upstream AMY Python extension run on the same computer. This path is useful for development and does not need the ESP32-P4.

The Raspberry Pi/UART path has been exercised on the project hardware. The local desktop path is implemented but has not yet been hardware/audio-tested as part of this project, so the platform instructions below follow the current upstream AMY build instructions and should be treated as development instructions rather than a validated release recipe.

## Repository layout

All commands below assume the AMY frontend directory:

```text
LB_Omnichord/amysynth_version/qt_frontend
```

The Sonic Pi version is unrelated to this installation.

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

Local mode uses the same Omnichord wire-command backend, but instead of writing the commands to a serial port it feeds them directly to the upstream Python `amy`/`c_amy` package. The application starts AMY with `amy.live(default_synths=0)` and then allocates the same Omnichord synths 0..4 used by the ESP32-P4 layout.

Run local mode with:

```text
--local-amy
```

The upstream AMY project currently documents Python installation from a source checkout with:

```bash
python -m pip install .
```

Install AMY into the **same virtual environment** as this frontend so `code/main.py` can import both `amy` and `c_amy`.

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

Install current upstream AMY into that environment. The following keeps the AMY source beside the Omnichord repository, but any source location is fine:

```bash
cd ../../..
git clone https://github.com/shorepine/amy.git
cd amy
../LB_Omnichord/amysynth_version/qt_frontend/.venv/bin/python -m pip install .
```

Run the frontend:

```bash
cd ../LB_Omnichord/amysynth_version/qt_frontend
.venv/bin/python code/main.py --local-amy --windowed
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

Clone and install AMY into the same environment:

```bash
cd ../../..
git clone https://github.com/shorepine/amy.git
cd amy
../LB_Omnichord/amysynth_version/qt_frontend/.venv/bin/python -m pip install .
```

Then run:

```bash
cd ../LB_Omnichord/amysynth_version/qt_frontend
.venv/bin/python code/main.py --local-amy --windowed
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
.venv/bin/python code/main.py --local-amy --windowed
```

On a normal Windows 11 WSLg installation the Qt window and AMY audio should be forwarded to the Windows desktop. This project has not yet validated that path.

For reference, upstream AMY's native Windows C example instead requires Visual Studio Build Tools 2022 with the C++ workload and can be built from `amy/windows`; that native C executable is not what `--local-amy` imports.

---

# Reverb and runtime notes

The Omnichord uses two AMY buses:

- the main bus contains chord, strum and bass;
- the percussion bus contains drums only.

The header reverb controls program AMY's reverb `level`, `liveness` and `damping` values. `DRM` decides whether the percussion bus receives the same reverb. With `DRM` off the drum bus is explicitly programmed with reverb level 0. The fourth AMY reverb parameter, crossover frequency, is not changed by the UI.

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
