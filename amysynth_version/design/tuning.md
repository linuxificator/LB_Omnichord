# Tuning Design

## Runtime state

Tuning coupling is runtime UI state and is not stored in presets.

Default startup state:

```
tuningCoupled = true
```

## Coupled mode

OMNI and MIDI use one shared tuning state.

A change from either screen must update:

- displayed tuning value in both screens
- generated note frequencies

## Decoupled mode

OMNI and MIDI have separate tuning states.

Changing one does not affect the other.

## MIDI conversion

MIDI notes are converted to AMY pitch values using the active MIDI tuning state before generating wire commands.
