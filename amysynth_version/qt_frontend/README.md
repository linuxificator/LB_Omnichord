# LB Omnichord — AMY / ESP32-P4 version

This directory contains the actively developed Qt frontend for the AMY-based Omnichord. The Raspberry Pi runs the PySide6/Qt Quick interface and sends native AMY wire-protocol commands over UART to AMY running on the ESP32-P4.

Sonic Pi is not used by this version.

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

The host uses five independent AMY synth instances: drums, bass, strum, manually held chord and rhythm-triggered chord. Manual and rhythm chord voices share patch/settings but have independent voice pools and note lifetimes.

Rhythm timing is compiled into AMY's 48-PPQ sequencer; Linux/Python is not used as the beat clock. A live tuning change updates the shared tuned chord state: held manual chords are retuned immediately, rhythm chord and bass sequencer events are rebuilt with the new pitches, and subsequent strum notes use the selected tuning. Bass retuning therefore appears in the AMY wire/debug stream mainly as rebuilt `H...n<note>...i1Z` sequencer events rather than standalone immediate bass note commands.

The bass watermark uses `gui/tuba_watermark.png`, loaded by `gui/InstrumentWatermarks.qml`.

## Regression tests

`tests/USE_CASES.md` is the behavioral regression contract. Test subsets are selected with:

```bash
python tests/run_tests.py --list
python tests/run_tests.py --suite serial
python tests/run_tests.py --suite native-rhythm
```

The component suites are `unit-controls`, `frontend`, `serial`, `presets`, `native-controls` and `native-rhythm`; `all` runs them sequentially for local/manual use. Pull requests targeting `main` run all component suites in parallel.

The serial suite exercises the production `pyserial` writer through a Linux PTY. Native suites feed that same wire stream into current upstream AMY and verify resulting AMY synth state, so passing is stronger than merely finding an expected command in the host log.
