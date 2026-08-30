# Runtime Behavior

## Screen switching

Switching OMNI/MIDI is display-only. Existing notes, rhythms, drums, and sequences continue unchanged.

## MIDI preview

The MIDI strum is a preview instrument. It uses the selected MIDI row instrument and MIDI routing, not the Omnichord strum synth.

Preview note lifetime is bounded by the selected row's four-voice allocation.
Before another onset would require AMY voice stealing, the oldest preview note
is explicitly released. The renewed tail timer releases only notes that remain
active, so delayed note-offs cannot overflow AMY's forgotten-note pool.

## One-shot drums

Tiny and Gamma9001 drum hits use four direct-PCM voices. Their samples must
finish naturally: the host does not synthesize early note-offs merely to retire
AMY's voice bookkeeping. Reusing those voices can consequently fill AMY's
finite forgotten-note diagnostic pool during a long rhythm. The drum synth
sets `SYNTH_FLAGS_NO_NOTE_WARNINGS`; that flag suppresses only inapplicable
note-bookkeeping messages and must not change voice stealing, PCM rendering or
the explicit all-off sent when rhythm transport stops.

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
