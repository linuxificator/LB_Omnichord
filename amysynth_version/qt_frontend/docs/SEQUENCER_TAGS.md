# AMY reusable-sequence allocation

The Omnichord rhythm engine stores fills, base percussion, bass phrases and
automatic chord phrases as reusable AMY sequences. The frontend sends only
wire commands; AMY owns sequence execution, timing and note lifetime.

An ordinary tagged ticks message appends one event to the reusable sequence at
that tag:

```text
H<local-tick>,<period>,<sequence-tag><payload>Z
```

Repeating the tag deliberately cumulates events, like repeated `synth=` calls
cumulate configuration. `HR<tag>Z` explicitly resets the future definition.
Already-running executions retain the immutable definition with which they
started. Untagged one- or two-field `H` messages retain their direct global
sequencer behavior.

`HC<tag>,<velocity>,<alignment>Z` starts for velocity `(0,1]` and stops for
velocity `0`. `HC<tag>,2,<duration>,<alignment>Z` gates current executions. A
sequence made only of period-zero events is a finite one-shot; one containing
a nonzero period repeats until stopped. A sequence may control another
sequence, but the Omnichord uses only one parent/child level and never
constructs recursive control graphs.

## Reserved tags

AMY has one public sequence-tag namespace. The configured 1280 tags are
partitioned so musical owners cannot collide:

| Owner | Reserved tags | Current use |
| --- | ---: | --- |
| Fill-launch root lane | 0..55 | tag 0 |
| Bass root lane | 56..111 | tag 56 |
| Automatic-chord root lane | 112..251 | tag 112 |
| Spare root allocation | 252..255 | unused |
| Stored fills | 256..1191 | 256..525 for the current 270 definitions |
| Automatic chord one-shots | 1192..1255 | stable definitions by source velocity |
| Base percussion loops | 1256..1279 | stable definitions by drum role |

The root allocations retain their wider historical ranges so configuration
migrations and external diagnostics stay stable, although cumulative tags now
let each lane use one tag. `tests/test_sequencer_tags.py` and
`tests/test_drum_patterns.py` audit identities, definition sizes and execution
capacity. New catalogue data must fail clearly rather than be truncated.

## Definition and replacement transactions

Static fill definitions are preloaded once during client construction:

1. `HR<tag>Z` resets the definition.
2. Repeated `H<tick>,0,<tag>...Z` messages cumulate all fill events.
3. Root or controller sequences start the fill when needed.

A live root-lane replacement is one deterministic transaction:

1. stop the old root sequence at the chosen global alignment;
2. reset its future definition with `HR`;
3. append all new events with ordinary tagged `H` messages;
4. start the replacement at that same alignment.

AMY's copy-on-write execution snapshot makes the transaction safe. LB does not
store the AMY clock, execution generations, pending note-offs, sequence end
ticks or an authoring high-water mark. A stopped or empty lane sends an
immediate stop and reset and is not restarted.

Lane-local changes do not reset transport:

- chord selection and tuning rebuild only bass and automatic-chord lanes;
- `CHORD OFF` or manual-hold promotion removes future automatic-chord starts;
- chord arpeggio mode, rate and direction replace only the chord root sequence;
- bass on/off, activity and riff selection replace only the bass root sequence;
- drum activity replaces base-role definitions and starts at a bar boundary;
- fill selection replaces only the fill-launch root sequence;
- a running preset/style switch retains the live performance controls and
  replaces affected definitions on the continuing AMY timebase.

Each automatic chord onset starts a finite child sequence containing every
note-on and its matching note-off. Consequently an arpeggio started under an
old rate completes its original gates even after the future definition has
changed. Multiple finite executions may overlap. Manual chord synth 3 remains
directly controlled and separate from automatic-chord synth 4.

Fill definitions may gate selected running percussion-role sequences. Gating
suppresses new event dispatch for the fill duration while local phase keeps
advancing; already-ringing audio is not cut off.

## Start and stop

Application construction sends `RESET_SEQUENCER | RESET_ALL_OSCS`, configures
the synths, then preloads the static fill catalogue. A later rhythm Start sends
only `RESET_TIMEBASE`, which discards active executions while retaining stored
definitions. After its audio-block boundary, LB installs current drum, fill,
bass and chord root sequences and queues `zY1` last.

Stopping transport is different from stopping one sequence. `zY0` prevents
future sequencer events, including pending note-offs. LB therefore follows it
with immediate all-off messages for rhythm-owned percussion synth 0, bass
synth 1 and automatic-chord synth 4. Manual chord synth 3 and strum synth 2 are
not rhythm-owned and remain untouched.

Manual-hold promotion and `CHORD OFF` do not need that all-off. They stop only
the parent sequence that launches future chord children; a child already
running in AMY still owns and delivers its original release.

## Writer ordering

Low-priority sequencer traffic has an independent generation per lane, so a
new chord update cannot invalidate queued bass or percussion traffic. A full
installation uses a separate `rhythm-full` generation. A targeted update may
queue behind an in-progress full transaction but cannot cancel that transaction
halfway through. A newer complete transaction may supersede an older complete
transaction after invalidating queued per-lane deltas.

## Period wrapping

AMY compares an event's tick with its sequence-local modulo-period offset.
Generated repeating ticks are normalized into `0..period-1`, including
note-offs that cross the end of a bar. The root lane alignment is the least
common multiple of its event periods, preserving global musical phase without
requiring the frontend to query or mirror AMY's clock.

## Synth and bus isolation

Sequence tags isolate scheduled control. AMY synths isolate voice ownership,
and buses isolate effects. The frontend uses four OMNI buses: drums 0, bass 1,
strum 2, and both chord synths 3/4 on chord bus 3. A strum patch change can
therefore alter only bus 2 and cannot change a sounding chord on bus 3.

On first allocation, bus routing is sent in the same command as patch and voice
allocation (`K...i...iv...iy...`). Later repatches retain the synth bus and the
frontend reapplies only the owning role's reverb state. Native regressions
cover this isolation as well as reusable-sequence note ownership.
