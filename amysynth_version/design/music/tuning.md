# Tuning Design

Status: authoritative tuning contract
Owner: shared OMNI/MIDI tuning subsystem
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-01

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

A static tuning change from either screen must update:

- displayed tuning value in both screens
- generated note frequencies

If either coupled reference has a green MIDI CC binding, MIDI owns the shared
numeric reference. Manual reference setters cannot change it. When coupling is
re-enabled, a bound side is authoritative regardless of which screen's link
was pressed. If both independently bound references differ, coupling is
refused rather than overwriting either MIDI-owned value.

## Decoupled mode

OMNI and MIDI have separate tuning states.

Changing one does not affect the other.

In decoupled mode only the screen whose reference is bound locks its tuning
reference. The other screen remains independently editable.

## Global pitch bend

Pitch bend is transient performance state, not a second tuning reference.
There is exactly one bend value and it is sent through AMY's global `s` field.
The visually identical UP/DOWN controls on both screens operate that same
value, regardless of whether the two static tuning sections are coupled.
A bound or decoupled A-reference never disables those bend controls.

Incoming MIDI Pitch Bend uses its full 14-bit value and AMY's conventional
two-semitone range. It does not change either displayed/stored A-reference and
does not regenerate active or quantized sequence notes. Releasing an on-screen
bend returns the global value to zero; MIDI wheel centre sends zero directly.
Panic and complete initial-state publication also restore zero.

## MIDI conversion

MIDI notes are converted to AMY pitch values using the active MIDI tuning state before generating wire commands.

Conversion includes the A-reference offset and the EQ/HARM/JV intonation table.
The active chord supplies the table root; C is the fallback with no active
chord. Root notes can remain integral in HARM/JV, while non-root intervals are
normally fractional. The tuned note used for note-on is retained for the
matching note-off. These static corrections are encoded in fractional AMY note
values; transient pitch bend remains AMY-global and is never folded into them.
