# Reusable-sequence ownership

Status: authoritative rhythm/sequencer architecture contract
Owner: rhythm command planning and AMY transport integration
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-04

## Boundary

LB Omnichord owns musical policy: rhythm and fill selection, drum-role
meaning, fill continuation, chord and arpeggio construction, bass choice and
the boundary at which future launches must change.

AMY owns generic execution: cumulative tagged definitions, local phase,
finite or repeating lifetime, aligned start/stop, temporary event gating and
the immutable definition snapshot retained by a running execution.

The frontend expresses everything as AMY wire commands. It must not import
AMY, call its Python or C API, poll sequencer position, mirror AMY's clock, or
use host timers for fill completion, arpeggio release, sequence repeats or
gate expiry. Linux/macOS sockets, a Windows named pipe, the Android service and
ESP32 serial are transport adapters behind the same wire boundary.

## Public command model

An ordinary `H<tick>,<period>,<tag><payload>Z` appends an event to a stopped
reusable definition. Repeating the tag cumulates. `HR<tag>Z` resets the future
definition. `HC<tag>,<velocity>,<alignment>Z` starts for velocity `(0,1]` and
stops for velocity `0`; `HC<tag>,2,<duration>,<alignment>Z` applies a finite
gate. Untagged `H` messages keep their direct global-clock behavior.

There is no separate group namespace, append command, publication revision,
length declaration or execution identifier. A finite sequence may start a
child sequence, which is sufficient for fills and arpeggios. LB deliberately
uses at most one parent/child level and never authors recursive control graphs.

## Persistent definitions and runtime state

Each fill is defined once during `AmySerialClient` construction. Rhythm Start
resets the timebase and active executions while retaining the catalogue.
Activity changes may replace base-role sequences. Arpeggio, chord or pitch
changes reset and rebuild a future definition behind a stable tag.

An execution already running in AMY retains its original copy-on-write
snapshot. LB therefore keeps no execution generation, phrase end time,
sequence phase, pending release, note-state mirror or authoring high-water
mark. Removing a fill or chord trigger changes future launches only; AMY owns
the releases in children that already started.

## Capacity and identity

LB uses one identity domain: deterministic public AMY sequence tags. The
hosted profile reserves 1280 tags, 64 events per definition and 40 active or
alignment-pending executions. Definitions allocate lazily, so reserving room
for a large fill catalogue does not make inactive sequences part of each tick
scan. Stored capacity and execution capacity remain independent.

## Regression requirements

Tests must keep proving that:

- repeating ordinary tagged `H` commands cumulates definition events;
- an explicit reset replaces only the future definition;
- all fills are preloaded once and Start does not resend them;
- live fill selection changes future launches only;
- fill gates suppress event dispatch without killing ringing audio or moving phase;
- arpeggio rate, direction, pitch and chord edits retain stable tag identity;
- every running one-shot retains its original releases after a definition edit;
- rhythm planning contains no host phrase timers, clock queries or execution state;
- frontend planner and transport code import no AMY runtime API;
- tag, event and simultaneous-execution bounds cover the full catalogues;
- explicit transport Stop still releases rhythm-owned voices because it
  prevents future sequenced note-offs.

AMY native tests own execution snapshots, local phase, finite/repeating
lifetime, aligned activation, gating, reset behavior, capacity failure and
unchanged untagged scheduling. LB tests own the emitted wire stream and musical
policy on its side of the boundary.
