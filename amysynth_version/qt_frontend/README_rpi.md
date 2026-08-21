# Raspberry Pi setup — AMY Omnichord Qt frontend

This frontend runs the Qt/PySide6 user interface on Raspberry Pi and sends the native AMY wire protocol over UART to the ESP32-P4. Sonic Pi is not part of this version.

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
- `tests/` — touch and regression/verification material
- `rpi/` — Raspberry Pi startup helpers
- `docs/` — implementation notes

`code/main.py` references these canonical directories directly. No symlinks or old-layout compatibility files are required.
