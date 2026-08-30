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
seven-octave chord arpeggio. LDR uses an explicitly audited pitch set for every
entry in `music/chords.csv`. Both modes use the same tuning and AMY wire-note
path. The backend owns the selected mode and OMNI presets store it as
`strum_mode`; missing legacy values mean `APG`.

LDR is not a free improviser: every listed pitch is traversed and may sound
prominently. Its mappings therefore follow common chord-scale relationships
with these stricter mechanical-strum rules:

- every pitch class named by the chord must be present;
- a scale degree which contradicts an explicit chord member is excluded, such
  as a flat seventh over a minor-major seventh chord or a third over `7 sus4`;
- common avoid tones are omitted where the chord does not explicitly require
  them: for example the perfect fourth over an ordinary major/dominant chord;
- an explicitly altered dominant does not acquire the opposite alteration
  merely because a complete octatonic/altered scale could contain both;
- complete major, Mixolydian or Dorian scales remain appropriate for 11th/13th
  chords whose symbols explicitly contain those otherwise omitted degrees.

The audited root-relative pitch sets are:

| Chord suffixes | LDR degrees |
| --- | --- |
| `major`, `major6`, `6_9`, `add9`, `5` | 1 2 3 5 6 |
| `minor`, `minor7` | 1 ♭3 4 5 ♭7 |
| `sus2`, `sus4` | 1 2 4 5 6 |
| `minor6` | 1 2 ♭3 5 6 |
| `minor_add9`, `minor9`, `minor11` | 1 2 ♭3 4 5 ♭7 |
| `dominant7`, `dominant9` | 1 2 3 5 6 ♭7 |
| `major7`, `major9` | 1 2 3 5 6 7 |
| `minor_major7` | 1 2 ♭3 5 6 7 |
| `minor7_flat5` | Locrian natural 2: 1 2 ♭3 4 ♭5 ♭6 ♭7 |
| `diminished`, `diminished7` | whole-half diminished |
| `augmented` | whole-tone |
| `augmented7`, `dominant7_sharp5` | 1 2 3 ♯5 ♭7 |
| `augmented_major7` | Lydian augmented |
| `7_sus4` | 1 2 4 5 6 ♭7 |
| `dominant11`, `dominant13` | Mixolydian |
| `major11`, `major13` | major |
| `minor13` | Dorian |
| `dominant7_flat5` | 1 2 3 ♭5 ♭7 |
| `dominant7_flat9` | 1 ♭2 3 5 ♭7 |
| `dominant7_sharp9` | 1 ♯2 3 5 ♭7 |
| `dominant7_sharp11` | Lydian dominant |
| `dominant7_flat13` | 1 2 3 5 ♭6 ♭7 |

For example, G minor-major 7 uses the melodic-minor-derived subset
`G A B♭ D E F♯`. It includes the chord's F♯ and deliberately excludes F
natural, so LDR does not add a competing flat seventh beside the defining
major seventh.

The audit used the University of Puget Sound
[chord-scale relationship method](https://musictheory.pugetsound.edu/mt21c/HowToDetermineChord-ScaleRelationships.html),
Jamey Aebersold's
[Scale Syllabus](https://www.jazzbooks.com/mm5/download/FREE-scale-syllabus.pdf)
and the melodic-minor mode relationships summarized by
[LearnMusicTheory](https://learnmusictheory.net/PDFs/pdffiles/04-03-02-TheModesOfMinor.pdf).
Those references establish conventional candidate scales; the stricter
mechanical-strum exclusions above remain an LB Omnichord design decision.

The narrow OMNI gap between the rhythm/bass sections and the strum pad shows
the pitch classes available to the current strum gesture. One light-blue round
marker is shown per pitch class, distributed vertically between the APG/LDR
header and the strum-synth section. APG shows the active chord tones and LDR
shows the selected scale tones; no markers are shown while no chord is active.
Note letters are uppercase and use the chord root and interval function for
musical enharmonic spelling (`C`, `E♭`, `G` for C minor, not `C`, `D♯`,
`G`). Scale spellings keep a consistent accidental direction where the scale
permits it; structurally unusual scales may mix accidentals when that is the
musically meaningful spelling.

## Reverb range

The OMNI and MIDI reverb level sliders cover `0.00..3.00`. This is the wet
return gain sent unchanged to the owned AMY buses. Liveness and damping remain
`0.00..1.00`, and both screens keep independent reverb state.

## Master volume

The brown OMNI and MIDI master sliders cover `0.00..1.00` and control the final
gain of their owned AMY buses: OMNI buses 0–3 and MIDI buses 4–10. Their values
and mute states are independent live state and are not preset contents. Mute
writes zero to the owned buses while retaining the slider value; changing the
slider while muted changes that retained value, and unmute reapplies it.
Per-role and per-row volumes remain unchanged, so muting never destroys the
instrument balance selected by the user or preset.

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
with the pinned Omnichord AMY release. A control must not be used as a level
correction when a broken filter/envelope range is the actual cause.

The host-native reference sweep completed on 2026-08-25: 124 WAV files, each
containing MIDI notes 40, 60 and 84, were rendered. The final pass contained no
silent instruments and no clipped samples. `tests/instrument_balance.py`
regenerates the command plan, WAV bank and per-register JSON report.
