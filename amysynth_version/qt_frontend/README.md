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

`code/synth_state.py` defines `SynthState`, which owns one logical role's selected instrument and all per-instrument slider values. The same object handles catalogue defaults, preset overlays, instrument switches, UI slider edits, QML control-model values, complete transport payloads, state copying and sparse preset serialization.

`InstrumentBackend` therefore does not maintain a second slider/preset dictionary. Startup, preset loading, instrument selection and UI edits mutate the role's `SynthState` and publish the same complete logical state. A UI slider edit is not a special parameter packet: it modifies `SynthState`, then sends the same complete state representation used after preset and instrument changes.

On the receiver side, `AmySerialClient._apply_synth_state()` is the normal convergence point. It compares the incoming complete state with current AMY-side state and decides whether to load a patch or emit only the parameters that changed. The old name-only and parameter-only handlers exist only as compatibility adapters into that method. For the chord role, both manual synth 3 and rhythm synth 4 are derived from this one logical state.

When automatic rhythm chords start, the current chord parameters are explicitly reasserted on rhythm synth 4 after the sequencer-reset guard and before the new automatic chord events are installed. This prevents startup/preset state from diverging at the ESP32-P4 audio-block boundary.

## Runtime AMY allocation

The host uses five independent AMY synth instances: drums, bass, strum, manually held chord and rhythm-triggered chord. Manual and rhythm chord voices share patch/settings but have independent voice pools and note lifetimes.

Rhythm timing is compiled into AMY's 48-PPQ sequencer; Linux/Python is not used as the beat clock.

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
