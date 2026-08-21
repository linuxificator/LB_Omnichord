# AMY sequencer tag allocation

The Omnichord rhythm engine uses current AMY's user-addressable sequencer tags to keep percussion, bass and automatic chords independent.

AMY stores one sequencer entry per tag. Sending another `H<tick>,<period>,<tag>...` message replaces that tag's previous entry. `H0,0,<tag>Z` clears exactly that tag. A tag is therefore an event identity, not a track identifier: simultaneous note-ons/note-offs require different tags.

## Reserved ranges

Current AMY defaults to 256 user-addressable tags. The complete `music/rhythms.json` catalogue has been audited at every maximum activity level and requires at most:

| Lane | Tag range | Capacity | Current worst case |
| --- | ---: | ---: | ---: |
| Percussion | 0..55 | 56 | 56 events (`trance`) |
| Bass | 56..111 | 56 | 28 hits × note-on/off (`seven_four_funk`) |
| Automatic chords | 112..251 | 140 | 28 hits × up to 4 note-ons + all-off (`seven_four_funk`) |
| Spare | 252..255 | 4 | unused |

`tests/test_sequencer_tags.py` recalculates these maxima from the catalogue. Adding or editing a rhythm which no longer fits must fail CI rather than silently dropping events.

## Lane updates

Each lane assigns deterministic consecutive tags to its current events. When a new pattern uses fewer tags than an older one, the no-longer-used tags are explicitly cleared. The lane remembers its maximum occupied count so an interrupted earlier update cannot leave an unreachable stale event behind.

Lane-local operations do not reset the sequencer:

- manual chord hold/release changes only the automatic-chord tag range (and may update bass pitches because the active chord changed);
- bass on/off changes only the bass range;
- tuning/chord-pitch changes replace bass and automatic-chord ranges but do not touch percussion;
- chord timbre changes repatch synths 3/4 without replacing their sequencer events;
- normal activity/config changes replace the affected tagged patterns while transport continues.

A rhythm-style change may deliberately restart the bar. Panic remains a full reset operation.

## Writer ordering

Low-priority sequencer traffic has an independent generation per lane, so a new chord update cannot invalidate queued bass or percussion traffic. A full Start/style installation uses a separate `rhythm-full` generation.

A targeted lane update is allowed to queue behind an in-progress full transaction, but it must **not cancel that full transaction halfway through**. Otherwise another lane could be left only partially installed. A newer complete transaction may supersede an older complete transaction; it first invalidates queued per-lane updates and then installs the authoritative three-lane state.

On Start, `zY1` is queued as the final item in the complete transaction, after all tagged definitions. Transport therefore cannot resume before the initial pattern has been sent.

## Period wrapping

AMY fires repeating entries by comparing the sequencer's modulo-period offset with the stored tick. Every generated tick is therefore normalized into `0..period-1`. This matters for note-offs near the end of a bar: `tick + gate` may cross the period boundary and must wrap rather than become an event which can never fire.

## Synth and bus isolation

Sequencer tags isolate scheduled events; AMY synths isolate voice/oscillator ownership. Audio effects require one more boundary because Juno patches can contain bus-level EQ/chorus/reverb. The frontend therefore uses four AMY buses: drums 0, bass 1, strum 2, and both chord synths 3/4 on chord bus 3. A strum patch change can consequently alter only bus 2; it cannot change the sound of an already-playing chord on bus 3.

On first allocation the target bus is included in the same AMY command as the patch and voice allocation (`K...i...iv...iy...`). This ensures bus-level FX embedded in a Juno patch are directed to the correct role from the start. On later repatches AMY preserves the synth's existing bus; the frontend then reapplies the Omnichord reverb state only to that role's bus.

The regression suite reproduces the reported cross-talk case with **Meow Brass** on chord and **Sustainer** on strum. Changing only the strum patch must leave both chord synth configurations and chord bus 3 unchanged in native AMY state readback.
