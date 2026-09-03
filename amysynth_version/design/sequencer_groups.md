# Sequencer-group ownership

Status: authoritative rhythm/sequencer architecture contract
Owner: rhythm command planning and AMY transport integration
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-03

## Boundary

LB Omnichord owns musical policy: rhythm and fill selection, drum-role
meaning, fill continuation, chord and arpeggio construction, bass choice and
the point at which future launches must change.

AMY owns generic sequencer execution: persistent group definitions, local
phase, repeat count, quantized control, finite event gating and the immutable
definition revision retained by a running execution.

The frontend expresses all of this as AMY wire commands. It must not import
AMY, call its Python or C API, poll the sequencer position, mirror AMY's clock,
or use host timers for fill completion, arpeggio note release, group repeats
or gate expiry. The local Python AMY process, native Windows service, Android
service and ESP32 serial endpoint are transport/service adapters behind the
same wire boundary.

## Persistent definitions and runtime state

Each fill is authored once during `AmySerialClient` construction. Transport
Start may reset timebase, root events and active executions, but it must not
reauthor the fill catalogue. Activity changes may replace base-role group
definitions. Arpeggio, chord or pitch changes may atomically publish a new
revision under a stable group tag. These are future-definition updates, not a
host-owned execution lifecycle.

An execution already running in AMY keeps its original revision. LB therefore
does not keep execution generations, calculate phrase end times or schedule
delayed cleanup. Removing a fill or automatic-chord root trigger changes only
future launches. AMY remains responsible for the releases stored in a running
one-shot.

The high-water mark retained for each group is definition-authoring state
only. It exists so a later shorter revision clears every stale local event tag,
including after a superseded asynchronous write. It is not an active-execution
identifier or revision owner.

## Command model

Grouped definitions reuse ordinary ticks syntax with a fourth group field:

```text
H<local-tick>,<period>,<local-event-tag>,<group-tag><payload>Z
```

`zQ<group>,<action>,<value>,<quantize>[,<execution-tag>]Z` is the single
generic control family used to publish, start, stop and gate groups. Root `H`
events may contain a one-shot group start. A group definition contains only
leaf AMY events or finite gate controls; LB never constructs recursive group
starts.

AMY definitions are persistent across `RESET_SEQUENCER`; root events and
active executions are not. Explicit transport Start therefore sends the reset,
waits only for its audio-block application boundary, installs current runtime
groups/root schedules and sends `zY1` last. The reset ordering delay is a
device-state guard, not musical timing.

## Capacity and identity

LB uses only two normal musical identity domains:

- deterministic persistent group tags;
- deterministic root sequencer event tags.

An execution tag is supplied only where AMY needs a stable target for a
looping base-role execution. It does not encode a definition generation.

The hosted integration profile reserves 1024 groups, 64 local tags per group
and 40 active/pending executions. Stored capacity and execution capacity are
separate. CI audits the full catalogues and every supported chord overlap so
new data fails explicitly before exceeding these bounds.

## Regression requirements

Tests must keep proving that:

- all fills are preloaded once and Start does not resend them;
- live fill selection changes only future root launches;
- fill gates suppress event dispatch without killing ringing audio or moving
  phase;
- arpeggio rate, direction, pitch and chord edits keep stable group identity;
- every running one-shot retains its original releases after a new revision is
  published;
- rhythm planners contain no host phrase timers or AMY-clock queries;
- the frontend-facing planner and transport import no AMY runtime API;
- root tags, local tags, stored groups and simultaneous executions remain
  within their independently configured capacities;
- explicit Stop still releases rhythm-owned voices because stopping transport
  prevents future sequenced releases from firing.

AMY's native regression suite is the authority for execution immutability,
local phase, exact repeat counts, quantized activation, gating, reset behavior,
capacity failure and the unchanged legacy root-sequencer path. LB tests prove
the wire stream and musical policy at its side of the boundary.
