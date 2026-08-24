# AMY Synth Omnichord Design Documentation

This directory is the design contract for the AMY Synth Omnichord implementation.

This is the only active implementation contract. The repository's Sonic Pi
version is frozen legacy material: it is not maintained, tested or modified as
part of AMY development.

The documents define:

- architecture boundaries
- GUI behavior
- MIDI behavior
- AMY wire protocol usage
- preset ownership
- tuning rules
- testable use cases

Core rules:

- The Qt application produces AMY wire commands only.
- AMY transport may be local development or ESP32-P4 serial without changing behavior.
- OMNI and MIDI remain separate subsystems.
- Shared state is explicit; tuning is shared only when coupling is enabled.
- `rhythm_bahavior.md` is the authoritative rhythm transport/tempo contract.
- `testing.md` defines the maintained local suites and CI responsibilities;
  it also defines Linux release packaging and validation. Detailed executable
  scenarios live in `../qt_frontend/tests/USE_CASES.md`.
- `sound_balance.md` defines user storage/config overrides, strum modes, MIDI
  control indicators and the instrument-balance measurement contract.

When implementation and design differ, the difference must be documented before changing behavior.
