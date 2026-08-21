# LB Omnichord — AMY / ESP32-P4 version

This directory contains the actively developed Qt frontend for the AMY-based Omnichord. The Raspberry Pi runs the PySide6/Qt Quick interface and sends native AMY wire-protocol commands over UART to AMY running on the ESP32-P4.

Sonic Pi is not used by this version.

## Layout

- `code/` — Python application/backend (`main.py`, `amy_serial.py`)
- `gui/` — QML interface components and directly rendered instrument watermarks
- `config/` — serial/application defaults
- `instruments/` — curated AMY Juno/DX7 catalogue and 18 factory presets
- `music/` — chord, rhythm and intonation definitions
- `tests/` — touch tests, regression verification data and fixtures
- `rpi/` — Raspberry Pi startup/autostart helpers
- `docs/` — ESP32-P4 notes, screenshots and historical implementation notes

For Raspberry Pi installation, UART wiring, 1,000,000-baud 8N1 serial configuration, direct transport testing and startup instructions, see `README_rpi.md`.

## Running

From this directory after creating the virtual environment described in `README_rpi.md`:

```bash
.venv/bin/python code/main.py --serial-port /dev/serial0 --serial-baud 1000000 --windowed
```

The canonical data and QML files live in their logical directories. `code/` contains compatibility symlinks for the existing tested path lookups in `main.py`; this avoids changing application behaviour as part of the filesystem cleanup.

## Runtime AMY allocation

The host uses five independent AMY synth instances: drums, bass, strum, manually held chord and rhythm-triggered chord. Manual and rhythm chord voices share patch/settings but have independent voice pools and note lifetimes.

Rhythm timing is compiled into AMY's 48-PPQ sequencer; Linux/Python is not used as the beat clock.

The tuba watermark no longer requires a PNG runtime asset. It is drawn directly by `gui/InstrumentWatermarks.qml` together with the other background instrument artwork.
