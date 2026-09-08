# Runtime Behavior

Status: authoritative runtime behavior contract
Owner: shared application behavior
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-01

## Screen switching

Switching OMNI/MIDI is display-only. Existing notes, rhythms, drums, and sequences continue unchanged.

## MIDI preview

The MIDI strum is a preview instrument. It uses the selected MIDI row instrument and MIDI routing, not the Omnichord strum synth.

Preview note lifetime is bounded by the selected row's four-voice allocation.
Before another onset would require AMY voice stealing, the oldest preview note
is explicitly released. The renewed tail timer releases only notes that remain
active, so delayed note-offs cannot overflow AMY's forgotten-note pool.

## Presets

OMNI and MIDI presets are separate. MIDI presets contain:

- instrument selection
- parameters
- volume
- MIDI channel
- MIDI-side reverb settings
- MIDI tuning mode/reference

Tuning coupling is runtime state and is never stored in presets.

## AMY communication

All musical actions are translated into AMY wire commands. Local and remote AMY execution must receive identical commands.
