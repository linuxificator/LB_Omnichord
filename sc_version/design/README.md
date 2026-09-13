# LB Omnichord design index

Status: authoritative documentation index
Owner: application architecture
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-08

This tree describes the current implementation. Historical experiments and
superseded decisions remain available in Git history; they are deliberately
not retained as competing active documents.

The Sonic Pi implementation is frozen historical material. New behavior,
tests and documentation belong to `amysynth_version`.

## Categories

- [`arch/`](arch/README.md): architecture, configuration, testing, quality,
  dependencies and open work.
- [`amy/`](amy/README.md): AMY wire boundary, reusable sequences and upstream
  maintenance findings.
- [`esp32/`](esp32/README.md): ESP32-P4 firmware, realtime performance,
  reverb and release evidence.
- [`gui/`](gui/README.md): Qt/QML layout, interaction and rendering contracts.
- [`controls/`](controls/README.md): MIDI, OSC and external-control learning.
- [`music/`](music/README.md): presets, rhythm, sequences, balance and tuning.
- [`platform/`](platform/README.md): desktop/mobile packaging and Raspberry Pi.
- [`quality_todo/`](quality_todo/README.md): bounded, evidence-backed quality
  work that has been identified but is not yet an active implementation.

## Required reading

For every active AMY task, first read:

1. [`../README.md`](../README.md)
2. [`arch/principles.md`](arch/principles.md)
3. [`arch/architecture.md`](arch/architecture.md)
4. [`arch/behavior.md`](arch/behavior.md)
5. [`arch/testing.md`](arch/testing.md)

Then read the category README and owning contracts for every subsystem being
changed. If `../../CODEX_HANDOFF.md` exists, read it for operational state; it
never overrides these contracts or the user's current request.

## Conflict resolution

When prose and implementation disagree, use this order:

1. current executable tests and machine-readable configuration;
2. authoritative subsystem contract;
3. current consolidated analysis;
4. historical Git content.

Document the discrepancy before changing behavior. Release pins and resource
limits must be read from
`../qt_frontend/packaging/release_inputs.json`, frontend configuration and the
ESP32-P4 Kconfig/build metadata rather than copied from old release notes.
