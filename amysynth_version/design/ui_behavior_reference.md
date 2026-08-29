# AMY Omnichord UI Behavior Reference

## Purpose

This document collects user interface and interaction decisions for the AMY Omnichord application. It is intended as a behavioral reference for future implementation work and regression testing.

The application is not a generic synthesizer UI. It is a musical instrument interface where immediate feedback, predictable touch behavior, and preserving the original Omnichord playing style are primary goals.

## Design principles

### Direct musical interaction

Controls used during performance must have predictable behavior. A musician should not need to understand internal state machines to play the instrument.

### Separate configuration and performance state

Instrument selection, tuning, rhythm, chord configuration and MIDI settings have explicit state ownership. UI appearance must not accidentally create hidden coupling between features.

### Transport independence

The Qt application generates AMY wire commands only. The UI must not depend on whether AMY runs locally or on ESP32-P4 hardware.

## Screen organization

### OMNI screen

The OMNI screen is the primary performance screen.

Elements:

- chord buttons;
- strum area;
- rhythm controls;
- instrument selection;
- octave controls;
- tuning controls;
- independent OMNI master volume and mute;
- transport and mode controls.

The layout should resemble the original Omnichord concept: large playable areas, minimal precision tapping requirements, and immediate visual feedback.

## MIDI screen

The MIDI screen provides external keyboard and MIDI-oriented control while preserving the same AMY sound generation path.

Rules:

- MIDI must use the same synth concepts as OMNI;
- MIDI and OMNI tuning can be coupled or independent;
- switching screens must not silently modify musical parameters;
- selecting an instrument must fully initialize the selected patch.
- MIDI master volume and mute control only MIDI buses and remain independent
  of the OMNI master.

## Tuning behavior

### Independent mode

When tuning is not linked:

- OMNI tuning state is independent;
- MIDI tuning state is independent;
- changing one never changes the other;
- both screens show their own actual value.

### Coupled mode

When tuning is linked:

- both screens display the same value;
- changing tuning from either screen updates both immediately;
- enabling the link performs an explicit synchronization operation.

The implementation must not use hidden "effective tuning" values selected by the active screen.

## Touch behavior

### Tap

Tap actions should trigger immediately and must not require a second interaction to initialize state.

A chord tap immediately starts the selected notes on the manual chord synth and
releases them on finger-up. It also selects that chord as the active chord for
strum and accompaniment. The accompaniment pitches may update, but the tap does
not temporarily suppress or stop the automatic-chord lane.

### Press and hold

Long presses are used where continuous musical interaction is required.

Examples:

- holding a chord past the tap window selects it for accompaniment and keeps it
  active while temporarily suppressing future automatic-chord onsets;
- holding performance controls must not repeatedly reset state;
- duplicate pointer-down events while a contact is active must not retrigger it.

Any real chord pointer-up stops the directly played manual synth immediately,
including after hold promotion. It has no release-grace timer and is not
quantized to the automatic rhythm lane. Restoring future automatic-chord events
is a separate sequencer-lane update.

Chord keys use Qt's device-independent pointer handling for mouse, touchscreen
and pen input. A desktop trackpad click follows the mouse path; enabling raw
trackpad touch for the complete window is not required for chord input.

### Strum behavior

The strum area is a performance control, not a normal button.

Requirements:

- touch and mouse input behave identically;
- active instrument must already be initialized;
- strum must work immediately after application start and screen selection;
- strum must generate the same AMY commands regardless of transport.

## Rhythm behavior

Rhythm controls must preserve musical continuity.

Rules:

- changing rhythm while playing must not create unrelated chord or note events;
- activity levels represent musical layers, not arbitrary volume controls;
- rhythm state changes must be deterministic and testable.

## Visual design

### Buttons

Buttons used for mode switching must have:

- readable text size;
- centered text horizontally and vertically;
- consistent spacing;
- clear active/inactive indication.

Round preset buttons keep exactly the same diameter during pointer-down and
after selection. Selection is indicated by replacing the ordinary single
border color with white; it does not add an inner/outer ring. The Store button
shares that diameter but uses a visibly darker purple fill. OMNI and MIDI use
the same preset geometry.

### Colors

Colors are used to communicate function:

- green elements indicate active/playable performance areas;
- different functional groups should remain visually distinguishable;
- visual changes should not replace actual state feedback.

The master-volume family uses the brown functional palette. Its center mute
panel is white with black `MUT` text while output is enabled, and black with
white `UMT` text while muted.

### Typography

Labels must remain readable on touch displays. Small decorative text is acceptable only where it does not affect operation.

## Presets

Presets define musical starting points but must not create hidden coupling.

Rules:

- missing values use defined defaults;
- loading a preset must initialize all required runtime state;
- preset loading must not depend on a user changing another control first.

## Testing implications

The following behaviors must be regression tested:

1. Start application and immediately play OMNI.
2. Start application and immediately play MIDI strum.
3. Change instrument and verify immediate sound.
4. Change MIDI tuning while linked and verify OMNI updates.
5. Change OMNI tuning while linked and verify MIDI updates.
6. Disable tuning link and verify independent operation.
7. Re-enable link and verify explicit synchronization.
8. Change rhythm during playback.
9. Switch screens without unintended parameter changes.
10. Verify local AMY and remote AMY produce identical wire command streams.
11. Drive a quick tap and a hold through the real QML chord item and verify
    active-border, note-release and hold-takeover state.

The current exact persistence, MIDI drum, bus-allocation and factory/user
preset rules are no longer open UI questions; their authoritative contracts
are `presets.md`, `midi.md`, `architecture.md` and `sound_balance.md`.
