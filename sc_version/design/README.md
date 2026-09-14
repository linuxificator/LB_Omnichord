# LB Omnichord SuperCollider design index

Status: authoritative documentation index

Owner: SuperCollider edition architecture

Applies to: `sc_version`
Last verified: 2026-09-14

This tree began as a behavior-preserving copy of the AMY design tree. The
contracts remain authoritative for UI, music, external controls, configuration
quality and tests. Where an AMY transport or engine detail conflicts with the
SuperCollider design, the documents in [`sc/`](sc/) and executable SC tests
supersede it for this edition only. The AMY implementation remains unchanged
and independently releasable.

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
- [`sc/`](sc/): migration requirements, decisions, implementation evidence and
  current completion status.

## Required reading

For every SuperCollider edition task, first read:

1. [`../README.md`](../README.md)
2. [`arch/principles.md`](arch/principles.md)
3. [`arch/architecture.md`](arch/architecture.md)
4. [`arch/behavior.md`](arch/behavior.md)
5. [`arch/testing.md`](arch/testing.md)
6. [`sc/CODEX_HANDOVER_SUPERCOLLIDER_MIGRATION.md`](sc/CODEX_HANDOVER_SUPERCOLLIDER_MIGRATION.md)
7. [`sc/STATUS.md`](sc/STATUS.md)
8. [`sc/PLAYBACK_QUALIFICATION.md`](sc/PLAYBACK_QUALIFICATION.md) when changing
   instruments, samples, drums, gain staging or voice lifetimes

Then read the category README and owning contracts for every subsystem being
changed. If `../../CODEX_HANDOFF.md` exists, read it for operational state; it
never overrides these contracts or the user's current request.

## Conflict resolution

When prose and implementation disagree, use this order:

1. current executable tests and machine-readable configuration;
2. authoritative subsystem contract;
3. current consolidated analysis;
4. historical Git content.

Document the discrepancy before changing behavior. SC release pins and
resource limits come from
`../qt_frontend/packaging/supercollider_release_inputs.json`,
`../supercollider/source-lock.json`, and
`../qt_frontend/config/supercollider.json`; copied AMY release metadata is not
an authority for the SC package.
