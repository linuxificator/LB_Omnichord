# Preset Design

## Separation

OMNI and MIDI presets are separate files and separate code paths.

OMNI presets own chord rows, selected chord/strum/bass instruments, sparse
instrument overrides, volumes, rhythm configuration and tempo, tuning mode and
reference, OMNI reverb state, and the strum traversal mode (`APG` or `LDR`).
Older presets without `strum_mode` load as `APG`. `rhythmRunning` is live
transport state and is never stored or restored. See `rhythm_bahavior.md` for
live-switch semantics.

While rhythm transport is running, an OMNI preset switch preserves the live
tempo, percussion activity, chord activity, bass activity and bass voicing.
It also preserves the octave of the active chord row. The destination preset
still supplies the octaves of every non-active row. With transport stopped,
all of these values load normally from the destination preset.

All three stored activity values use the visible range 1 through 4. A legacy
preset containing chord activity 0 loads as level 1; disabling automatic
chords is live `CHORD ON/OFF` state, not a preset activity value.

The active chord identity, chord gate and physical chord-button hold state are
also live performance state. Selecting an OMNI preset preserves them. The same
row/root therefore remains active across the switch, while its sounding notes
are recalculated from the destination preset's chord type, inversion and
tuning. Its row octave also comes from the destination preset while transport
is stopped, but remains live performance state while transport runs. A held or
rhythm-driven chord may change voicing during that transition, but it must not
be left silent and its later button release must still release the active
manual voice.

OMNI master volume and mute are live output state, not preset state. They
survive OMNI preset switches and are not serialized.

## MIDI preset contents

A MIDI preset stores:

- six instrument definitions
- parameters
- volumes
- MIDI channels
- MIDI reverb level, liveness, damping and drum inclusion
- MIDI tuning mode/reference

The tuning link/coupling state is runtime-only and is not stored.
MIDI master volume and mute are also runtime-only and survive MIDI preset
switches.

MIDI CC bindings follow target ownership: MIDI targets are stored in MIDI
presets and OMNI targets in OMNI presets under the optional
`midi_control_bindings` field. Learn selection, blue unlink timers and visible
indicator LRU state are never preset state. See `midi_control.md`.

During a runtime preset switch, a numeric target controlled by MIDI keeps its
current live value instead of accepting the destination preset value. The
protected set is the union of bindings active before the switch and bindings
declared by the destination preset. Startup preset loading is not a live switch
and may initialize every value normally. Section `RST` applies the same rule:
it restores the preset instrument, volume and unbound parameters, while bound
parameter and volume values remain under MIDI authority. Hidden
instrument-specific target values are protected without forcing that
instrument to become selected.

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
