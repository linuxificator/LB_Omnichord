# Codex handover — Gamma9001-first drum fill refresh

Status: **integrated, corrected and covered by source-backed executable contracts**

Repository: `linuxificator/LB_Omnichord`

Current integration branch: `feature/midi_osc_improvement`

Active implementation: `amysynth_version` only. Sonic Pi remains frozen.

## Intent

The 270 fills are matched to the richer Gamma9001-first activity grooves while preserving the existing five-F-button product behavior and wire-only AMY boundary.

## Final authority

Read `CODEX_HANDOVER_DRUM_CATALOGUE_MUSICAL_AUDIT.md` for the complete final state. It records:

- the review of all 54 rhythms and all 270 fills against musical sources;
- every allowed fill start;
- the measured before/after velocity balance;
- the correction of 113 conflicting duration metadata records;
- the requirement for five distinct rhythmic and orchestration contours per rhythm;
- the live enable/disable/density response contract;
- permanent regression coverage and validation commands.

This short document only retains the architectural constraints of the original refresh.

## Architecture constraints

- `drum_activity_timing.json` is the authority for repeating groove timing.
- `drum_fills_timing.json` contains only kit-independent tick, logical-role and velocity data.
- Concrete sounds remain in the kit-specific realization files.
- Gamma9001 is the musical quality reference.
- Tiny is a compatibility/test degradation path and never constrains authoring.
- F1–F5 use distinct logical orchestrations and distinct Gamma9001 fill profiles.
- Fill selection, phrase placement and continuation policy belong to LB Omnichord.
- AMY only provides generic sequencer-group storage, playback and gating.
- Do not use host timers as a musical clock and do not reset sequencer phase for a fill.

## Final behavior

- Every rhythm has exactly five fills.
- Every fill ends at the next written bar boundary.
- Fill order supplies variation; obsolete within-fill start rotation is gone.
- Every F1–F5 set has five distinct duration/onset contours.
- A proportional velocity trim preserves internal dynamics without near-maximum default loudness.
- A running child fill finishes when fills are disabled, while the root scheduler is replaced by the next bar and cannot launch a later stale fill.
- Enabling or changing density establishes the next bar as the new schedule origin.

## Do not regress

Do not re-author around Tiny limitations. Do not reintroduce mid-bar rotating starts, contradictory duration metadata or identical within-rhythm onset contours. Do not add autonomous fills to activity level 5. Do not move musical policy into AMY.
