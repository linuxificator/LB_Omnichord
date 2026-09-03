# AMY sequencer tag allocation

The Omnichord rhythm engine uses AMY root sequencer tags for sparse fill
launches, bass and automatic chords. Base percussion, fills and automatic
chord phrases use persistent AMY sequencer groups.

AMY stores one sequencer entry per tag. Sending another `H<tick>,<period>,<tag>...` message replaces that tag's previous entry. `H0,0,<tag>Z` clears exactly that tag. A tag is therefore an event identity, not a track identifier: simultaneous note-ons/note-offs require different tags.

## Reserved ranges

The root sequencer retains 256 user-addressable tags. Group event tags are
local to each definition and the integration profile allows 64 per group. The
root allocation is:

| Lane | Tag range | Capacity | Current worst case |
| --- | ---: | ---: | ---: |
| Fill launches | 0..55 | 56 | 10 root triggers in the largest current fill supercycle |
| Bass | 56..111 | 56 | 28 hits × note-on/off (`seven_four_funk`) |
| Automatic chord phrase triggers | 112..251 | 140 | compacted chord onsets: 28 (`seven_four_funk`) |
| Spare | 252..255 | 4 | unused |

Fill group tags are 1..936; the current library occupies 1..270. Automatic
chord phrases reserve 937..1000. Base-role group and execution tags are 1001
upward; the current 18 roles occupy 1001..1018, leaving 1019..1024 spare.
Group-local tags and root tags are separate namespaces.
`tests/test_sequencer_tags.py` and `tests/test_drum_patterns.py` recalculate
the maxima. Adding data which no longer fits must fail CI rather than silently
drop events.

## Lane updates

Bass and chords assign deterministic consecutive tags to their current root
events. The percussion root range contains only fill-group launches. When a
new schedule uses fewer tags than an older one, the no-longer-used root tags
are explicitly cleared. Each base drum role has a stable tagged loop instance;
live replacement is quantized to a whole-bar boundary.

Lane-local operations do not reset the sequencer:

- a quick chord tap starts/stops manual synth 3 and immediately selects the
  active chord for strum, bass and future automatic-phrase definitions. Active
  executions retain their immutable old pitch and releases;
- promotion to a manual chord hold and restoration after release change only
  the automatic-chord tag range (and may update bass pitches because the active
  chord changed). Pointer-up separately stops manual synth 3 immediately; that
  direct note lifetime has no sequencer delay. On hold promotion every future
  synth-4 phrase trigger is cleared. An already-running execution still owns
  its original note-offs and reaches its configured gate; manual synth-3
  note-ons may overlap it;
- `CHORD OFF` clears the same future triggers and `CHORD ON` reinstalls that
  lane. These controls never trigger or release manual synth-3 voices;
- chord-arpeggio `A`, `/1..4` and `U/D` changes replace only the automatic
  chord range. With `A` off, rate and direction remain editable preset state
  but have no musical effect and do not require a lane rewrite;
- bass on/off changes only the bass range;
- bass activity `R` replaces the simple `bass_levels` pattern with the selected
  riff's own PPQ phrase in the same bass range. A selector change replaces only
  that range; it never edits drum/chord tags or resets transport;
- tuning/chord-pitch changes replace bass and automatic-chord ranges but do not touch percussion;
- chord timbre changes repatch synths 3/4 without replacing their sequencer events;
- normal activity/config changes replace the affected root events or group definitions while transport continues;
- a live preset switch carries the current percussion/chord/bass activity,
  fill order and fill density into the destination pattern instead of
  substituting the preset's stored live controls.

A live rhythm-style or preset change replaces tagged events without stopping
transport or resetting the timebase. The new meter enters at the current
sequencer phase. Only explicit Start begins a new transport run; Panic remains
a full reset operation. `../../design/rhythm_bahavior.md` is authoritative.

Riff note-ons and their duration-defined note-offs each own one tag. The
catalogue currently needs at most 34 bass tags (17 notes), below the existing
56-tag bass capacity. A riff may have a period independent from the drum
pattern; its 96-PPQ ticks are converted to AMY's 48-PPQ sequencer units without
deriving or quantizing them from `rhythms.json` `bass_levels`.

Each selected `chord_events` onset becomes one root trigger for an untagged
one-shot phrase execution. The phrase contains all 2–7 chord notes and their
matching releases. `/1..4` maps to a 48, 24, 16 or 12-tick interval. Note gates
use the normal `chord_gate_beats` value as the sounding fraction of that
subdivision, and direction reverses the order of grouped note events.

One AMY tag can safely encode several of these occurrences when an identical
wire body has an exact shorter period which divides the full rhythm period.
The frontend folds only complete residue classes: expanding every compacted tag
over the full period yields exactly the original tick/body set. Coincident
identical triggers are one audible retrigger and are stored once. The catalogue
audit covers every rhythm, visible chord activity, rate and 2–7-note chord;
the current root worst case is 28 tags, below the existing 140-tag range. At
most two of the reserved 64 chord groups are needed concurrently for catalogue
velocities. The joint execution audit counts overlapping chord phrases, the
maximum active drum roles and one fill on every tick; its worst case is 34 of
the configured 40 executions. The
rhythm-chord synth has seven voices so a circular overlap can sound every chord
tone instead of truncating the set to the old four-voice whole-chord limit.

## Start and stop

Starting transport first sends
`S(RESET_TIMEBASE|RESET_SEQUENCER)`. Stored group definitions survive this
reset, while executions and old root triggers do not. It then installs
the current drum loops, fill-launch schedule, bass and automatic-chord ranges,
and queues `zY1` last.

Stopping transport is different from clearing a lane. `zY0` prevents future sequencer events from firing, so a note that is currently sounding cannot rely on its later tagged note-off. Stop therefore performs an explicit all-off immediately after `zY0` for the rhythm-owned synths: percussion synth 0, bass synth 1 and automatic-chord synth 4. Manual chord synth 3 and strum synth 2 are deliberately left alone because they are controlled directly by the player rather than by rhythm transport.

Manual-hold promotion and `CHORD OFF` do not share Stop's lost-off problem.
Their root range contains only future group starts, never the releases of
already-sounding notes. Clearing that range cannot alter an active execution's
immutable definition, so it executes its original note-offs at their original
gates. A live `/1`, `/2`, `/3` or `/4` change atomically publishes a new
revision under the same stable group tag and replaces future root starts. A
running old revision remains unchanged. Drums, bass, transport/timebase and
effects remain untouched.

The real-serial regression tests this ordering and also requires the frontend `rhythmRunning` state to become false after Stop. This guards both against hanging accompaniment notes and against a transport button that remains visually stuck on STOP even though the AMY sequencer has stopped.

## Writer ordering

Low-priority sequencer traffic has an independent generation per lane, so a new chord update cannot invalidate queued bass or percussion traffic. A full Start/style installation uses a separate `rhythm-full` generation.

A targeted lane update is allowed to queue behind an in-progress full transaction, but it must **not cancel that full transaction halfway through**. Otherwise another lane could be left only partially installed. A newer complete transaction may supersede an older complete transaction; it first invalidates queued per-lane updates and then installs the authoritative three-lane state.

On Start, `zY1` is queued as the final item in the complete transaction, after
all tagged definitions. Transport therefore cannot resume before the initial
phrases have been sent.

## Period wrapping

AMY fires repeating entries by comparing the sequencer's modulo-period offset with the stored tick. Every generated tick is therefore normalized into `0..period-1`. This matters for note-offs near the end of a bar: `tick + gate` may cross the period boundary and must wrap rather than become an event which can never fire.

## Synth and bus isolation

Sequencer tags isolate scheduled events; AMY synths isolate voice/oscillator ownership. Audio effects require one more boundary because Juno patches can contain bus-level EQ/chorus/reverb. The frontend therefore uses four AMY buses: drums 0, bass 1, strum 2, and both chord synths 3/4 on chord bus 3. A strum patch change can consequently alter only bus 2; it cannot change the sound of an already-playing chord on bus 3.

On first allocation the target bus is included in the same AMY command as the patch and voice allocation (`K...i...iv...iy...`). This ensures bus-level FX embedded in a Juno patch are directed to the correct role from the start. On later repatches AMY preserves the synth's existing bus; the frontend then reapplies the Omnichord reverb state only to that role's bus.

The regression suite reproduces the reported cross-talk case with **Meow Brass** on chord and **Sustainer** on strum. Changing only the strum patch must leave both chord synth configurations and chord bus 3 unchanged in native AMY state readback.
