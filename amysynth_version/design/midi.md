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

On Linux the frontend currently reads ALSA raw-MIDI character devices directly
from the configurable `/dev/snd/midiC*D*` glob on a background thread. It parses
Note On, Note Off, velocity-zero Note Off and running status. System real-time
bytes are ignored; SysEx, CC and Program Change are not application inputs.
Channel 0 in a row means omni/all incoming channels.

ALSA Sequencer-only applications such as VMPK do not create a raw-MIDI device.
For current local testing, load `snd-virmidi` and connect VMPK to a Virtual Raw
MIDI port. Direct ALSA Sequencer subscription is not implemented yet.

## Pitch handling

Incoming MIDI notes are converted using the active tuning configuration before generating AMY commands.

The active chord supplies the intonation root; without an active chord the
fallback root is C. EQ at A=440 maps an incoming note to the same AMY note.
HARM/JV apply the selected table's frequency factor and normally produce a
fractional AMY note for non-root intervals. A root such as C4/60 over C remains
exactly 60 by design. Note-off uses the tuned pitch remembered at note-on.

## Separation

MIDI audio routing is separate from Omnichord routing. MIDI must not reuse Omnichord synth instances or effect buses.

MIDI drums use bus 10. The pink MIDI reverb section programs all six MIDI row
buses with one shared user setting and includes bus 10 only when DRM is enabled.
The similarly shaped OMNI reverb control is independent.

Each pitched MIDI synth has four voices. Both external MIDI and preview notes
are tracked by source note. The preview strum explicitly releases its oldest
live preview note before exceeding four notes; it must not rely on AMY voice
stealing or AMY's finite forgotten-note pool.

## Patch parameters

The numeric UI state is not automatically an AMY override. MIDI uses the same
`SynthState.transport_payload()` contract as OMNI: controls equal to a patch's
native value are omitted, while application corrections and actual edits are
sent explicitly. This prevents a visible default slider value from overwriting
internal Juno/DX7 patch state merely because a preset was loaded.
