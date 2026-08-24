# Tuning Design

## Runtime state

Tuning coupling is runtime UI state and is not stored in presets.

Default startup state:

```
tuningCoupled = true
```

## Coupled mode

OMNI and MIDI remain separate tuning sections and separate state owners. When
coupling is enabled, the section in which coupling is turned on synchronizes
its current mode/reference to the other section. While coupled, every later
change invokes the same directional synchronization from the changed section.

A change from either screen must update:

- displayed tuning value in both screens
- generated note frequencies

## Decoupled mode

OMNI and MIDI have separate tuning states.

Changing one does not affect the other.

## MIDI conversion

MIDI notes are converted to AMY pitch values using the active MIDI tuning state before generating wire commands.

Conversion includes the A-reference offset and the EQ/HARM/JV intonation table.
The active chord supplies the table root; C is the fallback with no active
chord. Root notes can remain integral in HARM/JV, while non-root intervals are
normally fractional. The tuned note used for note-on is retained for the
matching note-off.
