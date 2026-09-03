# Raspberry Pi setup — AMY Omnichord Qt frontend

This frontend runs the Qt/PySide6 user interface on Raspberry Pi and sends the
native AMY wire protocol over UART to the ESP32-P4. The Sonic Pi implementation
is frozen legacy material and is never modified as part of this AMY version.

## Raspberry Pi AppImage

GitHub Releases also provide a self-contained `RaspberryPi-aarch64.AppImage`
for 64-bit Raspberry Pi OS. It targets the Raspberry Pi 4 instruction-set
baseline and runs on both Pi 4 and Pi 5; separate builds are unnecessary. Pi 3
and older models are outside the supported release target.

The AppImage bundles the pinned native AMY service and uses the Pi's local
audio output. It preserves the process boundary: its launcher starts AMY and
Qt as separate processes and they exchange AMY wire packets over a private
Unix socket. Use this package when the Pi itself should synthesize audio. The
source install and UART instructions below remain the path for driving an
external ESP32-P4 instead.

Make the downloaded package executable and start it directly:

```bash
chmod +x LB_Omnichord.R*.RaspberryPi-aarch64.AppImage
./LB_Omnichord.R*.RaspberryPi-aarch64.AppImage
```

## Wiring

Connect only UART TX and ground:

- Raspberry Pi GPIO14 / TXD, physical pin 8 -> ESP32-P4 GPIO15 / LP-UART RX
- Raspberry Pi GND, physical pin 6 -> ESP32-P4 GND

Both sides use 3.3 V logic. Do not connect either board's power rail through this UART link.

## Raspberry Pi serial setup

Run `sudo raspi-config`, select **Interface Options -> Serial Port**, disable the login shell on the serial port, and enable the serial-port hardware. Reboot afterwards.

The normal device is `/dev/serial0`. Check it with:

```bash
ls -l /dev/serial0
```

The application defaults to **1,000,000 baud, 8 data bits, no parity, 1 stop bit, no hardware flow control (8N1)**. The ESP32-P4 receiver must use the same baud rate.

The serial defaults are in `config/amy_config.json`. Command-line options override them.

## Install

From the repository root:

```bash
cd amysynth_version/qt_frontend
sudo apt update
sudo apt install python3-venv python3-pip
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

Windowed test:

```bash
.venv/bin/python code/main.py --serial-port /dev/serial0 --serial-baud 1000000 --windowed
```

Fullscreen:

```bash
.venv/bin/python code/main.py --serial-port /dev/serial0 --serial-baud 1000000 --fullscreen
```

The program may also use `/dev/ttyAMA0` or a USB UART such as `/dev/ttyUSB0` when supplied with `--serial-port`.

## USB MIDI input

The current Linux input backend opens every ALSA raw-MIDI character device
matching `/dev/snd/midiC*D*`. It receives Note On/Off, including velocity-zero
Note Off and running status. The glob and enable flag are configured under
`midi_input` in `config/amy_config.json`.

Check physical/virtual raw devices with:

```bash
amidi -l
ls -l /dev/snd/midiC*D*
```

ALSA Sequencer-only software such as VMPK is not visible to this reader. For
testing, load `snd-virmidi`, select a Virtual Raw MIDI output in VMPK, and then
start/restart the frontend:

```bash
sudo modprobe snd-virmidi
amidi -l
aconnect -lio
```

## Direct UART test

Before debugging Qt, the UART path can be tested directly:

```bash
stty -F /dev/serial0 1000000 raw -echo cs8 -cstopb -parenb -crtscts
printf 'v0w0f440Q0l0.2Z\n' > /dev/serial0
```

`Z` terminates the AMY message. The trailing LF is UART transport framing consumed by the ESP32-P4 receiver.

## Autostart

`rpi/omnichord_start` starts the frontend fullscreen. It accepts these environment overrides:

```text
OMNICHORD_DIR
OMNICHORD_SERIAL_PORT
OMNICHORD_SERIAL_BAUD
```

The default application directory is `$HOME/LB_Omnichord/amysynth_version/qt_frontend`, the default serial device is `/dev/serial0`, and the default baud rate is 1000000.

## Directory layout

- `code/` — Python application and AMY serial backend
- `gui/` — QML interface components and GUI assets
- `config/` — application and serial configuration
- `instruments/` — AMY instrument catalogue and factory presets
- `music/` — chords, rhythms and intonation definitions
- `tests/` — automated regression suites and the manual touchscreen diagnostic
- `rpi/` — Raspberry Pi startup helpers
- `docs/` — implementation notes

`code/main.py` references these canonical directories directly. No symlinks or old-layout compatibility files are required.

## Automated tests

From this directory, `python tests/run_tests.py` runs the automatically
discovered unit suite. Use `python tests/run_tests.py --list` for all suite
names or `python tests/run_tests.py --suite all` for the complete matrix. The
two native suites require the pinned LB AMY release and are principally
intended for Linux development/CI; they are not required to run the Qt-only
frontend on a Raspberry Pi connected to an ESP32-P4. See
`../design/testing.md` for details.
