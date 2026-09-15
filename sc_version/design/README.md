# LB Omnichord SuperCollider design index

Status: authoritative documentation index
Owner: SuperCollider edition architecture
Applies to: `sc_version`
Last verified: 2026-09-15

This design tree describes only the active SuperCollider edition. Historical
AMY implementation notes remain available in Git history and in the separate
`amysynth_version` tree; they are not runtime or packaging authority here.

## Required reading

Before changing this edition, read:

1. [`../README.md`](../README.md)
2. [`arch/principles.md`](arch/principles.md)
3. [`arch/architecture.md`](arch/architecture.md)
4. [`arch/behavior.md`](arch/behavior.md)
5. [`arch/testing.md`](arch/testing.md)
6. [`sc/STATUS.md`](sc/STATUS.md)
7. the README for each affected category

Use [`sc/PLAYBACK_QUALIFICATION.md`](sc/PLAYBACK_QUALIFICATION.md) for sound,
sample or voice-lifetime work, [`sc/INSTRUMENT_BROWSER.md`](sc/INSTRUMENT_BROWSER.md)
for program selection and controls, [`sc/MUSIC_EXPANSION.md`](sc/MUSIC_EXPANSION.md)
for rhythm/bass work and [`sc/BUILD_AND_RELEASE.md`](sc/BUILD_AND_RELEASE.md)
for package changes. `../../CODEX_HANDOFF.md` records operational state but
does not override these contracts.

## Categories

- [`arch/`](arch/README.md): ownership, configuration, tests and quality.
- [`gui/`](gui/README.md): Qt interaction and rendering.
- [`controls/`](controls/README.md): MIDI/OSC input and learning.
- [`music/`](music/README.md): routes to current musical contracts and data.
- [`platform/`](platform/README.md): supported packages and native boundaries.
- [`sc/`](sc/STATUS.md): engine implementation, evidence and release state.

Executable tests and validated machine-readable data outrank stale prose. A
superseded design is removed from the branch tip; Git keeps the audit trail.
