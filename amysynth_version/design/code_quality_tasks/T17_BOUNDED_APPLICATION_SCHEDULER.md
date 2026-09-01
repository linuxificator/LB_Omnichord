# T17 result: bounded application scheduling

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: delayed note releases and host tail callbacks

## Outcome

- Classified timing ownership: AMY patterns retain beat-accurate rhythm and
  arpeggio timing; QObject presentation continues to use `QTimer`; writer
  delays remain ordered reset/allocation guards; only host release/tail work
  uses the new `MonotonicScheduler`.
- Replaced every product `threading.Timer` with one bounded heap and one worker
  shared by the native AMY client and MIDI engine.
- Preserved independent delayed note-off callbacks and their synth-generation
  cancellation. OMNI strum and per-row MIDI preview tails use explicit replace
  keys, so renewed activity extends one tail without accumulating stale work.
- Added capacity rejection, idempotent close/cancel, callback-failure health,
  pending/high-water and replacement diagnostics. Closing the AMY client first
  cancels callbacks, then closes the command writer.
- `MidiAmyEngine` accepts the client's scheduler in production and owns a
  fallback only when used independently; `MidiPlayerBackend.close()` closes an
  owned fallback.

## Compatibility and proof

- Tests prove deadline ordering on one worker, keyed replacement, finite
  capacity, close cancellation, continued execution after callback failure and
  immutable health reporting.
- A generation test invokes delayed AMY releases deterministically and proves
  that an old synth generation emits no note-off while the current generation
  emits the exact existing wire command.
- MIDI preview tests retain voice-limit release order and prove all five tail
  updates use the same row replacement key.
- A source guard rejects `threading.Timer` in both product owners. The new
  scheduler passes strict mypy. Whole-project quality passes with 37/42 legacy
  mypy errors and 19 strict modules; the complete behavior runner passes.

## Findings and progressive insight

- Moving these releases to AMY absolute-time wire fields would require a
  trustworthy shared host/engine clock that this transport contract does not
  expose. A bounded monotonic host scheduler is therefore the smallest safe
  change; rhythm timing already stays in AMY where that clock is native.
- Replacement keys are semantic cancellation, not merely optimization. A
  strum or preview tail represents inactivity since the latest onset, whereas
  one-shot note-offs remain independent events.
- Callback exceptions must not kill the only scheduler worker. They remain
  visible through failure count and last-error health while later releases
  continue.

## Follow-up task effects

T18 can treat note lifetime and scheduler ownership as explicit dependencies
of immutable performance snapshots. No additional task was discovered.
