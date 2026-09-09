# Raspberry Pi setup — AMY Omnichord Qt frontend

This frontend runs the Qt/PySide6 user interface on Raspberry Pi and sends the
native AMY wire protocol over UART to the ESP32-P4. The Sonic Pi implementation
is frozen legacy material and is never modified as part of this AMY version.

## Raspberry Pi AppImage

GitHub Releases also provide a portable `RaspberryPi-aarch64.AppImage` for
64-bit Raspberry Pi OS. It targets the Raspberry Pi 4 instruction-set
baseline and runs on both Pi 4 and Pi 5; separate builds are unnecessary. Pi 3
and older models are outside the supported release target.

The package contains LB Omnichord, PySide6/Qt, AMY and their application
resources. Like other Linux application packages, it does not and cannot
contain the running kernel, Wayland compositor or hardware-specific Mesa/V3D
driver stack. Current 64-bit Raspberry Pi OS must therefore provide its normal
EGL, Wayland EGL and OpenGL libraries. The package deliberately uses the Pi
system's `libstdc++.so.6` so that this host graphics stack and its C++ ABI stay
matched; substituting an older builder runtime can make the Qt Wayland plugin
load while EGL context creation still fails.

The AppImage bundles the pinned native AMY service and defaults to the Pi's
local audio output. It preserves the process boundary: its launcher starts AMY
and Qt as separate processes and they exchange AMY wire packets over a private
Unix socket. The same self-contained AppImage can instead drive an external
ESP32-P4 over UART by passing `--serial`; in that mode it does not start the
local AMY process.

Make the downloaded package executable and start it directly:

```bash
chmod +x LB_Omnichord.R*.RaspberryPi-aarch64.AppImage
./LB_Omnichord.R*.RaspberryPi-aarch64.AppImage
```

For reliable local audio under load, download the matching
`LB_Omnichord.R*.Pi4-Pi5-realtime-setup.sh` asset from the same release and
install the measured, reversible host profile once:

```bash
chmod +x LB_Omnichord.R*.Pi4-Pi5-realtime-setup.sh
sudo ./LB_Omnichord.R*.Pi4-Pi5-realtime-setup.sh --user "$USER"
sudo reboot
```

The installer accepts only Pi 4/5 hardware, verifies its embedded setup
payload, preserves the original boot command line in a checksummed rollback
snapshot, activates the performance governor, and installs the measured
AMY/PipeWire scheduling watcher. An independent `.sha256` asset remains
available for users who want to verify the downloaded script itself, but this
optional security step is not required by the startup instructions. Both the
AppImage and `run_local.sh` display a startup warning when any part of that
profile is absent. No warning is displayed on non-Pi systems or after the full
profile is active.

To use the ESP32-P4 connected to the configured `/dev/serial0` at 1,000,000
baud:

```bash
./LB_Omnichord.R*.RaspberryPi-aarch64.AppImage --serial
```

The normal frontend overrides remain available, for example:

```bash
./LB_Omnichord.R*.RaspberryPi-aarch64.AppImage \
    --serial --serial-port /dev/ttyUSB0 --serial-baud 1000000
```

Released packages remain fully self-contained in either mode. Serial mode
selects external hardware; it does not download, install or import AMY into the
frontend process.

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
sudo apt update
sudo apt install python3-venv python3-pip
```

The source launcher creates and verifies the clone-local `.venv` itself.

## Run

Windowed test:

```bash
cd amysynth_version/qt_frontend
./run_local.sh --serial --windowed
```

Fullscreen:

```bash
cd amysynth_version/qt_frontend
./run_local.sh --serial --fullscreen
```

`--serial` prevents the launcher from starting local AMY and leaves the
frontend's socket options unset, so the normal serial transport is selected.
The default `/dev/serial0` and 1,000,000 baud come from `amy_config.json`.
The program may also use `/dev/ttyAMA0` or a USB UART such as `/dev/ttyUSB0`
when supplied after `--serial`, for example `./run_local.sh --serial
--serial-port /dev/ttyUSB0 --windowed`.

## Run AMY locally on the Raspberry Pi

To render AMY audio on the Pi from a source checkout instead of sending wire
commands to an ESP32-P4, start it directly:

```bash
cd amysynth_version/qt_frontend
./run_local.sh --windowed
```

On the first run, the source launcher creates `.venv` in the Git-clone root,
installs `requirements-source.txt`, checks out the exact AMY release below
`.amy/<commit>/`, and builds its Gamma9001 `c_amy` service. Both directories
are ignored by Git. This first preparation needs network access and the normal
Python/C build prerequisites. Later launches perform offline dependency,
commit/bank, symbol and binary-digest checks and start without downloading.

`run_local.sh` starts the standalone AMY service and the Qt frontend as two
processes connected by the local wire-protocol socket. `OMNICHORD_VENV` and
`OMNICHORD_AMY_ROOT` remain explicit overrides for intentionally managed
locations. Released AppImages remain self-contained and never execute this
source-only bootstrap.

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
`../design/arch/testing.md` for details.
