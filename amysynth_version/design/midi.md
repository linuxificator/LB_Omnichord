# MIDI Design

## Routing

USB MIDI input is received on the Raspberry Pi and translated into AMY wire commands.

Each MIDI row has:

- instrument
- MIDI channel
- parameters
- volume

Default channels are 1-6. Duplicate channel assignments are allowed.

## Pitch handling

Incoming MIDI notes are converted using the active tuning configuration before generating AMY commands.

## Separation

MIDI audio routing is separate from Omnichord routing. MIDI must not reuse Omnichord synth instances or effect buses.
