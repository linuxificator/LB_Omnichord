# Runtime Behavior

Status: authoritative runtime behavior contract
Owner: shared application behavior
Applies to: `sc_version`
Last verified: 2026-09-14

## Screen switching

Switching OMNI/MIDI is display-only. Existing notes, rhythms, drums, and sequences continue unchanged.

## MIDI preview

The MIDI strum is a preview instrument. It uses the selected MIDI row instrument and MIDI routing, not the Omnichord strum synth.

An external control bound to the OMNI strum is different from the MIDI-screen
preview: it supplies positions to the same OMNI strum instrument and musical
note collection as touch/mouse input. It does not supply velocity and it does
not disable or unlink direct screen strumming.

Preview note lifetime is bounded by the selected row's four-voice allocation.
Before another onset would exceed the configured preview ownership limit, the
oldest preview handle is explicitly released. The engine-owned renewed tail
deadline releases only handles that remain active.

## Presets

OMNI and MIDI presets are separate. MIDI presets contain:

- instrument selection
- parameters
- volume
- MIDI channel
- MIDI-side reverb settings
- MIDI tuning mode/reference

Tuning coupling is runtime state and is never stored in presets.

## Engine communication

All musical actions cross the typed SuperCollider protocol. Musical time and
note lifetime remain in the headless engine, not in Qt/Python. The SC edition
does not produce AMY wire commands or import AMY at runtime.
