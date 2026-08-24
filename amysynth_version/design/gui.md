# GUI Design

## Screens

The application has two main views:

- OMNI view: the Omnichord performance interface.
- MIDI view: MIDI instrument setup and preview interface.

The MIDI/OMNI switch changes only the visible UI. It must never stop, reset, or alter active music playback.

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

No watermark is shown on the MIDI screen.

## UI state versus audio state

UI changes must first update application state and then generate AMY wire commands. The GUI never directly manipulates AMY internals.
