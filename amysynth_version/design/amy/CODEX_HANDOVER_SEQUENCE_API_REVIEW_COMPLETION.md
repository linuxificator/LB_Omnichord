# Codex handover: sequence API review completion

Status: implemented, pinned and host-tested; not yet substituted into PR 1151
Date: 2026-09-04
AMY feature branch: `rework/sequencer_simplification`
AMY feature head: `f03875f239d85f44d7d3d4115e0b51bf6482318d`
LB branch: `rework/sequencer_simplification`

## Review input and resulting API

Dan Ellis' review comment on Shorepine AMY PR 1151 values a broad feature set
with few parameters and asks whether starting a stored sequence can look more
like sending a note-on. A first implementation overloaded `vel`, but subsequent
review exposed a semantic mismatch: velocity describes how strongly a note is
played, while sequence control has three distinct operations. A short-lived
boolean `run` API still hid the gate operation. The final API remains small and
exposes all operations without another public group, revision or execution
abstraction:

```python
amy.send(sequence=100, action='start', alignment_period=48)
amy.send(sequence=100, action='stop', alignment_period=48)
amy.send(sequence=100, action='gate', duration=24, alignment_period=1)
```

The named action is Python convenience syntax; it normalizes to the existing
low-level `sequence_control` field. A caller may still schedule that control as
an ordinary event by also supplying `ticks`. The raw wire equivalents are:

```text
HC100,1,48Z
HC100,0,48Z
HC100,2,24,1Z
```

The raw second field is strictly integer `1` for start, `0` for stop, or `2`
for gate. Gate additionally takes duration plus alignment. Fractional values
and note-velocity templates are rejected rather than being silently
interpreted as an action.

The comment used `-1` in an illustrative `ticks` period. This branch does not
add another sentinel because AMY already has a complete finite/repeating rule:
a stored definition with only period-zero events is finite, while any nonzero
periodic event repeats. Adding `-1` would duplicate that lifetime model and
complicate unsigned wire validation. `alignment_period=1` supplies the
next-tick/as-soon-as-possible behavior for a direct trigger.

Python documentation is primary. Wire commands remain fully documented as a
secondary interface because LB Omnichord deliberately uses them as its stable
cross-process boundary over Unix sockets, Windows named pipes, Android private
IPC and ESP32 serial. JavaScript and Godot callers retain the generated raw
`sequence_control` binding; the named `sequence=..., action=...` convenience
is Python-specific.

Source discussion:
<https://github.com/shorepine/amy/pull/1151#issuecomment-5544095824>

## Generic behavior decisions

- Repeating a tagged `ticks` definition cumulatively appends. This is an
  intentional breaking change, not a compatibility claim.
- Tagged definitions are stopped until explicitly started. Untagged one- and
  two-field scheduling keeps its original behavior.
- A start creates a bounded execution which owns an immutable definition
  snapshot. Finite executions of one tag may overlap.
- Stop and finite gate commands capture only executions active when the
  command is received. An execution started after a future-aligned command is
  not silently controlled by old per-tag state.
- A sequence can contain any AMY event, including parameter changes and
  sequence controls. Stop therefore cancels future dispatch but does not try to
  invent inverse operations.
- Cyclic control graphs consume the bounded execution pool and recover; AMY
  does not recurse through C call frames.
- AMY contains no percussion, arpeggio, fill, Omnichord or instrument-role
  policy. Callers choose their own event contents and composition depth.

## Diagnostic AMY commits after the realtime-publication baseline

- `0198b50e` — initial note-like Python trigger experiment and strict Python/C
  control shapes (its `vel` syntax is superseded below);
- `361ac404` — migrate AMY's own examples, audio tests and sampler experiments;
- `3060cc0b` — allocation-failure injection for immutable publication;
- `f22307a3` — deterministic two-writer compare/retry coverage;
- `dcbd2842` — bounded cycles and current-execution aligned stop/gate rules;
- `092941ca` — test normalized fractional trigger velocity while rejecting
  malformed/overflowing raw fields (the fractional behavior is superseded);
- `33f4c01c` — append new `amy_config_t` members so existing member offsets do
  not move, plus the source-rebuild migration note;
- `ab5f3020` — executable JavaScript serialization coverage and expanded
  compatibility documentation;
- `36aa150e` — replace the one-field stored-slot wrapper with direct pointers;
- `380f20e1` — ignore the three generated sequence-test executables;
- `4aab0fcb` — replace overloaded trigger velocity with boolean `run` and
  reject fractional wire actions;
- `cc2407ff` — update public documentation and examples to the boolean model.
- `841ccd29` — replace the partial boolean API with named start, stop and gate
  actions, including strict duration validation;
- `f03875f2` — document the complete named-action model.

The final feature diff against Shorepine base `0fb0a00b` is 35 files,
2,415 insertions and 167 deletions. The main C addition remains the immutable
stored-definition/execution implementation; the public model is smaller than
the superseded group design even though robust ownership, validation and
concurrency tests cost real lines.

## Compatibility evidence

AMY's own tagged examples, the three tagged audio tests and sampler experiments
have been migrated. The previous behavior made a tagged event immediately
active and replaced an existing tag; the new behavior defines a stopped,
cumulative reusable sequence and starts it explicitly.

Shorepine Tulip has one central meaningful dependency on the old semantics:
`AMYSequenceEvent.update()` reuses stable tags for replacement and `remove()`
uses empty tagged cancellation. Its drum-machine consumers inherit that
behavior. A coordinated Tulip migration must reset/append/start explicitly and
make its live-update phase choice explicit. This is bounded to the wrapper and
its consumers, but it is not zero impact. No external Tulip repository was
modified in this work.

A disposable clone was used to prototype the migration. The central wrapper
needs 11 added and 2 removed lines: `update()` sends aligned stop, reset,
ordinary tagged definition and aligned start; `remove()` sends next-tick stop
and reset. A fake-boundary unit test covers add/update/remove and passes. The
prototype keeps no AMY clock, execution or note state, and repeated updates
before the boundary remain safe because each later stop captures the earlier
pending execution.

There is one real product choice for Tulip's owners. Aligning replacement to
the sequence period preserves the global rhythmic phase without querying the
clock, but a newly added or edited pad becomes effective at the next full
sequence boundary. The old active root event could take effect at its next
position inside the current cycle. Preserving that exact mid-cycle latency
would require either caller clock/phase bookkeeping or another generic AMY
phase-start facility. The prototype deliberately chooses the simple
next-boundary behavior; it is evidence for review, not a committed Tulip
policy decision.

The two added `amy_config_t` fields still require callers to rebuild against
the new header. Placing them at the end preserves offsets of older fields and
reduces accidental ABI damage; it does not promise binary compatibility for a
public C struct whose size changed.

## Verification completed

Feature and release validation completed sequentially where targets regenerate
`src/patches.h`:

- complete `make ctest`;
- `python3 tests/test_sequence_api.py`;
- `make check-c-api`, including executable Node/JavaScript checks;
- Godot source parsing with `gdparse`;
- GCC `-fanalyzer` on `src/sequencer.c`;
- ThreadSanitizer on the two-writer sequence publication test with the unrelated
  Linux MIDI backend excluded;
- LB quality, unit, portable-input, Linux-input, frontend, serial, presets,
  native-controls and native-rhythm suites through `run_tests.py --suite all`.

The three migrated AMY audio tests all render non-silent output. Two match at
-100.0 dB; `TestSequencer` differs from the host reference by -99.7 dB, a
0.3 dB-at-the-noise-floor reference discrepancy rather than silence or a
sequence-timing failure.

An initial whole-program ThreadSanitizer run reported a pre-existing shutdown
race in `src/linux_midi.c` between `run_midi_linux()` and `stop_midi()` on
`midi_linux_should_exit`. Rebuilding the same targeted test without the Linux
MIDI device layer produced a clean sequence-concurrency run. Treat the MIDI
race as separate AMY maintenance; do not widen this sequence change to fix it.

Do not run `make ctest` and `make check-c-api` concurrently in one checkout.
Both may regenerate or inspect `src/patches.h`, producing a test-runner race
which is not a product defect.

## Immutable LB integration release

The new fork release is:

- branch `releases/amy_omnichord_R20260904T215233`;
- commit `8a896e9319957ed8eea49f26fe16378fcc2a27c5`;
- PCM bank `gamma9001`;
- 11 buses, 336 oscillators, 1280 stored tags, 64 events per definition and 40
  active/alignment-pending executions;
- existing socket, Android/Oboe and deterministic offline-render support;
- no abandoned bus-mixer experiment and no Codex files.

The release passed the same AMY C, Python and generated-binding checks. LB's
single release manifest now pins it for Linux, Raspberry Pi, macOS, Windows and
Android. ESP32-P4 remains a separately validated hardware task.

## Remaining work

1. Physically measure ESP32-P4 render deadlines, publication critical-section
   time, heap low-water, largest block and retire-list depth at the established
   48 kHz / 128-sample / 2x64-DMA baseline and under maximum expected effects.
2. Let Shorepine choose the Tulip live-edit phase policy, then turn the tested
   disposable wrapper prototype into a coordinated Tulip change before
   claiming a Shorepine-wide transition is complete.
3. Add a Godot runtime behavior test when a Godot executable is available;
   generated source freshness and parser syntax currently pass, and behavior
   remains in the common C core.
4. Consider the older anonymous repeating-event allocation/copy under the AMY
   lock as a separate optimization. It predates reusable sequences and does not
   belong in this PR without scope agreement.
5. Pack snapshot allocation only if ESP32 measurements demonstrate worthwhile
   fragmentation or latency improvement. The current intrusive deferred
   reclamation already removes clone/free work from the render path.
6. Replace PR 1151 only after deciding how to preserve its discussion history;
   its current head is still the superseded `rework/sequencer` branch. Do not
   force-rewrite that branch merely to make GitHub show the new implementation.
