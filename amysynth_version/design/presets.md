# Preset Design

## Separation

OMNI and MIDI presets are separate files and separate code paths.

OMNI presets own chord rows, selected chord/strum/bass instruments, sparse
instrument overrides, volumes, rhythm configuration and tempo, tuning mode and
reference, and OMNI reverb state. `rhythmRunning` is live transport state and is
never stored or restored. See `rhythm_bahavior.md` for live-switch semantics.

The active chord identity, chord gate and physical chord-button hold state are
also live performance state. Selecting an OMNI preset preserves them. The same
row/root therefore remains active across the switch, while its sounding notes
are recalculated from the destination preset's chord type, octave, inversion
and tuning. A held or rhythm-driven chord may change voicing during that
transition, but it must not be left silent and its later button release must
still release the active manual voice.

## MIDI preset contents

A MIDI preset stores:

- six instrument definitions
- parameters
- volumes
- MIDI channels
- MIDI reverb level, liveness, damping and drum inclusion
- MIDI tuning mode/reference

The tuning link/coupling state is runtime-only and is not stored.

MIDI CC bindings follow target ownership: MIDI targets are stored in MIDI
presets and OMNI targets in OMNI presets under the optional
`midi_control_bindings` field. Learn selection, blue unlink timers and visible
indicator LRU state are never preset state. See `midi_control.md`.

## Factory presets

M1 is the most accessible/mellow preset. Higher numbers progressively introduce more unusual and experimental combinations.

Factory OMNI presets are copied into `~/.omnichord/omni_presets` without overwriting valid
user presets. The recognizable obsolete bootstrap bank—18 byte-identical files
using `prophet`, `pluck`, `fm` and `waltz`—is first moved to a timestamped
`legacy-presets-*` archive and then replaced with current AMY factory presets.
Any non-identical or edited bank is preserved.

MIDI presets use the independent `~/.omnichord/midi_presets` directory.
Older root-level OMNI presets and the former `~/.omnichord/midi` directory are
migrated on startup without overwriting new-layout files.
