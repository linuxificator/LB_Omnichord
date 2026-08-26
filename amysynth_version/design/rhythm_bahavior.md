# Omnichord Rhythm Behavior

This document defines the required behavior of the Omnichord rhythm/drum subsystem. It is a behavioral contract for the GUI, backend, AMY wire-command generation, presets, and regression tests.

The central rule is:

> **When rhythm playback is stopped, stored configuration wins. When rhythm playback is running, playback continuity wins.**

A preset or rhythm selection may change the pattern and other stored rhythm parameters, but it must not unexpectedly start or stop the rhythm, change the currently running tempo, reset the sequencer timebase, or interrupt the beat.

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
3. The new preset may change the rhythm/pattern.
4. Other rhythm parameters from the new preset may be applied if they do not require stopping or resetting the running rhythm transport.
5. The tempo stored in the newly selected preset must **not** replace the effective live tempo during this live transition.
6. The AMY sequencer must remain running.
7. The AMY sequencer timebase must not be reset.
8. No artificial pause, restart, dropped beat, or transport pulse may be inserted.

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
| Select preset | Load preset rhythm and preset tempo; stay stopped | Load preset rhythm; preserve current live tempo; stay running |
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

### RHYTHM-016 — manual chord takeover releases the automatic chord normally

Pressing a manual chord while automatic rhythm chords are enabled must close
the automatic-chord gate before starting the manual chord. Clearing future
sequencer events is insufficient because it also removes the pending note-off
of a synth-4 chord which may already be sounding.

The gate transition must therefore send an immediate velocity-zero note-off to
all active voices of automatic-chord synth 4 before sending the manual synth-3
note-ons. This is an ordinary AMY note-off and must follow the selected patch's
normal release envelope; it must not reset oscillators, patches, effects, the
sequencer or its timebase. Drums and bass continue. A finite release tail may
overlap the manual chord, but the old automatic chord may not sustain after its
release has completed.

## 16. Summary rule

The complete behavior can be reduced to this rule:

> **When stopped, configuration changes may load stored tempo values. When running, pattern changes must preserve the current tempo and continuous sequencer clock. Transport ON/OFF is user-controlled live state and is never preset state.**
