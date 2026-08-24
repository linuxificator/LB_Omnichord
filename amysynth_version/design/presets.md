# Preset Design

## Separation

OMNI and MIDI presets are separate files and separate code paths.

OMNI presets own chord rows, selected chord/strum/bass instruments, sparse
instrument overrides, volumes, rhythm configuration and tempo, tuning mode and
reference, and OMNI reverb state. `rhythmRunning` is live transport state and is
never stored or restored. See `rhythm_bahavior.md` for live-switch semantics.

## MIDI preset contents

A MIDI preset stores:

- six instrument definitions
- parameters
- volumes
- MIDI channels
- MIDI reverb level, liveness, damping and drum inclusion
- MIDI tuning mode/reference

The tuning link/coupling state is runtime-only and is not stored.

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
