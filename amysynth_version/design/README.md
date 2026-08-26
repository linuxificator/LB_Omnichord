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
- `midi_control.md` is the authoritative MIDI CC learn, binding, LRU/LED and
  preset-persistence contract.

## Required reading route for Codex

`AGENTS.md` requires Codex to use this route at the start of every active-AMY
session. Read selected files in full rather than relying on search excerpts.

Always read these baseline contracts:

- `../README.md` — active implementation, runtime and package overview;
- `principles.md` — product and engineering priorities;
- `architecture.md` — process, transport, synth and bus ownership;
- `behavior.md` — shared application behavior;
- `testing.md` — maintained suites, CI and verification rules.

Then add every row that matches the task:

| Task area | Additional required reading |
| --- | --- |
| Qt/QML layout, interaction or screen behavior | `gui.md`, `ui_behavior_reference.md`, `../qt_frontend/docs/CONTROL_SAFETY.md` |
| MIDI input, MIDI screen or CC learn | `midi.md`, `midi_control.md`, `presets.md`, `sound_balance.md`, `../qt_frontend/tests/USE_CASES.md` |
| Presets, user state or migration | `presets.md`, `sound_balance.md`, `../qt_frontend/tests/USE_CASES.md` |
| Rhythm, tempo or sequencer behavior | `rhythm_bahavior.md`, `../qt_frontend/docs/SEQUENCER_TAGS.md`, `../qt_frontend/tests/USE_CASES.md` |
| Tuning, pitch or note conversion | `tuning.md`, `use_cases.md`, `../qt_frontend/tests/USE_CASES.md` |
| AMY commands, sockets, serial or buses | `amy_interface.md`, `../qt_frontend/docs/CONTROL_SAFETY.md` |
| Instrument catalogue, defaults or balance | `sound_balance.md`, `presets.md`, `../qt_frontend/instruments/README_defaults.md` |
| Desktop packages, releases or native Windows | `../qt_frontend/README.md`, `../qt_frontend/INSTALL.md`, `../qt_frontend/docs/WINDOWS_NATIVE.md`, `../../.github/workflows/desktop-release.yml` |
| Optional historical WSL experiment | `../qt_frontend/docs/WSL_APPIMAGE_TESTING.md`, plus the desktop documents above |
| ESP32-P4 firmware or packaging | `../esp32p4/README.md`, `../esp32p4/CI_FLASH.md` |
| Known unresolved behavior | `unclear.md` plus the owning subsystem documents above |

When a selected document points to a more specific behavioral contract, read
that contract too. Historical files under `qt_frontend/docs/history/` and the
Sonic Pi tree are not startup reading unless the user explicitly asks for
historical comparison.

When implementation and design differ, the difference must be documented before changing behavior.
