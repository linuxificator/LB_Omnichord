# Runtime Behavior

## Screen switching

Switching OMNI/MIDI is display-only. Existing notes, rhythms, drums, and sequences continue unchanged.

## MIDI preview

The MIDI strum is a preview instrument. It uses the selected MIDI row instrument and MIDI routing, not the Omnichord strum synth.

## Presets

OMNI and MIDI presets are separate. MIDI presets contain:

- instrument selection
- parameters
- volume
- MIDI channel

Tuning coupling is runtime state and is never stored in presets.

## AMY communication

All musical actions are translated into AMY wire commands. Local and remote AMY execution must receive identical commands.
