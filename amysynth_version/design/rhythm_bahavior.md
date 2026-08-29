# Omnichord Rhythm Behavior

This document defines the required behavior of the Omnichord rhythm/drum subsystem. It is a behavioral contract for the GUI, backend, AMY wire-command generation, presets, and regression tests.

The central rule is:

> **When rhythm playback is stopped, stored configuration wins. When rhythm playback is running, playback continuity wins.**

A preset or rhythm selection may change the pattern and other stored rhythm parameters, but it must not unexpectedly start or stop the rhythm, change the currently running tempo, reset the sequencer timebase, or interrupt the beat.

For preset selection, playback continuity also includes the current
percussion/chord/bass activity, bass voicing, compatible playing bass riff and
active chord-row octave. These controls shape the accompaniment that is already
in progress and therefore remain live while transport runs.

## 1. State model

The implementation must keep the following concepts separate.

### 1.1 Transport state

`rhythmRunning` means whether the rhythm transport is currently running.

- `true`: rhythm playback is active.
- `false`: rhythm playback is stopped.
- This is live session state.
- It is **never** part of a preset.
- Selecting a preset must never change it.

### 1.2 Effective live tempo

`runningTempo` is the tempo currently used by the active rhythm sequencer.

When playback is running, this live tempo has precedence over the tempo stored in a newly selected preset or rhythm configuration.

### 1.3 Stored rhythm configuration

A preset may store rhythm configuration such as:

- selected rhythm/pattern;
- tempo;
- rhythm-related parameters that are part of the preset design.

The stored tempo is a configuration value. It is not permission to change the currently running tempo during a live preset switch.

### 1.4 Bass activity and independent riff mode

Bass activity values 1 through 4 select the existing simple accompaniment
levels. Value 5 is displayed as `R` and selects an independent riff phrase.
Riff mode never derives timing or pitches from `rhythms.json` `bass_levels`:
each catalogue riff owns its complete 96-PPQ event timing, duration and
velocity.

The available riff set is the stable-index order of entries compatible with
both the current rhythm ID and exact chord suffix. The one-based riff selector
chooses within that set. Stored pitches are normalized to C2/MIDI 36; every
event is transposed by the active chord root and then passes through the normal
OMNI tuning conversion. A root change therefore changes pitch immediately for
the replacement bass schedule without changing event ticks, durations,
velocities, transport or sequencer timebase.

When a chord-suffix, rhythm or preset change produces a new available set, a
riff which is actually playing (`rhythmRunning`, bass transport and `R` all
active) is retained by stable riff ID when that ID occurs in the new set. The
selector follows its possibly different one-based position. If it is not
present, or no riff is playing, the selector uses the loaded preset's
`bass_riff_selector`, clamped to the set, with the application default as the
legacy fallback. Selector and mode changes replace only the bass tag range.

## 2. Application startup

Every application start must begin with:

```text
rhythmRunning = false
```

This is unconditional.

The application may restore or load the selected preset and its stored rhythm configuration, including its rhythm type and tempo, but rhythm playback must remain stopped until the user explicitly starts it.

Example:

```text
Preset P3:
    rhythm = Jazz Waltz
    tempo = 80 BPM
```

At startup with P3 selected:

```text
rhythm = Jazz Waltz
displayed tempo = 80 BPM
rhythmRunning = false
```

No drum or rhythm playback may start automatically because of preset contents or because rhythm playback happened to be active during the previous application session.

## 3. Rhythm ON/OFF is not preset state

The ON/OFF state of rhythm playback must never be serialized into an Omnichord preset.

Therefore a preset selection must never independently cause either of these transitions:

```text
OFF -> ON
ON  -> OFF
```

Only an explicit user transport action may change `rhythmRunning`.

This rule also applies when storing a preset: the current running/stopped state is ignored and is not persisted.

## 4. Preset selection while rhythm is stopped

Initial state:

```text
rhythmRunning = false
```

When a new preset is selected, its stored rhythm configuration is applied normally, including its stored tempo.

Example:

```text
Current state:
    rhythm = Jazz Swing
    tempo = 100 BPM
    running = false

Selected preset:
    rhythm = Jazz Waltz
    tempo = 80 BPM
```

Required result:

```text
rhythm = Jazz Waltz
tempo = 80 BPM
running = false
```

When playback is stopped, the UI therefore shows the actual stored configuration of the selected preset.

## 5. Preset selection while rhythm is running

Initial state:

```text
rhythmRunning = true
runningTempo = T
```

When another preset is selected:

1. `rhythmRunning` remains `true`.
2. The effective live tempo remains exactly `T`.
3. Live percussion activity, chord activity, bass activity and bass voicing
   remain unchanged. In riff mode, a compatible playing riff is retained by
   ID; otherwise the destination preset/default riff selector is applied.
4. The octave of the active chord row remains unchanged. Octaves belonging to
   non-active chord rows may load from the destination preset.
5. The new preset may change the rhythm/pattern.
6. Other rhythm parameters from the new preset may be applied if they do not require stopping or resetting the running rhythm transport.
7. Stored values for the protected live controls must **not** replace their
   effective values during this live transition.
8. The AMY sequencer must remain running.
9. The AMY sequencer timebase must not be reset.
10. No artificial pause, restart, dropped beat, or transport pulse may be inserted.

Example:

```text
Currently playing:
    Jazz Swing
    tempo = 100 BPM

Selected preset contains:
    Jazz Waltz
    tempo = 80 BPM
```

Required live result:

```text
rhythm = Jazz Waltz
effective tempo = 100 BPM
running = true
```

The stored 80 BPM remains part of the preset definition, but it is not allowed to disturb the running 100 BPM performance.

The implementation must never perform the logical equivalent of:

```text
stop rhythm
load preset
reset timebase
start rhythm again
```

for a live preset switch.

## 6. Rhythm-type selection while rhythm is stopped

When the user selects another rhythm/pattern while playback is stopped, the selected rhythm configuration may load its own stored/default tempo.

Example:

```text
Current:
    Jazz Swing
    tempo = 100 BPM
    running = false

Selected rhythm:
    Jazz Waltz
    stored/default tempo = 80 BPM
```

Required result:

```text
rhythm = Jazz Waltz
tempo = 80 BPM
running = false
```

## 7. Rhythm-type selection while rhythm is running

When playback is running, selecting a different rhythm must preserve the current live tempo.

Initial state:

```text
rhythm = A
runningTempo = T
running = true
```

The user selects rhythm `B`, whose stored/default tempo is `TB`.

Required result:

```text
rhythm = B
effective tempo = T
running = true
```

The following invariant applies:

```text
effectiveTempoAfterSwitch == effectiveTempoBeforeSwitch
```

not:

```text
effectiveTempoAfterSwitch == storedTempoOfNewRhythm
```

Example:

```text
Jazz Swing @ 100 BPM
        |
        | select Jazz Waltz
        v
Jazz Waltz @ 100 BPM
```

The new rhythm must adopt the already-running pulse.

## 8. Beat continuity during live changes

Beat continuity is a hard real-time behavioral requirement.

During a live preset or rhythm switch, the implementation must not:

- stop the AMY sequencer;
- restart the AMY sequencer;
- reset the AMY timebase;
- intentionally insert silence;
- intentionally skip a beat;
- delay the next beat to align the new pattern;
- create a transport restart pulse that is audible as a hiccup.

The intended behavior is conceptually:

```text
old rhythm events  -------------------->
                       replace pattern events
new rhythm events                       -------------------->
sequencer clock      --------------------------------------->
```

The clock remains continuous. Only the pattern events associated with the rhythm are replaced.

A live pattern change must therefore use AMY's running sequencer/event replacement mechanism rather than transport stop/reset/start behavior.

## 9. Beat phase versus pattern phase

The priority is continuous physical beat timing, not forcing the newly selected pattern to begin on its own nominal beat 1.

For example, changing from a 4-beat pattern to a 3-beat pattern may cause the new pattern to enter at the current sequencer phase instead of waiting for a newly created bar boundary.

Acceptable:

```text
1 2 3 4 | 2 3 1 2 3 ...
          ^
        switch
```

Not acceptable:

```text
1 2 3 4 | ...pause... | 1 2 3
```

The rhythm may change phase relationship; the pulse may not stop.

## 10. Manual tempo changes while rhythm is running

When the user changes the tempo during playback, the new value immediately becomes the live tempo:

```text
runningTempo = newTempo
```

This new live value must subsequently survive live preset and rhythm changes.

If rhythm tempo has a green MIDI CC binding, MIDI has exclusive write
authority instead: manual tempo setters and UP/DOWN holds have no effect, and
both buttons are disabled and grey. Genuine movement of the bound controller
still changes the effective live tempo through the normal backend path.

Example:

```text
Preset P2 starts at 90 BPM
User changes tempo to 107 BPM
User selects P8 while rhythm is still running
P8 stores 75 BPM
```

Required result:

```text
P8 rhythm/pattern is active
107 BPM remains active
rhythm remains running
```

The preset's stored 75 BPM must not be applied until a later selection occurs while rhythm playback is stopped.

## 11. Stopping rhythm playback

Pressing rhythm/drum OFF changes transport state only:

```text
rhythmRunning: true -> false
```

It must not implicitly:

- reload the current preset;
- restore the preset's stored tempo;
- select another rhythm;
- reset rhythm parameters.

Example:

```text
Preset P8 originally stores 75 BPM
While running, live tempo is 107 BPM
User presses OFF
```

Required result:

```text
rhythm = current rhythm
UI tempo = 107 BPM
running = false
```

The live configuration remains visible after stopping.

A later preset or rhythm selection while stopped may then load the selected configuration's stored tempo normally.

## 12. Starting rhythm playback

Pressing rhythm/drum ON starts the rhythm using the configuration currently shown by the application.

It must not implicitly reload the selected preset first.

For example, if the rhythm is stopped and the user has manually changed the tempo to 103 BPM, pressing ON starts at 103 BPM.

## 13. Storing a preset

When the user stores an Omnichord preset, the current rhythm configuration and current tempo are stored according to the normal preset definition.

Example stored data may include:

```text
rhythm type
tempo
other preset-owned rhythm parameters
```

The following value must never be stored:

```text
rhythmRunning
```

If the user has changed the tempo from 80 BPM to 103 BPM and then stores the preset, 103 BPM becomes the stored preset tempo.

This is true whether the rhythm happens to be running or stopped when `STR` is used.

## 14. Required transition table

| User action | Rhythm stopped | Rhythm running |
|---|---|---|
| Select preset | Load all preset rhythm controls, riff selector and row octaves; stay stopped | Load preset rhythm; preserve live tempo, three activities, bass voicing, a compatible playing riff and active-row octave; otherwise use the destination riff selector; load non-active-row octaves; stay running |
| Select rhythm type | Load rhythm and its stored/default tempo; stay stopped | Change rhythm; preserve current live tempo; stay running |
| Preset says rhythm ON | Ignore | Ignore |
| Preset says rhythm OFF | Ignore | Ignore |
| Change tempo | Change current displayed/configured tempo | Change effective live sequencer tempo immediately |
| Press rhythm ON | Start current configuration and current tempo | No state change required |
| Press rhythm OFF | No state change required | Stop only; retain current configuration and tempo |
| Store preset | Store current rhythm configuration and tempo; never transport state | Store current rhythm configuration and live tempo; never transport state |
| Application restart | Always start stopped | Always start stopped |

## 15. Behavioral invariants for regression tests

### RHYTHM-001 — preset selection never controls transport

Loading any preset must not change `rhythmRunning`.

### RHYTHM-002 — startup is always stopped

Application startup must set:

```text
rhythmRunning = false
```

regardless of previous session state or preset contents.

### RHYTHM-003 — stopped preset selection applies stored tempo

When `rhythmRunning == false`, preset selection must apply the selected preset's stored rhythm tempo.

### RHYTHM-004 — running preset selection preserves live tempo

When `rhythmRunning == true`, preset selection must preserve the currently effective live tempo.

### RHYTHM-005 — stopped rhythm selection applies rhythm tempo

When `rhythmRunning == false`, selecting a rhythm type must apply that rhythm's stored/default tempo.

### RHYTHM-006 — running rhythm selection preserves live tempo

When `rhythmRunning == true`, selecting a rhythm type must preserve the currently effective live tempo.

### RHYTHM-007 — live changes do not stop the sequencer

A live rhythm or preset switch must not stop the AMY sequencer.

### RHYTHM-008 — live changes do not reset timebase

A live rhythm or preset switch must not reset the AMY sequencer timebase.

### RHYTHM-009 — live changes do not insert timing gaps

A live rhythm or preset switch must not intentionally insert a silent beat, dropped beat, restart gap, or artificial alignment delay.

### RHYTHM-010 — stopping does not reload stored state

Stopping rhythm playback must not reload the selected preset tempo or other preset-owned rhythm parameters.

### RHYTHM-011 — transport state is never serialized

`rhythmRunning` must not be serialized into an Omnichord preset or restored from one.

### RHYTHM-012 — UI tempo equals effective tempo while running

While rhythm playback is running, the tempo shown in the GUI must equal the effective AMY sequencer tempo.

### RHYTHM-013 — manual tempo survives live preset changes

If the user manually changes the tempo while running, that tempo must remain effective through subsequent live preset selections until the user explicitly changes tempo or stops and selects another stored configuration.

### RHYTHM-014 — manual tempo survives live rhythm changes

If the user manually changes the tempo while running, that tempo must remain effective through subsequent live rhythm-type changes.

### RHYTHM-015 — starting uses current visible configuration

Starting rhythm playback must use the currently selected rhythm and current displayed tempo without first reloading preset defaults.

### RHYTHM-016 — manual chord takeover preserves the sequenced gate

Chord finger-down must start the manual synth-3 chord immediately. A quick tap
ends that manual voice on finger-up and immediately selects the chord for the
strum, bass and automatic chord accompaniment. The affected bass/chord pitch
schedules are replaced without stopping transport. A tap must not change
effective chord activity, close the automatic-chord lane or perform the
hold-specific draining of its note-on tags.

If Qt's `TapHandler` reports a long press using its platform long-press style
hint, the contact is promoted to a manual hold. The backend does not classify
the contact with another timer. That promotion performs the established
accompaniment takeover:
while automatic rhythm chords are enabled it temporarily closes the effective
automatic-chord lane without changing the independent `CHORD ON/OFF` state. It
must remove the repeating positive-velocity synth-4 note-on tags, but retain the
already scheduled synth-4 `l0` tags. Retained note-offs are explicitly
reinstalled so their delivery does not depend on an older queued lane update. A
rhythm chord which is sounding when the hold is promoted therefore reaches the
note-off at its original sequencer gate instead of being cut off immediately or
hanging because its future note-off was removed.

Current AMY has no deferred tag-removal command or wire callback which says
that a repeating event has just fired. Its per-event user tags nevertheless
provide the required behavior: note-on tags and note-off tags are addressed
independently. While automatic chords are gated off, retained note-off tags may
continue firing harmless synth-4 all-offs; they are replaced or cleared when
the lane is enabled, restarted or reset. Manual synth-3 note-ons begin at
finger-down and may overlap the remainder of the automatic chord's normal gate
and release. Drums, bass, transport, effects and sequencer timebase continue.

### RHYTHM-017 — running preset selection preserves live performance controls

When `rhythmRunning == true`, preset selection must preserve percussion
activity, chord activity, bass activity, bass voicing, a compatible playing
bass riff and the octave of the active chord row, in addition to live tempo.
The riff selector follows that riff's destination-set position; an incompatible
or non-playing riff uses the destination preset/default selector. Octaves of
non-active chord rows load from the destination preset. When
`rhythmRunning == false`, the complete stored set loads normally.

### RHYTHM-018 — CHORD ON/OFF owns only automatic sequencer chords

`CHORD OFF` drains future synth-4 note-ons while preserving their sequenced
note-offs. `CHORD ON` reinstalls the automatic synth-4 lane from the remembered
chord identity. Neither action may start, retrigger, release or otherwise
control a manual synth-3 chord. A physically held chord remains owned by its
chord-button press/release lifecycle.

The gate is a binary live-performance state, initially OFF, and can be toggled
before any chord identity exists. A chord tap selects the active chord and may
therefore replace the bass and automatic-chord pitches, but it must never change
that gate state or temporarily close the lane. When the gate is ON, only a
manual hold temporarily suppresses its sequencer lane; release restores it
without toggling the control.

### RHYTHM-019 — bass activity adds independent riff mode

Percussion and chord activity expose levels 1 through 4. Bass activity exposes
the same four levels plus a fifth `R` mode. Chord activity 0 is not a selectable
or stored state; `CHORD OFF` owns that meaning.
During manual chord takeover the effective chord activity may temporarily be 0
so the sequencer lane remains closed. In that interval the interface shows no
selected chord-activity button and restores the unchanged stored 1–4 selection
on release. Legacy presets containing chord activity 0 load as level 1.

### RHYTHM-020 — riffs keep independent timing and transpose live

Riff selection reads only the independent bass-riff catalogue and filters by
current rhythm ID and exact chord suffix. Its PPQ timing, durations and
velocities remain unchanged under transposition. Root/tuning changes replace
only the bass pitches; selector changes replace only bass tags. Neither path
may stop/reset transport or edit percussion/automatic-chord tags. Every current
rhythm/chord combination has at least three candidates and every selected riff
fits the reserved bass tag range.

## 16. Summary rule

The complete behavior can be reduced to this rule:

> **When stopped, preset configuration wins. When running, preset changes preserve live tempo, activity, bass voicing, a compatible playing bass riff, the active chord-row octave and the continuous sequencer clock. Transport ON/OFF is user-controlled live state and is never preset state.**
