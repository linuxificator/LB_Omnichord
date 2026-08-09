# Qt Omnichord — rhythm, dual synths and strum

## New controls

### Rhythm row

The yellow row contains:

- A circular rhythm selector.
- One play/stop button (`▶` / `■`).
- Tempo.
- Busyness.
- Chord activity.
- A vertical percussion-volume control.

The rhythm engine starts stopped.

### Busyness algorithm

Every rhythm in `rhythms.json` has five ordered percussion layers.

```text
0 = defining pulse only
1 = core backbeat or guide rhythm
2 = subdivision/pulse layer
3 = stylistic syncopation or colour
4 = a musically related fill/ornament layer
```

Selecting a higher value includes all lower layers. The defining pattern is
therefore never replaced: house retains four-on-the-floor, tango retains its
habanera/marcato basis, reggae retains the one-drop, and odd metres retain
their additive accent grouping.

### Chord activity

Each rhythm has five complete chord-trigger patterns. Level zero triggers the
selected chord only on the first count of each bar. Higher levels use
genre-specific placements rather than a generic density algorithm.

The rhythm data is entirely external:

```text
rhythms.json
```

The Python application selects the current percussion layers and chord
pattern, then sends one compact JSON pattern to Sonic Pi. Sonic Pi remains
responsible for sample and chord timing.

## Layout

- Bone-white main background.
- Yellow rhythm family row.
- Blue band connecting the strum synth, its sliders, strum volume and strum
  surface.
- Green chord synth and chord volume.
- Six red octave buttons per chord row: O1 through O6.
- Brown `CHORD OFF` button.
- A green circular button with a blue down arrow beside the first chord row.

The arrow copies all blue strum-synth presets, the currently selected synth
and the blue volume into the green chord engine.

## Included rhythms

```text
waltz
bossa
rock
house
tango
5/4 · 3+2
7/8 · 2+2+3
reggae one-drop
shuffle
disco
samba
```

The catalogue includes source notes and links documenting the defining
features used as the stable base layer. The detailed patterns and density
levels are original configurable arrangements derived from those conventions.

## OSC

```text
/chord/notes
/chord/trigger
/chord/amp
/chord/synth/name
/chord/synth/params

/strum/note
/strum/amp
/strum/synth/name
/strum/synth/params

/rhythm/config
/rhythm/running
/rhythm/amp
```

`/rhythm/config` contains the selected pattern as a compact JSON string.
The included Sonic Pi program parses it using Ruby's standard JSON library.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Run `sonic_pi_receiver.rb` in Sonic Pi.


## Bass and synchronization revision

A grey bass-synth row now sits immediately below the yellow rhythm section.
The yellow section contains a fourth horizontal control, `bass activity`.

Every rhythm in `rhythms.json` now has five `bass_levels`. These use the
rhythm's own accompaniment timings and progressively move through the
selected chord's low-register notes.

Chord selection now uses one atomic OSC message:

```text
/chord/state "{notes:[...],bass_notes:[...],play_now:true}"
```

The former separate `/chord/notes` and `/chord/trigger` messages could be
received by different Sonic Pi loops in the opposite order. The new message
updates the state and triggers the exact supplied note list in one receiver.

The rhythm loop also merges these into one sorted timeline:

```text
percussion_events
bass_events
chord_events
```

This puts percussion, bass and chord accompaniment on one Sonic Pi clock.
The receiver uses a 0.1-second schedule-ahead window as a compromise between
tight response and internally scheduled timing stability.


## Bass controls and four-state activity revision

- `B VOL` is a separate vertical bass-volume control.
- The grey bass row has an independent circular play/stop button.
- The dark-blue strum surface now spans the complete height.
- The green chord-synth row has a pale-green family background.
- Tempo always spans 40–200 BPM.
- Percussion, chord and bass activity are four-state button groups.

Visible levels map to the existing catalogue as `1,2,3,4 -> 0,1,2,4`, so level 4 includes the complete arrangement and fills.

Additional OSC state: `/bass/amp` and `/bass/running`.


## Startup defaults

Startup selections are now consolidated in:

```text
defaults.json
```

That file controls:

- The four initial chord types.
- Initial octave and inversion per chord row.
- Chord, strum and bass synth selection.
- Chord, strum, bass and percussion volume.
- Initial rhythm.
- Initial rhythm and bass play/stop states.

The other files retain data that belongs to their own domain:

```text
chords.csv    chord intervals and wheel order
synths.json   synth catalogue, controls and Sonic Pi parameter defaults
rhythms.json  rhythm events and per-rhythm tempo/activity defaults
defaults.json application startup selections
```

## Visual details

The selected octave now changes to violet with a thick pale-violet border,
rather than relying on a thin white edge.

The three activity selectors are separately framed and staggered vertically:

```text
percussion activity  ─ highest
chord activity       ─ middle
bass activity        ─ lowest
```


## Expanded rhythm catalogue

`rhythms.json` now contains 54 rhythm entries grouped into pop/rock, country, traditional, blues/jazz, soul/funk, electronic, urban, Latin, Afro-Cuban, Caribbean and odd-metre families. The patterns are deliberately editable approximations rather than claimed transcriptions. Source notes and reference links are embedded at the top of the JSON.

## Full-screen startup and automatic scaling

Start full screen from the command line:

```bash
python main.py --fullscreen
```

Or change this in `defaults.json`:

```json
"window": {
  "start_fullscreen": true,
  "scale_to_fit": true
}
```

The complete control surface is uniformly scaled and centred to use the largest size that fits the current window or full screen. F11 toggles full screen and Escape returns to windowed mode. Use `--no-scale-to-fit` to retain the design size and scroll instead.


## Multi-touch diagnostics

The strum strip now uses `MultiPointTouchArea` for real touchscreen input
and separate mouse-only `TapHandler`/`DragHandler` instances for desktop
testing. The touch area owns only one point inside the strum strip, leaving
other fingers available to the rest of the interface.

Run the standalone diagnostic on the Raspberry Pi:

```bash
source .venv/bin/activate
python touch_test.py
```

Place two or more fingers on different parts of the screen.

Expected result:

```text
Current touch points: 2
Maximum seen: 2
```

The terminal also prints Qt's device classification and `max_points`.

A healthy direct touchscreen should appear approximately as:

```text
type=TouchScreen max_points=5
```

If the test never exceeds one point, or Qt reports `Mouse`,
`TouchPad`, or `max_points=1`, the application is receiving a single-pointer
stream from the display server or driver. QML cannot reconstruct the missing
touch contacts; the Raspberry Pi input/display configuration must then be
corrected.


## QML backend lifetime fix

The QML engine is now explicitly destroyed before the Python `backend`
QObject when the application exits. This prevents shutdown-time messages
such as:

```text
TypeError: Cannot read property 'chordVolume' of null
TypeError: Cannot read property 'stateVersion' of null
```

No runtime UI, touch, OSC, or audio behavior is changed by this fix.


## Chord tap versus hold

Chord note buttons now support two gestures:

```text
quick tap       existing one-shot chord
hold >= 200 ms  sustained chord until the finger is released
```

The threshold is the QML property:

```qml
property int chordHoldThresholdMs: 200
```

When a sustained hold begins:

1. The selected chord becomes the active chord for the strum/bass logic.
2. Chord activity is temporarily overridden to `0`.
3. The chord-activity selector visibly moves to `0`.
4. Automatic rhythm chord events are immediately gated.
5. Sonic Pi starts long-sustain chord synth nodes.

On release, those synth nodes are killed and the chord-activity selector
returns to exactly the value it had before the hold. The underlying
per-rhythm activity setting is never overwritten by the temporary hold.

Chord activity `0` can also be selected manually. In that state the rhythm
plays no automatic chords, while normal chord taps and sustained chord holds
still work.

New OSC addresses:

```text
/chord/hold/start
/chord/hold/stop
/rhythm/chord/enabled
```

The strum surface no longer contains HIGH, LOW or STRUM text.


## Immediate chord-button response

Chord buttons now produce sound on `pressed`, not after the 200 ms
tap/hold threshold.

```text
press
  -> immediate chord note-on
  -> start 200 ms classification timer

release before 200 ms
  -> release/fade the chord
  -> ordinary tap
  -> chord activity is never changed

still pressed at 200 ms
  -> the already-playing chord continues without retriggering
  -> chord activity temporarily changes to 0
  -> automatic rhythm chords are gated

release after 200 ms
  -> release/fade the held chord
  -> previous chord activity is restored
```

The threshold therefore remains only for deciding whether the gesture should
temporarily override chord activity. It no longer delays the sound.

Sonic Pi uses a long-sustain node for the manual chord. On finger release,
the node's controllable `amp` is faded to zero using `amp_slide`, then the
silent node is killed. Sonic Pi's ADSR options themselves cannot be modified
after the node has started.


## Multi-touch/manual-chord reliability fixes

### Row controls no longer retrigger the selected chord

Changing chord type, octave or inversion updates the active chord state used
by strum/rhythm/bass but sends `play_now: false`. Therefore tapping an octave
button after playing a chord does not play that chord again.

### Independent manual chord voices

Each pressed chord button now owns its own manual voice ID. Multiple chord
buttons may therefore sound simultaneously. The last pressed chord remains
the active chord for the strum and bass logic, but releasing one finger stops
only that finger's manual voice.

If several buttons are down and the active one is released, active state
deterministically moves to the most recently pressed remaining button.

The temporary chord-activity override remains at `0` while at least one
pressed chord has crossed the hold threshold, and returns to the user's
stored activity only after the last promoted hold is released.

### Ordered OSC note-on/note-off

Old versions used two separate Sonic Pi loops:

```text
/chord/hold/start
/chord/hold/stop
```

A fast tap could therefore be handled out of order by the two independent
loops. The receiver now uses one serialized event stream:

```text
/chord/manual
```

with JSON actions `start`, `stop`, and `stop_all`. This guarantees note-on
and note-off ordering and prevents stuck manual chord nodes.

### Startup cleanup

At GUI startup the backend now first sends rhythm transport OFF and
`stop_all` before loading the rest of the state. Sonic Pi also kills any
manual nodes left by a previous receiver run. Automatic rhythm chords start
gated until the GUI explicitly publishes its current chord-activity state.

The rhythm player also checks transport state again after each sleep and
immediately before playing an event.

### Strum level

The temporary `0.35` Sonic Pi strum attenuation has been removed. Strum amp
is again exactly the GUI `strumVolume`.


## Live octave/inversion retuning

Octave, inversion and chord-type changes now affect currently sounding
voices.

- Every held manual chord in the edited row receives a `/chord/manual`
  `update` event and is pitch-retuned in place.
- The most recently triggered automatic rhythm chord is tracked as individual
  Sonic Pi nodes and is retuned when the active chord's octave/inversion
  changes.
- If no rhythm chord is currently sounding, changing octave/inversion does
  not produce a new attack.

## Blue edge with multi-touch

The selected state is now the union of the persistent active chord and the
button's physical `pressed` state. Every simultaneously touched chord button
therefore receives the blue edge.

## Startup rhythm isolation

Automatic chord playback now requires both:

```text
rhythm transport ON
chord activity > 0
```

When rhythm transport is OFF the GUI always sends chord gate `0`, and the
Sonic Pi receiver independently forces the gate to `0`. A stale scheduled
bar can therefore no longer produce the startup-only second chord while the
drum transport is visibly stopped.


## Idle CPU optimization

The rhythm player previously used:

```ruby
if get(:rhythm_running) != 1
  sleep 0.05
  next
end
```

That wakes the Sonic Pi Ruby scheduler 20 times per second while the
instrument is completely idle.

It is now event-driven:

```ruby
sync :omnichord_rhythm_wake
```

The OSC receiver cues that event only when rhythm transport or rhythm
configuration changes. The other OSC receiver loops already block on `sync`
and therefore did not need changing.

This optimization affects only the Sonic Pi Ruby process. It cannot reduce
the separate Qt Sonic Pi GUI process itself.


## Fixed seven-octave strum range

The strum is now independent of the chord row's octave and inversion.

Its absolute pitch window is:

```text
MIDI 24 .. 107
C1      .. B7
```

That is exactly seven chromatic octaves of physical range. Only notes whose
pitch class belongs to the active chord are included.

For example, C major gives:

```text
C1 E1 G1
C2 E2 G2
C3 E3 G3
C4 E4 G4
C5 E5 G5
C6 E6 G6
C7 E7 G7
```

Changing the chord row from O2 to O6, or changing its inversion, does not
move or reorder this strum range.

Changing the root or chord type does change the available strum notes,
because those define the chord pitch classes.


## Touch-oriented wheel selection

All three wheel types now support both gestures:

```text
swipe/flick                 existing wheel behavior
tap visible item above      select previous value
tap visible item below      select next value
tap current centre item     no change
```

A `TapHandler` observes short taps while normal drags remain available to the
`Tumbler`.

## Tap/hold volume controls

The four narrow vertical volume controls keep the same visual track/fill/
handle appearance but are no longer sliders.

```text
tap upper half     +5 %
tap lower half     -5 %
hold ~380 ms       begin fast auto-repeat
auto-repeat        2.5 % every 75 ms
```

Only the percentage is displayed, centred in the control. The P VOL/B VOL/
S VOL/C VOL text labels have been removed.

Each volume control owns at most one touch point, so it remains compatible
with the instrument's multi-touch interaction.

## Instrument watermarks

The four colored synth/rhythm bars now contain low-contrast vector line-art
watermarks drawn directly by QML Canvas:

```text
yellow   drum, tambourine, maracas, cymbal
gray     tuba, contrabass, sousaphone
blue     harp, lyre
green    accordion, mandolin, Omnichord-style instrument
```

They are deliberately sparse and only a slightly different shade from the
bar background.

## First-chord startup race hardening

The GUI's `rhythm_running` state is now carried inside `/chord/state` and
manual chord-start packets.

If a chord arrives while the GUI says rhythm transport is OFF, that same
Sonic Pi receiver loop immediately:

```text
sets rhythm_running = 0
sets rhythm_chord_enabled = 0
resets bar/phrase position
stops any tracked automatic rhythm-chord nodes
wakes/aborts the rhythm scheduler
```

This is intentionally redundant with `/rhythm/running`. It removes the
cross-live-loop startup race where the first manual chord could arrive while
Sonic Pi still had stale rhythm state from the previous Qt process.


## Correct touchscreen wheel taps

Tap handling now lives in each Tumbler delegate rather than on the Tumbler
itself. A stationary touch selects the touched visible item. Moving beyond
Qt's drag threshold cancels the tap and retains normal swipe/flick behavior.

This applies to rhythm, synth and chord-type wheels.

## Immediate manual chord override

The 200 ms hold timer is gone. From finger-down, effective chord activity is
immediately 0 and automatic rhythm chords are gated before the manual chord
note-on is sent. Releasing the final pressed chord restores the stored
activity value.

A tap is simply a short press/release.

## Startup rhythm wake correction

Receiving `/rhythm/config` no longer wakes `rhythm_player`. A config packet
only stages data. The normal wake source is the actual transport message
`/rhythm/running`.

This removes the startup race where initial Qt configuration could wake a
Sonic Pi rhythm loop while it still briefly held state from the previous Qt
process.


## Orange utility / tuning strip

A fifth 104-pixel-high row has been added above the rhythm row.

The orange wheel contains:

```text
HARM
EQ       default
JV
```

These modes are UI/preset state only for now; they do not yet alter pitch.

The adjacent orange tap control contains the reference frequency:

```text
range       415 .. 466 Hz
default     440 Hz
tap step    1 Hz
hold        fast repeat
```

Its x-position is exactly aligned above the beginning of the yellow tempo
slider. The orange background stops at the right edge of this tap control.
The small orange area between wheel and number contains a tuning-fork
watermark.

## PNC! and ESC

`PNC!` is a dedicated panic control. It:

- stops rhythm transport;
- disables automatic chords;
- stops bass transport;
- stops all manual chord nodes;
- stops the currently tracked rhythm chord;
- kills recent strum, bass and percussion nodes;
- sends a dedicated `/panic` OSC packet to Sonic Pi.

`ESC` returns the application to windowed mode.

## Presets

The violet strip contains one large `STR` button and 18 round preset buttons
`P1` through `P18`.

At startup the application creates:

```text
~/.omnichord/
    p1.json
    p2.json
    ...
    p18.json
    last_preset.json
```

Missing preset files are initialized from the application's current default
state and existing files are never overwritten.

`last_preset.json` stores the most recently selected preset. That preset is
loaded before the QML interface is shown on the next startup.

Selecting any `P<n>` loads it immediately. Selecting the already highlighted
preset reloads it from disk. `STR` writes the complete current instrument
state to the selected preset.

Preset JSON includes:

- all four chord-row chord types, octaves and inversions;
- selected chord, strum and bass synths;
- all remembered control values for every synth in each of those three roles;
- all four volumes;
- rhythm and bass running/stopped state;
- selected rhythm;
- tempo and all three activity settings for every rhythm;
- tuning mode and reference-frequency UI settings.

Active/held performance notes are intentionally not stored.


## FSC / ESC fullscreen toggle

The pale-red window-state button is now bidirectional:

```text
fullscreen    button says ESC    -> normal decorated window
windowed      button says FSC    -> fullscreen
```

The application window is created with explicit normal top-level/titlebar
flags and changes state with `showFullScreen()` / `showNormal()` instead of
only assigning the `visibility` property. This is intended to restore normal
labwc/Wayland window decoration when leaving fullscreen.

F11 still toggles both ways. The keyboard Escape key still exits fullscreen.

## Tuba and watermark update

The bass row now uses `tuba_watermark.png`, derived directly from the supplied
upright-tuba reference drawing. The approximate old tuba vector has been
removed. The contrabass and sousaphone remain.

All watermark opacity and line weight have been increased. The green
Omnichord watermark has also been redrawn around the classic Suzuki
Omnichord/OM-84 form: long chord-key wing, sloping control area, diagonal
strum plate and large rounded speaker end.

## A-reference tuning

The 415..466 control now changes actual pitch. The default remains A=440 Hz.

Sonic Pi numeric notes use the MIDI logarithmic semitone scale, so the Qt
application calculates:

```text
ratio       = A_reference / 440
note_offset = 12 * log2(ratio)
sent_note   = nominal_MIDI_note + note_offset
```

For example, changing A from 440 to 442 applies the same small fractional
semitone offset to chord, rhythm-chord, bass and strum notes.

The calculation remains entirely in the Qt/Python application. Sonic Pi only
receives already-adjusted decimal note values.

Chord/manual/bass notes are sent in JSON as Python double-precision numbers.
The direct OSC strum-note path sends 12 decimal places as text and Sonic Pi
converts it with `to_f`, avoiding OSC float32 precision loss.

Changing A while a manual chord is held retunes that chord immediately. It
also republishes the active rhythm chord/bass state. The reference-frequency
value was already part of preset JSON under:

```json
"tuning": {
  "mode": "EQ",
  "reference_hz": 440
}
```

so stored presets retain their A reference.


## Chord hold stability / diagnostics

The chord-note controls no longer use Qt Quick `Button`. They now use a
plain visual item plus one `MultiPointTouchArea` each. This removes
`AbstractButton`'s click/grab/cancel state machine from musical note holds.

A physical touch owns one chord key until that touch is released or the
touchscreen itself reports cancellation.

### Debug flag

To capture the remaining problem if it still occurs:

```bash
python3 main.py --fullscreen --debug
```

The application prints the file name, for example:

```text
Omnichord debug log: /home/pi/.omnichord/debug-20260808-191234.jsonl
```

Or specify one:

```bash
python3 main.py --fullscreen --debug-file ~/.omnichord/test.jsonl
```

The JSON-lines file records:

- QML chord touch `pressed`, `released`, `canceled`;
- backend `pressChord` / `releaseChord`;
- pressed/promoted chord sets;
- effective and stored chord activity;
- hold-override changes;
- calls to the visible chord-activity selector;
- manual chord start/stop OSC;
- chord-state OSC;
- rhythm chord gate/config OSC.

If the activity still visibly alternates 0/3 while one finger remains down,
reproduce it once and send that `.jsonl` file.


## Touch-dropout filter derived from the captured trace

The debug log proves that the 0/3 oscillation is not generated by the rhythm
scheduler or Sonic Pi. During one physical hold, Qt reported several actual
release/re-press cycles:

```text
contact 342 ms -> release -> 77 ms gap -> press
contact 328 ms -> release -> 343 ms gap -> press
contact 217 ms -> release -> 1087 ms gap -> press
then 3506 ms continuous contact -> actual release
```

The backend now filters that exact failure mode.

A first short release gets a 200 ms grace period. If the same key returns
during that interval, note-off is cancelled and the existing Sonic Pi voice
continues without retriggering. That proves a dropout occurred and marks that
physical hold as bounce mode.

In bounce mode, later short dropouts can be bridged for up to 1300 ms. Once
the touchscreen has reported one uninterrupted contact for at least 800 ms,
the next release is treated as genuine and note-off happens immediately.

Therefore the long 1300 ms grace does not normally delay the end of a stable
held chord. A normal quick tap has only a 200 ms release tail.

While contact is temporarily absent but a release is pending, chord activity
remains at 0 and the manual chord remains sounding.

Debug mode is still available. New events include:

```text
chord_release_delayed
touch_dropout_recovered
pressChord_dropout_resume
chord_release_finalized
```


## Second dropout trace: exact remaining hiccup

The second debug trace showed that the previous filter was already suppressing
all later false touch transitions. The one remaining audible/visible hiccup
was the first dropout:

```text
press at       3319 ms
false release  3562 ms
200 ms timer expired at ~3753 ms
touch returned 3793 ms
```

The touch was absent for about 230 ms, so the old 200 ms initial grace expired
roughly 40 ms before the same key returned. That caused exactly one real
manual note-off/note-on pair and one activity `0 -> 3 -> 0` transition.

The initial filter is now:

```text
release <= 160 ms after a new press:
    genuine quick tap -> release immediately

release after 160 ms but before 800 ms:
    wait up to 450 ms for the same touch to return

if it returns:
    classify the physical hold as dropout/bounce mode
    keep the same Sonic Pi voice
    keep activity at 0

after bounce mode has been detected:
    bridge later dropouts for up to 1300 ms

continuous stable contact >= 800 ms:
    release immediately
```

This keeps normal short taps responsive while covering the 230 ms current
trace and the approximately 343 ms first-dropout gap seen in the earlier
capture.

## Sonic Pi idle CPU regression

The event-driven rhythm scheduler itself remains in place. The regression was
caused by later safety code adding extra:

```ruby
cue :omnichord_rhythm_wake
```

calls to manual-chord, chord-state and panic paths even while rhythm transport
was OFF.

Those wakeups have been removed.

The rhythm player now receives `:omnichord_rhythm_wake` only when
`/rhythm/running` changes to `1`. When rhythm is stopped it remains blocked on
`sync` with no periodic polling and no chord/manual wakeups.


## Receiver idle-CPU wake semantics restored

The later receiver changed the rhythm wake policy to cue the sleeping rhythm
player only on transport START and not on configuration reception. Despite
looking more efficient, that version regressed idle CPU on the Raspberry Pi 5.

The receiver now uses the exact event-wake pattern from the previously tested
low-CPU version:

```ruby
live_loop :receive_rhythm_running do
  use_real_time
  new_state = sync("/osc*/rhythm/running")[0].to_i
  # ... update state ...
  cue :omnichord_rhythm_wake
end

live_loop :receive_rhythm_config do
  use_real_time
  set :rhythm_config_json,
      sync("/osc*/rhythm/config")[0].to_s
  cue :omnichord_rhythm_wake
end
```

The rhythm player itself still has no polling loop:

```ruby
if get(:rhythm_running) != 1
  sync :omnichord_rhythm_wake
  next
end
```

Thus a startup config/OFF packet wakes it once, after which it returns to a
blocking `sync`. There is still no 50-ms idle polling.

Manual chord, chord-state and panic paths do not cue the rhythm player.


## HARM intonation

The orange `EQ / HARM / JV` wheel now has two implemented intonations:

```text
EQ      equal temperament; every JSON correction factor is exactly 1.0
HARM    harmonic / just intonation from intonation_harm.json
JV      reserved; currently behaves exactly like EQ
```

The active **key** is the root of the currently active Omnichord chord. Thus,
pressing a C chord uses `key_c`, pressing D-flat uses `key_db`, etc.

There are 12 chromatic roots and 12 chromatic note classes, therefore each
intonation file contains **144 factors (12 x 12)**.

Files:

```text
intonation_eq.json
intonation_harm.json
```

Each file is deliberately simple, for example:

```json
{
  "key_c": {
    "note_c": 1.0,
    "note_db": 1.0067992668604735,
    "note_d": 1.0022610579078817
  }
}
```

The JSON number is a **frequency correction relative to equal temperament**,
not the interval ratio itself. For C->E, HARM wants a frequency ratio 5/4,
while equal temperament gives `2^(4/12)`, so:

```text
factor(C,E) = (5/4) / 2^(4/12)
            = 0.992125657480125...
```

Qt converts the factor to the fractional Sonic Pi note offset:

```text
intonation_offset = 12 * log2(factor)

sent_note =
    nominal_note
    + 12 * log2(A_reference / 440)
    + intonation_offset
```

Thus the existing A-reference control and the new intonation correction are
independent multiplicative frequency factors.

The HARM interval table is:


| semitones | ratio | ET correction factor | cents vs ET |
| ---: | ---: | ---: | ---: |
| 0 | 1/1 | 1.000000000000000 | +0.000 |
| 1 | 16/15 | 1.006799266860473 | +11.731 |
| 2 | 9/8 | 1.002261057907882 | +3.910 |
| 3 | 6/5 | 1.009075698304458 | +15.641 |
| 4 | 5/4 | 0.992125657480125 | -13.686 |
| 5 | 4/3 | 0.998871384584454 | -1.955 |
| 6 | 7/5 | 0.989949493661166 | -17.488 |
| 7 | 3/2 | 1.001129890627526 | +1.955 |
| 8 | 8/5 | 1.007936839915899 | +13.686 |
| 9 | 5/3 | 0.991005929168934 | -15.641 |
| 10 | 7/4 | 0.982154292270701 | -31.174 |
| 11 | 15/8 | 0.993246650961839 | -11.731 |

For C major this gives exactly:

```text
C   1/1
E   5/4
G   3/2
```

The major second / chordal 9th uses `9/8`, so harmonic 9 is useful. The
ordinary chordal 11th is a perfect fourth `4/3`; it is not the 11th harmonic.
Using `11/8` would create the undecimal interval at about 551.3 cents, almost
49 cents below an equal-tempered tritone, so it is not used by this HARM
table.

The harmonic seventh uses `7/4`, and the tritone uses `7/5`. Major seventh
and minor second naturally use `15/8` and `16/15`; these have larger integer
numerators but still use only small prime factors.

The intonation correction is applied in Qt to:

- manually held chords;
- automatic/rhythm chord notes;
- bass notes;
- strum notes across the fixed seven-octave range.

Changing `EQ`/`HARM` while a chord is sounding retunes the held chord in
place. The selected mode was already stored in preset JSON under `tuning.mode`,
so HARM/EQ selection remains part of every preset.


## Factory presets

The project now ships 18 complete factory preset files:

```text
default_presets/p1.json
...
default_presets/p18.json
```

On startup, `~/.omnichord/pN.json` is created from the matching factory file
only when that user file does not already exist. Existing user presets are
never overwritten.

The progression is intentional:

```text
P1..P4     subdued / moody / easy-listening
P5..P9     pop, jazz, Latin, funk and dub
P10..P13   disco, house, 2-step and breakbeat
P14..P16   techno, trance and drum & bass
P17..P18   rave / strongly experimental dance-floor settings
```

Every factory preset has:

```json
"transport": {
  "rhythm_running": false,
  "bass_running": true
}
```

so selecting a factory preset never starts drums by itself.

## STR feedback

After `STR` writes the selected preset, that preset button flashes a brighter
violet with a white border for about half a second. The stored preset remains
selected normally afterward.

## JV intonation

`JV` is now implemented as a third 12 x 12 key-dependent intonation table in:

```text
intonation_jv.json
```

The C-root construction follows the specified chain exactly:

```text
C  = 1
G  = C  * 3/2
D  = G  * 3/4
A  = D  * 3/2
E  = A  * 3/4
B  = E  * 3/2
Eb = B  * 5/8
```

To fill the remaining chromatic notes from the new E-flat anchor without
introducing another non-3-limit interval, the table continues by pure fifth
relations in both directions:

```text
Eb -> Bb -> F
Eb -> Ab -> Db -> F#/Gb
```

The second branch is the inverse direction on the circle of fifths and thus
uses the equivalent octave-normalized powers of 2 and 3.

The resulting C-root ratios and EQ correction factors are:


| semitones | JV ratio | ET correction factor | cents vs ET |
| ---: | ---: | ---: | ---: |
| 0 | 1/1 | 1.000000000000000 | +0.000 |
| 1 | 135/128 | 0.995492439156474 | -7.821 |
| 2 | 9/8 | 1.002261057907882 | +3.910 |
| 3 | 1215/1024 | 0.997743305208265 | -3.911 |
| 4 | 81/64 | 1.004527228198626 | +7.820 |
| 5 | 10935/8192 | 0.999999260598542 | -0.001 |
| 6 | 45/32 | 0.994368911043582 | -9.776 |
| 7 | 3/2 | 1.001129890627526 | +1.955 |
| 8 | 405/256 | 0.996617236733249 | -5.866 |
| 9 | 27/16 | 1.003393503283546 | +5.865 |
| 10 | 3645/2048 | 0.998870646017496 | -1.956 |
| 11 | 243/128 | 1.005662234098862 | +9.775 |

All JV correction factors are deliberately close to 1.0. Across the complete
relative octave the range is approximately:

```text
minimum factor = 0.9943689
maximum factor = 1.0056622
```

or less than about ±10 cents from equal temperament.

As with HARM, `intonation_jv.json` stores correction factors relative to the
already-selected equal-tempered note. Qt applies:

```text
sent_note =
    nominal_note
    + 12 * log2(A_reference / 440)
    + 12 * log2(JV_or_HARM_correction_factor)
```

The active chord root selects the corresponding `key_*` row. All 12 roots are
transpositions of the same relative JV construction.


## Preset switch while rhythm is playing: ZeroTimeLoopError fix

Selecting a preset while the rhythm player was active could stop Sonic Pi
with:

```text
loop did not sleep or sync!
ZeroTimeLoopError
```

The cause was the transport-OFF path in `live_loop :rhythm_player`. If the
transport changed to OFF before the next scheduled event, the loop marked the
bar as aborted and skipped the normal end-of-bar `sleep`. That left one
`live_loop` iteration with no `sleep` or `sync`, which Sonic Pi forbids.

The aborted transition now executes:

```ruby
sleep 0.001
next
```

exactly once. On the next iteration `rhythm_running == 0`, so the receiver
blocks on:

```ruby
sync :omnichord_rhythm_wake
```

There is therefore no reintroduced idle polling and no 50-ms CPU loop.


## Safer aborted-rhythm handling

The previous ZeroTimeLoopError fix used `sleep 0.001` on an aborted bar.
Although that code should only run on transport transitions, it has been
removed completely.

An aborted bar now does:

```ruby
sync :omnichord_rhythm_wake
next
```

Transport is already OFF in this path, so blocking is the natural state. A
later rhythm start/configuration message wakes the player. This satisfies
Sonic Pi's requirement that every live-loop iteration sleep or sync while
adding no timer, polling loop, or scheduler wakeup.


## Raspberry Pi display/Wayland diagnostic build

This build removes all explicit `Window.flags` from `Main.qml`. In windowed
mode the application is now created as an ordinary Qt top-level window and
the desktop compositor is solely responsible for title bar, movement,
placement and decoration.

Do the first test with:

```bash
python3 main.py --windowed --software-renderer
```

This changes only Qt Quick rendering; Sonic Pi and OSC remain identical.

The software backend uses Qt Quick's raster scene-graph adaptation rather than
the GPU-backed RHI renderer. If the HDMI blanking disappears with this option,
the fault is in the Qt Quick GPU / Wayland / compositor graphics path rather
than chord/audio logic.

For comparison:

```bash
python3 main.py --windowed --opengl-renderer
```

To isolate native Wayland versus XWayland:

```bash
python3 main.py --windowed --software-renderer --x11
```

or:

```bash
python3 main.py --windowed --software-renderer --wayland
```

At startup this diagnostic build prints the QPA platform and relevant Qt
renderer/environment values. `QSG_INFO=1` is also enabled so Qt prints the
actual scene-graph backend.

If the complete display loses signal again, inspect user-space desktop logs,
not only the kernel journal:

```bash
journalctl -b --since "-3 min" | \
  grep -Ei 'labwc|wayland|wlroots|xwayland|segfault|coredump|python|qt|v3d|vc4|drm'
```

and:

```bash
coredumpctl list --since "-10 min"
```

A `labwc`, Xwayland, Python/PySide or graphics-process crash should then be
visible even when `journalctl -k` showed nothing.


## Percussion amplitude normalization

`rhythms.json` previously used drum-event amplitudes both for relative
kick/snare/hat balance and, unintentionally, as an overall rhythm attenuation.
The separate percussion volume control then attenuated the complete section a
second time.

All percussion event amplitudes are now normalized independently per rhythm:

```text
scale = 1 / strongest_event_amp_in_this_rhythm
new_event_amp = old_event_amp * scale
```

Thus every rhythm has a strongest percussion event of exactly `1.0`, while all
relative event amplitudes inside that rhythm are preserved.

Examples:

```text
pop_8:
    old peak 0.82
    scale 1.2195
    new peak 1.0

jazz_swing:
    old peak 0.34
    scale 2.9412
    new peak 1.0

waltz:
    old peak 1.0
    unchanged
```

The effective percussion sample gain remains:

```ruby
event[:amp] * get(:percussion_amp)
```

but `event[:amp]` is now purely a relative musical accent/dynamics value.
`percussion_amp` is therefore the single overall percussion-volume control.
No hidden gain multiplier was added to Sonic Pi.


## Birthday title

A new `title.json` controls the single centered line above the complete
instrument surface:

```json
{
  "text": "Luciel's Birthday Omnichord",
  "height": 74,
  "font": "URW Chancery L"
}
```

Fields:

```text
text      displayed title
height    title/header height in design pixels
font      Qt/system font-family name
```

The default height is `74`, exactly the chord-button row height. Font size is
derived automatically from the configured header height.

The default font is `URW Chancery L`, a restrained handwriting/calligraphic
style. If that exact family is unavailable on the system, Qt automatically
falls back to a matching installed font. You can put any installed font-family
name in `title.json`.

Set `"height": 0` if the title should be hidden without removing the JSON.

## Percussion normalization

The per-rhythm normalization remains at a peak of exactly `1.0`: the strongest
percussion event in every non-empty rhythm is `1.0`. Event amplitudes therefore
describe only relative accents/dynamics; the percussion volume control remains
the overall section gain.
