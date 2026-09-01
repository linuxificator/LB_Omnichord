# T09 result: versioned schema and immutable resolved configuration

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: configuration loading, migration and composition
Applicability: shipped/user config, all Python entrypoints and five packages

## Outcome

- Added an authoritative Draft 7 schema for configuration revision 1. It
  covers every shipped top-level section and rejects missing, unknown and
  wrongly typed operational values with JSON paths.
- Added cross-field validation for unique OMNI/MIDI synth and bus ownership,
  seven-note chord pools, bus capacity, sequencer tag range overlap/bounds,
  pattern tag/instance capacity and default synth references. Independent
  domain issues are aggregated into one startup error.
- Added frozen typed sections for serial transport, MIDI input, voice/runtime
  capacities, synth/bus/tag layout, debug policy and provenance.
- Provenance records the actual source and kind, shipped baseline, user paths
  that differ from it and platform-derived fields. `auto` MIDI profile is
  recorded as runtime-adapter owned; an explicit profile is recorded as an
  override.
- Kept legacy consumers stable through a fresh isolated compatibility
  dictionary. It includes the same derived 256-entry Juno/DX7 patch map and an
  optional revision-1 external patch extension. Mutating one view cannot mutate
  typed state or another view.
- The local AMY service now uses the same resolved loader and no longer repeats
  fallback bus/oscillator/pattern capacities.
- Added path-specific adversarial fixtures, aggregate invariant fixtures,
  immutability/provenance proof and a test that invalid config fails before a
  serial resource can open.
- Added the authoritative `configuration.md` contract and routed it from the
  design index.

## Dependency decision

Adopted exactly `fastjsonschema==2.22.2` after a dated assessment. It is a
Production/Stable, OS-independent, universal pure-Python wheel with a
2016-present history and current Python 3.10-3.14 support. It enters no audio,
MIDI or UI hot path; schema compilation/validation occurs once at startup.

The broader `jsonschema` alternative currently depends on native/Rust
`rpds-py`, for which this project's Python-for-Android packaging has no proof.
It was therefore not adopted solely for startup validation. The exact pure
Python pin is declared in the runtime group and generated Android target
requirements. Desktop groups inherit it from the runtime file.

Required/unknown members at the failing object and all Python domain issues are
reported together. Other JSON Schema constraint failures stop at the exact
first failing path, which is the validator's deterministic API; LB does not
reimplement a second schema walker merely to change collection order.

## Package proof

- AppImage self-test now requires the versioned schema.
- Android staging copies the typed loader and nested schema asset; a packaging
  test proves both paths.
- AppImage, macOS and Windows already collect the complete config directory;
  imported runtime dependencies are collected by their Python packagers.
- The full Android build/emulator and all five artifact gates remain required
  before a future merge to `main`; a universal wheel is not treated as product
  acceptance by itself.

## Verification

- resolved/config adversarial tests: 9 passed
- program/legacy loader tests: 5 passed
- dependency declaration tests: 3 passed
- Android packaging contracts: 10 passed
- local service/config entrypoint tests: passed
- T06 public loader/behavior characterization: passed
- complete unit suite: passed
- quality gate: passed; three new production modules pass strict mypy
- `git diff --check`

## Findings and progressive insight

- T07 changed the shipped MIDI profile to `auto` without increasing
  `config_revision`. A previously seeded user file can therefore remain at
  revision 1 with the old shipped `linux` value and continue forcing Linux.
  T10 must introduce revision 2 and explicitly migrate the former shipped
  default to `auto`; otherwise T07 is complete only for new installations.
- Existing migration writes directly and has no backup/recovery. T10 must run
  revision transforms before this validator and use the atomic store for the
  revision-2 write.
- CLI serial overrides are currently applied by mutating the compatibility
  dictionary after typed resolution. T11 should apply them as explicit
  composition inputs and record their provenance rather than adding mutable
  fields to the frozen config.
- The schema locator deliberately supports source, PyInstaller and Android's
  flat stage without an OS branch. T14 should replace these packaging-layout
  candidates with a supplied resolved runtime path, not copy the logic.
- Required `.get(..., fallback)` calls remain in legacy command consumers.
  T12 removes those only after T11 injects typed sections; removing them in T09
  would create a temporary construction path.
- Revision 1 accepts the transitional `synth_patches` object because external
  revision-1 files may contain it. The shipped file remains free of that
  duplicated map. T12 can remove this compatibility field only with explicit
  migration evidence.

## Follow-up task effects

No new queue item is added, but T10's first migration is now mandatory and
concrete: revision 1 `tech_profile: linux` to revision 2 `auto`, followed by
schema validation and an atomic recoverable write. T11 owns CLI provenance;
T12 owns compatibility/fallback removal; T14 owns injected schema/runtime
paths.
