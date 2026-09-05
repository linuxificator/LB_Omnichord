# Codex handover: cumulative reusable AMY sequences

Status: implemented and tested on `rework/sequencer_simplification`
Date: 2026-09-04
Repositories: `linuxificator/amy` and `linuxificator/LB_Omnichord`

## Why this supersedes the previous design

The original `rework/sequencer` experiment introduced sequencer groups as a
second abstraction beside AMY's root sequencer. Discussion on shorepine/amy
PR 1151 showed that the public model could be smaller. Dan Ellis additionally
stated that backwards compatibility with “repeating a tag overwrites its
previous content” was not desirable: for harmony with repeated `synth=`
configuration, repeated tagged events should cumulate by default.

That decision is now the contract. Do not restore replacement-on-repeat, the
`HA` append operation, a fourth ticks field, group publication, public revision
numbers or execution IDs. Historical handovers may describe those experiments;
this document and `sequencer_sequences.md` supersede them.

## AMY public model

- Untagged `ticks=(tick,)` and `ticks=(tick, period)` keep direct scheduling on
  the global clock.
- `ticks=(tick, period, tag)` appends a normal AMY event to the stopped,
  reusable sequence at `tag`. Repeating the tag cumulates events.
- `sequence_reset=tag` / `HR<tag>Z` resets the future definition.
- `sequence_control` / `HC` starts, stops, aligns or temporarily gates a tag.
- A definition containing only period-zero events is finite. A nonzero period
  makes an execution repeat until stopped.
- A sequence may control another sequence. Cyclic graphs cannot exceed the
  bounded execution pool; LB authors only one parent/child level.
- Multiple finite executions of one tag may overlap.
- An active execution retains a reference-counted copy-on-write snapshot.
  Resetting/rebuilding future contents cannot delete its pending note-offs or
  change any other scheduled payload.
- Stop targets all active executions of the public tag and cancels their future
  dispatch. It does not infer or synthesize inverse events for arbitrary
  payloads. A parent stop can leave already-started finite child executions
  alive so the note-offs stored in those children still run; an explicit stop
  of a leaf execution also cancels its pending note-off.
- Gating suppresses ordinary events while phase advances. Control events keep
  running so a finite controller can restore state.

The Python helper `define_sequence(tag, events)` validates the complete input,
sends one reset, then sends ordinary tagged ticks messages. AMY documentation
is Python-first; exact wire equivalents remain documented because LB's
multi-platform process boundary uses sockets, a Windows named pipe, Android
service IPC and ESP32 serial.

Python exposes the full operation with explicit named actions:
`amy.send(sequence=tag, action='start'|'stop'|'gate', ...)`. Gate requires a
duration. Low-level `HC` uses the strict integer action values `1`, `0`, and
`2`. This avoids both a misleading partial boolean and overloaded note
velocity, and rejects fractional control values. See
`CODEX_HANDOVER_SEQUENCE_API_REVIEW_COMPLETION.md` for the decision trail.

## AMY branches and diagnostic commits

Clean upstream-directed worktree:
`/home/jeroen/omnichord/amyfork/amy-sequencer`

Branch:
`rework/sequencer_simplification`

Relevant commits:

- `29aa50a8 Make sequencer tags cumulative sequences`
- `06309fa9 Document cumulative sequencer tags`
- `21395160 Align sequence test terminology`
- `fca15795 Remove retired sequence append from Godot`
- `2669c3ae Cover concurrent sequence definition generations`
- `b2a88659 Move sequence version reclamation off render path`
- `7c98ad2b Reclaim sequence versions at control boundary`
- `b6f559a5 Defer render-fired sequence reset cleanup`
- `0198b50e Make sequence triggers note-like and strict`
- `361ac404 Migrate first-party sequencer callers`
- `3060cc0b Test sequence publication allocation failures`
- `f22307a3 Cover concurrent sequence publication retry`
- `dcbd2842 Define bounded sequence composition semantics`
- `092941ca Accept note-like sequence control velocity`
- `33f4c01c Preserve existing config member offsets`
- `ab5f3020 Document and test sequence API migration`
- `36aa150e Simplify stored sequence slots`
- `380f20e1 Ignore generated sequence test binaries`
- `4aab0fcb Use explicit run state for sequence control`
- `cc2407ff Document boolean sequence run control`
- `841ccd29 Expose named sequence control actions`
- `f03875f2 Document start stop and gate actions`

No Codex documents, Omnichord policy or downstream release configuration may
be committed on that branch.

LB integration release:

- branch `releases/amy_omnichord_R20260904T215233`;
- exact commit `8a896e9319957ed8eea49f26fe16378fcc2a27c5`;
- generic cumulative-sequence commits are cherry-picked above the existing
  Omnichord release profile;
- release-only sizing remains 11 buses, 336 oscillators, 1280 public sequence
  tags, 64 events per definition and 40 executions;
- Gamma9001 and maintained socket/Android/offline-render support remain;
- the abandoned bus-mixer experiment remains absent.

The active-definition COW path now pins its source briefly, performs all
allocation and copying after releasing the AMY queue lock, and publishes with
a checked short pointer swap. Render-side last releases link definitions onto
an intrusive retire list; the public control/wire boundary owns destruction.
This supports more than two simultaneously retained versions without a fixed
buffer pool or tracing collector. See
`CODEX_HANDOVER_REALTIME_SEQUENCE_PUBLICATION.md` for the exact migration and
the still-open physical ESP32 timing proof.

## LB implementation

LB stays a wire-only client. It does not import AMY outside the separately
managed local service and does not maintain AMY sequence, note or timing state.

Each root musical lane now uses one stable tag:

- fill launch: 0;
- bass: 56;
- automatic chords: 112.

A replacement emits stop-at-alignment, reset, cumulative ordinary tagged
events and start-at-the-same-alignment. Empty output emits immediate stop/reset
without restart. The lane's alignment is the least common multiple of its
event periods. This preserves AMY's running musical phase without querying or
mirroring its clock.

The old host `high_water` state and one-tag-per-root-event clearing algorithm
were removed. Stored fills, chord one-shots and base drum role loops retain
stable tags in the disjoint 256..1279 area. Child sequences own complete
note-on/off pairs, so rate/chord edits and manual-hold takeover need no caller
note bookkeeping or delayed cleanup.

Diagnostic LB commit:

- `1d1165d Adopt cumulative AMY sequence tags`

The immutable AMY release pin is stored once in
`qt_frontend/packaging/release_inputs.json` and repeated only in human release
documentation/provenance where required.

## Tests already run

AMY feature and release worktrees:

- `make ctest -j2`;
- `python3 tests/test_sequence_api.py`;
- `make check-c-api`.

LB targeted tests:

- `tests/test_command_plans.py`;
- `tests/test_sequencer_tags.py`;
- `tests/test_drum_patterns.py`;
- `tests/test_program_architecture.py`;
- integration `test_serial.py`;
- integration `test_native_rhythm.py`;
- integration `test_presets.py`.

The architecture regression explicitly forbids host sequence clock/execution
state, authoring high-water state and reintroduction of an `HA` wire adapter.
Before merging, rerun `tests/run_tests.py --suite all` and the quality suite.

That complete LB suite was rerun after pinning the final release and passed.
The detailed API-feedback, compatibility, analyzer and sanitizer evidence is
in `CODEX_HANDOVER_SEQUENCE_API_REVIEW_COMPLETION.md`.

## Lessons and future constraints

1. Compatibility claims must distinguish untagged scheduling from tagged
   scheduling. Untagged behavior is preserved; repeating a supplied tag is an
   intentional API behavior change.
2. A reusable definition and a running execution are separate internal
   lifetimes, but do not need separate public abstractions.
3. Event ownership is payload-agnostic. Note-offs, synth parameters and
   sequence controls all remain part of the execution snapshot.
4. Generic AMY behavior must not encode Omnichord policy. AMY exposes storage,
   execution and gating; LB chooses instruments, roles, fill continuation and
   replacement boundaries.
5. Tests and docs must use exact current wire syntax. Old `zQ`/group and `HA`
   examples are historical only.
6. Never add Codex traces to an upstream-directed AMY branch. Put all handover
   material in LB Omnichord.
7. Copy-on-write publication is semantically correct but its current clone and
   release paths are not yet suitable evidence of bounded real-time behavior.
   See `CODEX_HANDOVER_REALTIME_SEQUENCE_PUBLICATION.md` before changing that
   implementation.
