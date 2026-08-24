# Tuning Design

## Startup

Tuning coupling always starts enabled.

The coupling state is live UI state and is never stored in presets.

## Coupled mode

OMNI and MIDI share one tuning state.

Changing tuning from either screen must immediately update:
- the displayed value in both screens
- generated note frequencies

## Decoupled mode

OMNI and MIDI maintain independent tuning states.

Changing one does not affect the other.

## MIDI note conversion

Incoming MIDI notes are converted to AMY fractional pitches according to the active MIDI tuning state before wire commands are generated.
