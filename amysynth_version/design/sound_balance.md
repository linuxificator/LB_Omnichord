# Sound Balance, User Storage and Performance Controls

## User-writable data

The active user root is `~/.omnichord`. OMNI presets live in
`omni_presets/`, MIDI presets in `midi_presets/`, and editable startup JSON in
`config/`. On first startup the application migrates the former root-level
`pN.json`/`last_preset.json` files and the former `midi/` directory without
overwriting a file already present at the new destination.

All shipped JSON configuration files are copied to the user config directory
when missing. Existing user copies are authoritative and are never refreshed
automatically. Explicit command-line overrides remain highest priority.

## Strum modes

The blue APG/LDR button belongs to the OMNI strum header. APG is the existing
seven-octave chord arpeggio. LDR uses a consonant scale selected by chord
family: major or suspended pentatonic, minor pentatonic, Mixolydian for
dominants, octatonic for diminished/flat-five chords, and whole-tone for
augmented/sharp-five chords. Power chords use major pentatonic. Both modes use
the same tuning and AMY wire-note path.

## MIDI control activity

Raw MIDI Control Change messages establish baselines and show grey radio-style
activity knobs identified by channel and controller. Unbound controls do not
alter musical state. Explicit one-to-one MIDI-learn bindings may route later
genuine changes to numeric controls as specified in `midi_control.md`. Capacity
is calculated from the available width; eligible indicators use genuine-change
LRU replacement and the outgoing knob flashes red twice.

## Physical strings

Karplus-Strong feedback remains the decay control. The strum path applies a
smooth synth-level compensation from MIDI 60 through 96, reaching 10x at the
top. This uses AMY `iV` wire commands supported by the ESP32-P4 build and does
not introduce a host-only synthesis path.

Measured patch-level multipliers attenuate Harpsichord 2 and Orchestral Pad
before the normal role volume is applied. Harpsichord 1 instead uses a stable
4 kHz/1.0-resonance VCF correction, because its imbalance was filter feedback
rather than output level. High Bells receives
the same small compatibility excitation used by other silent resonant factory
patches. These corrections apply identically to OMNI and MIDI roles.

## Balance measurement contract

Every curated OMNI instrument must be rendered at low, middle and high notes
using its catalogue defaults and production wire commands. Captures must record
RMS, peak, crest factor and clipping per register. Corrections belong in the
catalogue or the narrow `patch_compatibility` table and must remain compatible
with the ESP32-P4 tiny-bank AMY build. A control must not be used as a level
correction when a broken filter/envelope range is the actual cause.

The host-native reference sweep completed on 2026-08-25: 124 WAV files, each
containing MIDI notes 40, 60 and 84, were rendered. The final pass contained no
silent instruments and no clipped samples. `tests/instrument_balance.py`
regenerates the command plan, WAV bank and per-register JSON report.
