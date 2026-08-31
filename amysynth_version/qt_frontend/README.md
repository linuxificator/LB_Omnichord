# LB Omnichord — AMY / ESP32-P4 version

This directory contains the actively developed Qt frontend for the AMY-based
Omnichord. It sends native AMY wire commands either over UART to AMY on the
ESP32-P4 or over local IPC to a separate desktop AMY service. Unix local IPC
selects packet-preserving or LF-framed stream sockets by endpoint capability,
not an OS-name branch; that currently yields packet sockets on Linux and stream
sockets on macOS. Native Windows uses a private named pipe through Qt's
`QLocalSocket`.

The Sonic Pi version elsewhere in the repository is frozen legacy material. It
is not a backend option for this frontend and must not be changed as part of
AMY work.

## Layout

- `code/` — Python application/backend, including synth, transport and MIDI-control state
- `gui/` — QML interface components and GUI assets
- `config/` — serial/application defaults
- `instruments/` — curated AMY Juno/DX7 catalogue and 18 factory presets
- `music/` — chord, rhythm and intonation definitions
- `screenshots/` — current public OMNI and MIDI screen images used by the root README
- `capture_screenshots.py` — deterministic offscreen capture of those real QML screens
- `tests/` — unit, headless, serial and native-AMY regression tests plus fixtures
- `rpi/` — Raspberry Pi startup/autostart helpers
- `docs/` — ESP32-P4 notes, screenshots and historical implementation notes

For Raspberry Pi installation, UART wiring, 1,000,000-baud 8N1 serial configuration, direct transport testing and startup instructions, see `README_rpi.md`.

For local Linux development with a separate AMY process, use:

```bash
./run_local.sh --windowed
```

The Qt process does not import AMY or own its lifetime; the launcher is only a
shell-level convenience wrapper for the two independent processes.

## Running

From this directory after creating the virtual environment described in `README_rpi.md`:

```bash
.venv/bin/python code/main.py --serial-port /dev/serial0 --serial-baud 1000000 --windowed
```

`main.py` addresses the canonical `gui/`, `config/`, `instruments/` and `music/` directories directly. There are no compatibility symlinks or duplicate runtime data files in `code/`.

## Public screenshots

Refresh the two screenshots used by the repository README with the same Python
environment as the frontend:

```bash
python capture_screenshots.py
```

The helper runs the real frontend and QML scene through Qt's offscreen software
renderer, uses an isolated temporary home and a drained pseudo-serial endpoint,
selects C minor for the OMNI strum-note guide, and injects three representative
MIDI CC movements for the grey MIDI controller bar. It overwrites only
`screenshots/omni.png` and `screenshots/midi.png`; it does not read or alter the
user's presets or connect to AMY hardware.

After every successful `main` release, CI runs this same capture against the
exact released commit. The captured PNGs must load as 1920x850 images and must
have enough sampled color variation to rule out a blank or error screen. CI then
stores them as release-tagged files such as `screenshots/omni-RYYYYMMDDTHHMMSS.png`
and updates the repository README links in the same commit. That screenshot-only
commit uses a human-readable `skip-rebuild` note plus GitHub's required
`skip-checks:true` trailer; ordinary merges and pushes to `main` still run the
complete release workflow.

## Synth-state architecture

Synth state is intentionally object-oriented and single-path.

`code/synth_state.py` defines `SynthState`, which owns one logical role's selected instrument and all per-instrument slider values. The same object handles catalogue defaults, preset overlays, instrument switches, UI slider edits, QML control-model values, transport payloads, state copying and sparse preset serialization.

`InstrumentBackend` therefore does not maintain a second slider/preset dictionary. Startup, preset loading, instrument selection and UI edits mutate the role's `SynthState` and publish the same logical state. A UI slider edit is not a special parameter packet: it modifies `SynthState`, then follows the same state-convergence path used after preset and instrument changes.

The catalogue distinguishes an AMY `native_default` from the application/UI `default`. If both are equal, AMY's factory patch remains authoritative and that control is omitted from the engine-override payload. Application corrections, stored preset overrides and user edits are sent explicitly. On the receiver side, `AmySerialClient._apply_synth_state()` is the single normal convergence point; if an override is removed, it reloads the patch and reapplies the remaining overrides so the native value is restored deterministically.

For the chord role, manual synth 3 and rhythm synth 4 are derived from this one logical state. When automatic rhythm chords start, only actual engine overrides are reasserted on rhythm synth 4 after the sequencer-reset guard and before automatic chord events are installed. Native factory coefficients are not redundantly rewritten.

## Control units

Frequency controls display real frequencies in Hz and use logarithmic slider travel. For Juno patches, `VCF base` is specifically the constant/base term of AMY's filter-frequency control model; the instantaneous cutoff also depends on note tracking, envelope and modulation coefficients stored in the factory patch. For example, Chorus Vibes has a native VCF base of about 27 Hz, but that does not mean its audible filter is fixed at 27 Hz.

Time controls display milliseconds, resonance displays Q, and modulation depths retain their documented physical/domain units. If a MIDI-note-valued control is exposed, the UI formats it as a note name and octave such as `C4` or `F♯3`, not as a raw MIDI integer.

## Runtime AMY allocation

OMNI uses five independent AMY synth instances: drums 0, bass 1, strum 2,
manually held chord 3 and rhythm-triggered chord 4. MIDI uses pitched synths
5–10 and drum synth 11. Manual and rhythm chord voices share patch/settings but
have independent voice pools and note lifetimes. The eleven-bus mapping is
documented in `../design/architecture.md`.

Rhythm timing is compiled into AMY's 48-PPQ sequencer; Linux/Python is not used as the beat clock. A live tuning change updates the shared tuned chord state: held manual chords are retuned immediately, rhythm chord and bass sequencer events are rebuilt with the new pitches, and subsequent strum notes use the selected tuning. Bass retuning therefore appears in the AMY wire/debug stream mainly as rebuilt `H...n<note>...i1Z` sequencer events rather than standalone immediate bass note commands.

Linux MIDI input opens ALSA raw-MIDI devices and an ALSA sequencer input port
named `LB Omnichord / MIDI In`. Graph tools such as `qpwgraph` can connect VMPK,
BLE MIDI bridges and MIDI Through directly to that port. See
`../design/midi.md`.

The bass watermark uses `gui/tuba_watermark.png`, loaded by `gui/InstrumentWatermarks.qml`.

## Regression tests

`tests/USE_CASES.md` is the behavioral regression contract. Test subsets are selected with:

```bash
python tests/run_tests.py --list
python tests/run_tests.py
python tests/run_tests.py --suite unit
python tests/run_tests.py --suite serial
python tests/run_tests.py --suite native-rhythm
```

The component suites are `unit`, `frontend`, `serial`, `presets`,
`native-controls` and `native-rhythm`; `all` runs them sequentially for
local/manual use. The `unit` suite automatically includes every top-level
`tests/test_*.py`. Pull requests targeting `main` and pushes to `main` run all
component suites in parallel.

Without `--suite`, the runner executes `unit`. The serial suite exercises the
production `pyserial` writer through a Linux PTY. Native suites feed that same
wire stream into the pinned LB Omnichord AMY release, started with 11 buses,
336 oscillators and the nested-pattern capacities in `INSTALL.md`, and verify
resulting AMY synth state. A passing
native test is therefore stronger than merely finding an expected command in
the host log. See `../design/testing.md` for the complete local/CI inventory.

## Platform releases

Every successful complete test run after an update to `main` publishes one
five-platform GitHub Release. Tags use `RYYYYMMDDTHHMMSS`; asset timestamps
omit the `T`. The release page has separate sections and downloads for:

- Linux x64: `LB_Omnichord.RYYYYMMDDHHMMSS.Linux-x86_64.AppImage`
- Raspberry Pi 4/5: `LB_Omnichord.RYYYYMMDDHHMMSS.RaspberryPi-aarch64.AppImage`
- macOS Apple Silicon: `LB_Omnichord.RYYYYMMDDHHMMSS.macOS-arm64.dmg`
- Windows x64: `LB_Omnichord.RYYYYMMDDHHMMSS.Windows-x86_64.zip`
- Android arm64: `LB_Omnichord.RYYYYMMDDHHMMSS.Android-arm64.apk`

Each package has a matching `.sha256` asset. All timestamps are UTC.

Every package contains the Qt frontend and supported AMY fork with the tiny PCM
drum bank. At runtime they remain separate processes connected by the
platform's private local transport. The Pi build requires 64-bit Raspberry Pi
OS and uses a Pi 4 baseline that also runs on Pi 5. The macOS DMG is Apple
Silicon-only and ad-hoc signed, but it is not signed with an Apple Developer ID
and is not Apple-notarized. The Windows zip contains separate
`LB_Omnichord.exe` and `amy_service.exe` binaries plus `LB_Omnichord.cmd` and
the internal `run_windows.ps1` supervisor. Extract the complete zip and
double-click `LB_Omnichord.cmd`; the wrapper applies an execution-policy bypass
only to that one bundled launcher process and leaves startup failures visible.
It uses a private Windows named pipe rather than WSL or a network listener. The
zip is portable and contains its dependencies, but it is deliberately not a
single executable: the frontend and AMY service remain separate processes and
the extracted directory must stay together.

The Android APK embeds the `amy-service` AAR from the pinned AMY Omnichord
release branch and exact commit. Its unexported provider owns the separate
`:amy` service process and Oboe output; PySide6 discovers the
application-private files directory and sends ordinary AMY packets through
`amy.sock`. The CI APK is debug-signed and is therefore an experimental
sideloadable artifact, not a Play Store/update-channel build. See
[the shared AMY release contract](packaging/AMY_RELEASE.md) and
[the Android package contract](packaging/android/README.md).

To install the macOS build, open the DMG, drag `LB_Omnichord.app` to
`Applications`, eject the DMG and try to open the app once. After macOS blocks
that first launch, open Apple menu > `System Settings` > `Privacy & Security`,
scroll down to `Security`, click `Open Anyway` beside the LB Omnichord message,
authenticate if requested, then click `Open` in the repeated warning. `Open
Anyway` is available for about one hour after the blocked launch attempt. This
adds an exception for LB Omnichord only; disabling Gatekeeper or globally
weakening `Allow applications downloaded from` is neither necessary nor
recommended. See [Apple's current instructions](https://support.apple.com/en-gb/guide/mac-help/mh40616/mac).

The first complete four-platform release, `R20260826T230234`, passed every
frontend suite and package job on native GitHub runners. Windows validation
included an offline native-AMY render and an end-to-end start of the extracted
Qt frontend and AMY service over the named pipe. The earlier x64 release
`R20260824T204611` was downloaded and physically tested on Linux with working
UI and audio. Raspberry Pi, macOS and Windows still need physical-device/audio
validation. Android also needs physical touchscreen/audio-route/latency
validation. Windows MIDI input and measured low-latency audio tuning are also
outstanding. See [the native Windows status and contract](docs/WINDOWS_NATIVE.md).
Current macOS and Windows package jobs additionally drive quick-tap and hold
gestures through the real packaged QML chord item; physical pointer and audio
validation on those platforms remains outstanding.
The Linux AppImage through WSL2/WSLg remains an optional diagnostic experiment,
not a Windows release target. Use GitHub Releases for current artifacts rather
than treating a baseline tag as a hard-coded update channel.

[Open GitHub Releases](https://github.com/linuxificator/LB_Omnichord/releases)
