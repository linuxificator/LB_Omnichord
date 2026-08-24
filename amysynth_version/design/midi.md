# MIDI Design

## Routing

USB MIDI input is received on the Raspberry Pi and translated into AMY wire commands.

Each MIDI row has:

- instrument
- MIDI channel
- parameters
- volume
- its own AMY bus (4 through 9)

Default channels are 1-6. Duplicate channel assignments are allowed.

## Pitch handling

Incoming MIDI notes are converted using the active tuning configuration before generating AMY commands.

## Separation

MIDI audio routing is separate from Omnichord routing. MIDI must not reuse Omnichord synth instances or effect buses.

MIDI drums use bus 10. The pink MIDI reverb section programs all six MIDI row
buses with one shared user setting and includes bus 10 only when DRM is enabled.
The similarly shaped OMNI reverb control is independent.

## Patch parameters

The numeric UI state is not automatically an AMY override. MIDI uses the same
`SynthState.transport_payload()` contract as OMNI: controls equal to a patch's
native value are omitted, while application corrections and actual edits are
sent explicitly. This prevents a visible default slider value from overwriting
internal Juno/DX7 patch state merely because a preset was loaded.
