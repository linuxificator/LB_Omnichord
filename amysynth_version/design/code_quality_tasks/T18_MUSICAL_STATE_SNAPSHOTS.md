# T18 result: immutable musical-state snapshots

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: tuning, chord identity/voicing and shared performance context

## Outcome

- Added pure frozen `TuningSnapshot`, `ChordSnapshot`,
  `PerformanceStateSnapshot` and `OmniPerformanceSnapshot` values.
- Moved reference/bend clamping, equal-temperament offset, table lookup,
  key-dependent intonation and note tuning into `musical_state.py`.
- Added one public `performance_snapshot()` boundary on the OMNI owner.
  `performance_backend` enriches it with chord gate, bass voicing, arpeggio
  state and current bass notes without changing the base facade contract.
- Replaced MIDI's direct access to OMNI active-row, root, chord catalogue,
  row-index and intonation-table private fields in chord/tuning calculation.
  Coupled tuning consumes the OMNI snapshot; uncoupled MIDI supplies its local
  mode/reference/bend while reusing the immutable table data.
- Retained the existing compatibility methods in `app_core`, now as adapters
  over the pure functions. Note generation, note ownership, synth IDs and
  release scheduling are unchanged.

## Compatibility and proof

- Pure tests cover 440-Hz identity, reference/bend bounds, fractional MIDI
  conversion, key-dependent HARM lookup, no-root unity, active/inactive chord
  identity and pitch classes.
- A boundary guard proves MIDI chord/tuning methods call the public snapshot
  and contain none of the former OMNI private-field accesses.
- Existing tuning, performance, MIDI engine, native chord and package suites
  retain the characterized outputs. The pure module passes strict mypy.
  Whole-project quality passes with 37/42 legacy mypy errors and 20 strict
  modules; the complete behavior runner passes.

## Findings and progressive insight

- Intonation tables are application resources and immutable after startup.
  Freezing them once avoids repeatedly copying 12×12 matrices during strums
  while making the cross-component contract safe to share.
- “Current chord” is identity and harmonic context, not sounding-note
  ownership. Publishing root/intervals/pitch classes does not authorize MIDI
  to stop or mutate OMNI voices.
- Coupled and uncoupled tuning share the same pure equation but deliberately
  supply different snapshot inputs. This removes duplication without hiding
  policy in a boolean-heavy universal controller.

## Follow-up task effects

T19 can use `PerformanceStateSnapshot` while extracting binding/takeover state,
but remaining MIDI-to-OMNI private mutations must move through explicit owner
commands rather than adding setters to the immutable snapshot. T21 will reduce
the facade after those commands exist.
