# Installation

Status: authoritative installation/launch guide
Owner: frontend runtime and packaging
Applies to: active source and released package layouts
Last verified: 2026-09-01

This document covers the three runtime layouts for the AMY version of LB
Omnichord:

1. **Raspberry Pi frontend + ESP32-P4 AMY over UART** — the hardware layout
   used for the instrument.
2. **Local Unix desktop AMY** — the Qt frontend and the supported AMY release
   fork run as separate processes on Linux or macOS.
3. **Native Windows package** — separate frozen Qt and native AMY executables
   communicate through a private Windows named pipe.

The Raspberry Pi/UART path has been exercised on the project hardware. The
Linux two-process socket path has also been exercised with working audio,
multibus routing and the Gamma9001 drum bank. The published x86_64
AppImage was downloaded from GitHub Releases and physically validated with
working UI and audio on Linux on 2026-08-24. Release `R20260824T212125` also
passed native packaged-runtime validation for Linux x64, Linux aarch64 and
macOS arm64. Release `R20260826T230234` additionally passed native Windows x64
compilation, offline PCM rendering and packaged Qt/named-pipe/service startup.
Raspberry Pi, macOS and Windows still require physical-device/audio tests; WSL
is an optional Linux-artifact experiment rather than the Windows runtime.

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

# 2. Local Linux/macOS AMY

Unix local mode consists of two processes. `local_amy_service.py` owns AMY and
the desktop audio device. The Qt application only sends AMY wire packets over a
filesystem `AF_UNIX` socket. It does not import AMY or call an AMY API. The
service and client prefer packet-preserving `SOCK_SEQPACKET` and fall back to
an LF-framed stream according to endpoint capability, without testing an OS
name. Linux currently selects packets and macOS the stream fallback. This
deliberately matches the Android AMY-service boundary.

Start both processes with:

```text
./run_local.sh --windowed
```

Install the pinned nested-sequencer/Gamma9001 AMY release into the environment
used by the service. The Qt process remains independent of AMY.
`OMNICHORD_VENV` can override the launcher's
default `../omnichord-env`; `OMNICHORD_AMY_SOCKET` can override
`~/.omnichord/amy.sock`; and `OMNICHORD_AMY_ROOT` can override the expected AMY
checkout at `../amyfork/amy`.

Prepare the local AMY fork with the hosted Gamma9001 bank before first use (and
after rebuilding AMY):

```bash
./prepare_local_amy.sh
```

This reads the exact branch, commit and bank from `packaging/release_inputs.json`,
invokes `AMY_PCM_BANK=gamma9001`, and verifies that the installed extension
contains both Gamma9001 registration and PCM-data symbols. A bank/map mismatch
can accept every wire command while producing unrelated drum timbres.

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
`./prepare_local_amy.sh`; a generic or differently pinned AMY build is not
compatible with the supported release contract.

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
Linux. The fork must support the bus count and the exact Gamma9001 profile
declared by `release_inputs.json`.

Then run:

```bash
cd ../LB_Omnichord/amysynth_version/qt_frontend
./run_local.sh --windowed
```

The upstream AMY Python build links the macOS CoreAudio/CoreMIDI frameworks itself.

## Windows

### Install the native package

Download `LB_Omnichord.R<date><time>.Windows-x86_64.zip` and its
`.zip.sha256` file from GitHub Releases. Verify and extract them in PowerShell:

```powershell
$zip = Get-Item .\LB_Omnichord.R*.Windows-x86_64.zip
$checksum = "$($zip.FullName).sha256"
$expected = ((Get-Content $checksum) -split '\s+')[0].ToLowerInvariant()
$actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "Checksum mismatch" }
Expand-Archive -LiteralPath $zip.FullName -DestinationPath .\LB_Omnichord
```

Keep the extracted directory intact, then double-click:

```text
LB_Omnichord\LB_Omnichord.cmd
```

This is the supported Explorer entry point. It starts the bundled PowerShell
supervisor with a process-only execution-policy bypass and keeps its console
open when startup fails, so the actual error remains readable. It does not
change the user or machine execution policy. For a windowed diagnostic launch,
open Command Prompt in the extracted directory and run:

```bat
LB_Omnichord.cmd -Windowed
```

The zip is portable and includes its runtime dependencies after extraction,
but it is not a single executable. `LB_Omnichord.exe` is the frozen PySide6
frontend, `amy_service.exe` is the independent native AMY/miniaudio process,
and `run_windows.ps1` is their internal supervisor. The complete extracted
directory must remain together. This preserves the required two-process
architecture instead of hiding a second runtime in a self-extracting frontend.
The supervisor gives each run a unique private pipe name. Qt connects with
`QLocalSocket`; the service accepts LF-framed AMY wire commands with
`CreateNamedPipeA` and rejects remote clients. No TCP port is opened and AMY is
not linked into the frontend.

The Windows service is built with Gamma9001, matching Linux, Raspberry Pi,
macOS and Android. Its CMake target generates, links and registers the PCM blob;
using a Tiny service with the shipped Gamma map is a release-blocking mismatch.
ESP32-P4 remains a separately declared Tiny-bank firmware target.

The package is currently experimental. GitHub's Windows Server 2025 job proves
native compilation, offline non-silent PCM rendering, frozen QML/assets,
named-pipe command delivery, quick-tap/hold behavior through the packaged QML
chord item and clean process shutdown. Physical Windows pointer hardware,
audio, MIDI and low-latency/drop-out behavior have not yet been validated. The
current MIDI reader is ALSA-only, so native Windows MIDI input is not
implemented.

### Build the native package

Install Python 3.12, CMake and either Visual Studio 2026 or Visual Studio 2022
with the C++ build workload. Install the declared build requirements,
check out the pinned compatible AMY fork, then run from this directory:

```powershell
python -m pip install -r requirements-build.txt
$env:OMNICHORD_AMY_ROOT = "C:\path\to\amy"
.\packaging\build_windows.ps1
```

The zip and checksum are written below `dist`. The release workflow pins both
AMY fork branch `releases/amy_omnichord_R20260903T201525` and commit
`3d6ec079eb73bf5d021312ff8ac07ebae8e5eae7`; local release candidates must use
that exact commit unless the shared release contract and its compatibility
tests are deliberately updated together.

See [WINDOWS_NATIVE.md](docs/WINDOWS_NATIVE.md) for the full transport,
packaging, smoke-test and remaining-hardware-validation contract.

### Optional WSL experiment

WSL2/WSLg may still run the Linux artifact for diagnostic experiments, but it
is not the Windows architecture or the native release path. Follow
[WSL_APPIMAGE_TESTING.md](docs/WSL_APPIMAGE_TESTING.md) when that experiment is
specifically useful; do not use its results as evidence for native Windows
audio, MIDI or named-pipe behavior.

---

# Reverb and runtime notes

The complete application uses eleven isolated AMY buses: four for OMNI, six
for the individual MIDI instruments and one for MIDI drums. See
`../design/architecture.md` for the authoritative mapping.

OMNI and MIDI each have independent header reverb state. Within either section,
`DRM` decides whether that section's drum bus receives the same room.

# Linux MIDI input

The frontend reads ALSA raw-MIDI devices matching `/dev/snd/midiC*D*` and also
creates an ALSA Sequencer input named `LB Omnichord` with port `MIDI In`.
Check raw devices with `amidi -l` and sequencer ports with `aconnect -lio` or
`qpwgraph`. VMPK can connect directly to the Omnichord sequencer port; a virtual
raw bridge is not required.

```bash
aconnect -lio
```

Start Omnichord, then select or connect `LB Omnichord / MIDI In` as VMPK's
ALSA Sequencer output. Use `snd-virmidi` only when deliberately testing the raw
MIDI reader rather than for ordinary VMPK input.

# Automated tests

Use the same Python environment as the frontend:

```bash
python tests/run_tests.py --list
python tests/run_tests.py
python tests/run_tests.py --suite all
```

The command without `--suite` runs all automatically discovered unit tests.
`all` additionally needs Linux PTY/local-socket support, PySide6, pyserial and
the pinned LB Omnichord AMY release. Native suites start AMY with 11 buses, 336
oscillators, 1024 stored sequence groups, 64 local events per group and 40
active or pending group executions. Run `./prepare_local_amy.sh` first when
that release is not installed. The full suite and CI layout is documented in
`../design/testing.md`.

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

The release job mounts the final DMG and drives a quick tap and hold through a
real packaged QML chord key before publication. That catches QML/backend input
wiring regressions, but it does not prove a physical Mac trackpad, touchscreen
or audio device.

## Install the Android arm64 APK

Download `LB_Omnichord.R<date><time>.Android-arm64.apk` and its checksum from
GitHub Releases, then verify it on a Linux host before transferring it:

```bash
sha256sum --check LB_Omnichord.R*.Android-arm64.apk.sha256
```

On the Android device, allow installation from the file/browser application
used to open the APK, then install it. This experimental artifact is CI
debug-signed; it is not a Play Store package or a stable update channel. The
APK contains both the PySide6 frontend and the AMY AAR, but they run as separate
processes. No AMY Python package or external service installation is needed.
See `packaging/android/README.md` for the socket, test and signing contract.

CI installs the x86_64 build into an emulator, drives real packaged QML chord
tap/hold input, requires the private `amy.sock` service connection, and checks
that AMY's non-silent render samples match the samples sent to Oboe. A physical
arm64 phone/tablet still needs touchscreen, speaker/headphone route, lifecycle,
latency and sustained-load validation.

# Troubleshooting

## No local AMY module (Unix convenience service)

If local mode reports that `amy` or `c_amy` cannot be imported, verify the package in the frontend virtual environment:

```bash
.venv/bin/python -c 'import amy, c_amy; print(amy.__file__)'
```

Then reinstall from the upstream AMY checkout using that exact Python interpreter.

## No Raspberry Pi serial output

Confirm that `/dev/serial0` exists, the console login is disabled, and the ESP32-P4 is configured for the same 1,000,000-baud 8N1 transport.

## Test installation without fullscreen

Use `--windowed` first. Fullscreen and automatic scaling can be enabled after audio and input are working.
