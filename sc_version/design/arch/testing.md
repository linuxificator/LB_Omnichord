# SuperCollider edition testing

Status: authoritative test and package validation contract
Owner: frontend and SC engine
Applies to: `sc_version`
Last verified: 2026-09-15

`qt_frontend/tests/run_tests.py` is the single runner. `unit` discovers every
top-level `test_*.py`; named suites group process, platform, SC compiler,
sequencer, audio, bank and package evidence. Each script is isolated and the
runner writes an atomic JSON report. Coverage is diagnostic branch coverage,
not an arbitrary global score.

Important suites:

- `quality`: syntax, JSON/Markdown, import/dependency boundaries, QML warning
  ratchet, Ruff and mypy.
- `sc-desktop-portable`: portable frontend/config/process/package contracts.
- `portable-input-processes` and `desktop-network-discovery`: external sender
  processes and protocol boundaries.
- `platform-input-linux`: a PTY MIDI source, real frontend and separate fake SC
  process.
- `sc-compiler`, `sc-sequencer`, `sc-audio`, `sc-banks`: real SC language and
  deterministic NRT evidence.
- `sc-packaged`: source/package/runtime/release invariants.

GitHub runs portable gates on Linux x86_64, Raspberry Pi aarch64, macOS arm64
and Windows x86_64. Linux also runs real SC compiler/NRT suites. Every package
self-check validates the bundled executables, clean-user config, all engine
config migrations, frontend config, production catalogue and bootstrap without
opening an audio device.
