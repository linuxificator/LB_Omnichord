# LB Omnichord — AMY / ESP32-P4 version

This directory contains the actively developed Qt frontend for the AMY-based
Omnichord. It sends native AMY wire commands either over UART to AMY on the
ESP32-P4 or over a Unix packet socket to a separate local AMY service.

The Sonic Pi version elsewhere in the repository is frozen legacy material. It
is not a backend option for this frontend and must not be changed as part of
AMY work.

## Layout

- `code/` — Python application/backend (`main.py`, `synth_state.py`, `amy_serial.py`)
- `gui/` — QML interface components and GUI assets
- `config/` — serial/application defaults
- `instruments/` — curated AMY Juno/DX7 catalogue and 18 factory presets
- `music/` — chord, rhythm and intonation definitions
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

Linux MIDI input currently opens ALSA raw-MIDI devices matching
`/dev/snd/midiC*D*`. VMPK exposes an ALSA Sequencer port rather than a raw device;
use `snd-virmidi` as a bridge for current testing. See `../design/midi.md`.

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
wire stream into the pinned LB Omnichord AMY bus-mixer fork, started with 11
buses and 336 oscillators, and verify resulting AMY synth state. A passing
native test is therefore stronger than merely finding an expected command in
the host log. See `../design/testing.md` for the complete local/CI inventory.

## Linux AppImage releases

Every successful complete test run after an update to `main` publishes an
x86_64 AppImage under this repository's GitHub Releases. Tags use
`RYYYYMMDDTHHMMSS`; assets use
`LB_Omnichord.RYYYYMMDDHHMMSS.AppImage`. Both timestamps are UTC.

The AppImage contains the Qt frontend and the supported AMY fork with the tiny
PCM drum bank. At runtime they remain separate processes connected through the
same Unix wire-protocol socket as `run_local.sh`. Download the accompanying
`.sha256` asset to verify the file.
