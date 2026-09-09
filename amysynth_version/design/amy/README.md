# AMY integration notes

Status: authoritative category index for LB-facing AMY work
Owner: LB Omnichord AMY integration
Last verified: 2026-09-09

- `interface.md` owns the frontend/wire boundary.
- `sequencer.md` consolidates the current reusable-sequence implementation,
  compatibility and realtime publication model.
- `aux_returns.md` records generic shared effect routing and the P4-specific
  built-in-reverb resource limit.
- `shared_reverb_zero_level.md` records the disabled-return regression, its
  AMY-side correction and the native regression test.
- `maintenance.md` records independently discovered AMY defects and fixes.
- `../esp32/` owns target-specific performance, reverb and firmware evidence.

These documents belong only in LB Omnichord. Clean Shorepine-facing AMY
branches contain public AMY documentation but never Codex/LB handovers or
Omnichord-specific musical policy.
