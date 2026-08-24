# GUI Design

## Screens

The application has two main views:

- OMNI view: the Omnichord performance interface.
- MIDI view: MIDI instrument setup and preview interface.

The MIDI/OMNI switch changes only the visible UI. It must never stop, reset, or alter active music playback.

The large lower-left mode switch uses the shared rainbow button on both views.
Its MIDI/OMNI label is centered on the complete visible shape, including the
right-hand extension, and uses 55% of the button height so `OMNI` remains
inside the button at the supported layouts.

## Common controls

The following remain available in both screens:

- Panic button: stops active notes.
- Fullscreen toggle.
- Tuning controls.
- Mode switch.

## MIDI view

The MIDI view contains:

- M1-M18 MIDI presets.
- Six instrument rows.
- MIDI channel selectors.
- Instrument selection.
- Instrument parameters.
- Volume controls.
- MIDI preview strum.
- Independent MIDI reverb controls for level, liveness, damping and drum send.

No watermark is shown on the MIDI screen.

## UI state versus audio state

UI changes must first update application state and then generate AMY wire commands. The GUI never directly manipulates AMY internals.
