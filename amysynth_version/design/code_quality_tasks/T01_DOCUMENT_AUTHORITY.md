# T01 result: documentation authority and contradictions

Status: complete
Completed: 2026-09-01
Task source: `../CODEX_HANDOVER_ORDERED_CODE_QUALITY_TASKS.md` T01

## Changes

- Added status, owner, applicability and verification metadata to every active
  routed design/runtime contract touched by the Codex reading route.
- Kept `midi.md` as the authority for MIDI input capability.
- Corrected `unclear.md`: ALSA raw and ALSA Sequencer are implemented; only a
  UI selector and non-Linux native adapters remain possible work.
- Corrected `INSTALL.md`: VMPK connects directly to `LB Omnichord / MIDI In`;
  `snd-virmidi` is optional raw-reader testing, not a requirement.
- Corrected the Windows status table so it no longer calls the Linux reader
  raw-only while still stating that WinMM is not implemented.
- Created this per-task result-handover index for T01-T25.

## Findings and decisions

- A document can be authoritative for behavior while a dated task handover is
  authoritative only for what that task changed. Both roles must remain
  explicit.
- Support-state prose should be owned by the subsystem contract and summarized
  elsewhere. T14 should expose a structured runtime capability model; a later
  documentation generator may consume that model, but T01 deliberately did
  not introduce generation infrastructure.
- The shipped `tech_profile: linux` statement in `midi.md` remains factually
  correct for the current code and is explicitly identified as a defect for
  T07. Changing the documentation before the implementation would create a new
  contradiction.

## New or refined follow-up

- T07 must update `midi.md` in the same commit that changes the shipped profile
  to automatic capability selection.
- T14 should make platform capabilities structured data so installation and
  status documentation can link to one source without duplicating code paths.
- T23 should enforce metadata on active routed contracts and local-link
  validity without asserting exact prose.

## Verification

- Markdown local-link check.
- `git diff --check`.
- Full frontend unit suite.
