# Independent Omnichord bass riffs

Status: authoritative musical data contract

The executable catalogue is
`../../qt_frontend/music/omnichord_bass_riffs.json`. Chord IDs come from
`../../qt_frontend/music/chords.csv`; rhythm IDs come from
`../../qt_frontend/music/rhythms.json`. Runtime behavior is specified in
[`rhythm.md`](rhythm.md), [`../gui/contract.md`](../gui/contract.md) and
[`presets.md`](presets.md).

## Critical architectural/music constraint

The existing `rhythms.json -> bass_levels` data is deliberately **not used** to construct these riffs.

Those existing bass levels are the current simple accompaniment bass. The riff
subsystem is an *additional, independent musical layer*. Its implementation
must not:

- selecting a `bass_level`;
- copying `bass_levels` event times;
- mapping riff notes onto `bass_levels`;
- treating a riff as a higher simple `bass_levels` pattern; the visible `R`
  selector may still use bass-activity state value 5;
- quantizing a riff back onto the existing bass-level trigger locations.

Each riff already contains its own complete note-on timing in PPQ ticks.

## Catalogue size and guaranteed coverage

- rhythms: **54**
- chord suffixes: **36**
- rhythm/chord combinations: **1944**
- riffs: **1664**
- minimum candidates for any rhythm/chord combination: **5**
- maximum candidates for any rhythm/chord combination: **10**
- combinations with fewer than 3 candidates: **0**

This means the catalogue already exceeds the hard requirement of at least one riff for every current rhythm/chord combination, and also meets the preferred target of at least three candidates everywhere.

## Normalization and transposition

Every riff is normalized to **C** and anchored at MIDI **C2 = 36**.

For each event:

```text
actual_midi =
    normalized_anchor_midi
  + pitch_offset_semitones_from_C2
  + chord_root_semitones_from_C
```

Example:

- stored event offset = `7` (G relative to C2)
- played chord root = E (`+4`)
- resulting pitch = B2 (`36 + 7 + 4 = 47`)

Octave placement may be adjusted later by an explicit bass-octave control, but the interval structure of the riff must not be rewritten during ordinary transposition.

## Scale vocabulary

The user asked for twelve named scale/modal patterns rather than only major/minor. The JSON therefore defines a fixed 12-entry vocabulary:

1. C Ionian (major)
2. C Dorian
3. C Phrygian
4. C Lydian
5. C Mixolydian
6. C Aeolian (natural minor)
7. C Locrian
8. C harmonic minor
9. C melodic minor (ascending form)
10. C whole-tone
11. C diminished (whole-half)
12. C blues

The first seven are the traditional diatonic modes. Harmonic minor, melodic minor, whole-tone, diminished and blues extend the vocabulary so altered, diminished and augmented chord types can be labelled honestly. A riff can list multiple compatible scales. Explicitly marked chromatic approach notes may fall outside the listed scale; the stable structural tones do not.

## Chord compatibility

`compatible_chords` uses the **exact suffix IDs** from `chords.csv`; do not invent aliases in the selection core.

Examples:

- `major7`
- `minor7_flat5`
- `dominant7_flat9`
- `dominant7_sharp11`
- `7_sus4`

The catalogue is deliberately conservative. For example:

- perfect-fifth riffs are not offered to chords whose defined fifth is altered away from G;
- flat-five riffs explicitly target chord types containing the tritone;
- augmented-five riffs target chord types containing the augmented fifth;
- major/minor third riffs require that third to exist in the chord;
- three root/octave/chromatic-root families remain available even for exotic chord types.

## Rhythm compatibility

`compatible_rhythms` also uses exact IDs from the current rhythm catalogue.

The rhythm label or category must not be used as the persistent key. Use the ID.

Examples:

- `pop_8`
- `jazz_swing`
- `twelve_eight_blues`
- `salsa`
- `afro_cuban_6_8`
- `seven_four_funk`
- `eleven_eight`

## Phrase length

`phrase_bars` is rational, not floating-point.

Examples:

```json
{"numerator": 1, "denominator": 1, "display": "1"}
{"numerator": 2, "denominator": 1, "display": "2"}
{"numerator": 1, "denominator": 2, "display": "1/2", "meter_fraction_display": "6/12"}
```

Most riffs are one bar; several melodic families are two bars; short chromatic turns are half-bar only where the meter divides cleanly in half.

## Timing representation

The catalogue uses:

```text
PPQ = 96
```

Each riff contains:

- `phrase_ticks`
- ordered event `tick`
- `duration_ticks`
- pitch offset
- velocity
- musical role

No floating point timing is required at runtime.

The backend can convert PPQ ticks to the already-running rhythm sequencer timebase using the effective live tempo. Live rhythm continuity rules from the existing design remain in force: adding/changing a bass riff must not stop or reset transport.

## Selector data contract

A simple selector can:

1. read current `rhythm_id`;
2. read current chord root and exact chord suffix;
3. filter riffs where:
   - `rhythm_id in compatible_rhythms`; and
   - `chord_suffix in compatible_chords`;
4. optionally prefer riffs whose `compatible_scales` match a chosen tonal colour;
5. select the requested authored `activity_rank` (`1..5`), retaining a
   compatible stable riff ID where possible and using `selection_weight` only
   to make a deterministic choice among candidates at that rank;
6. transpose from C to the current chord root;
7. schedule the riff's own PPQ events.

Do not make scale matching mandatory unless the UI later exposes a scale/mode choice. The chord suffix filter is sufficient to guarantee a musically intentional candidate.

## Behavior on a chord change

The catalogue itself does not dictate one implementation. The adopted runtime
policy preserves transport and the sequencer timebase, retains a compatible
playing riff by stable ID, and otherwise uses the preset/default selector.
Future bass events are replaced immediately at the current sequencer phase.
The underlying musical safety rules remain:

- preserve transport and sequencer timebase;
- choose a compatible riff for the new chord/rhythm;
- transpose to the new root;
- use an explicitly designed lane-local replacement boundary;
- do not mutate the riff's internal rhythm.

If a future product decision allows immediate mid-phrase replacement, that must still be implemented as a lane-local event replacement and not as transport restart.

## Source/research policy

External sources were used to establish conventional bass vocabulary: roots/fifths/octaves, sixths, boogie/blues, walking-bass chord tones and chromatic approaches, bossa/Latin root-fifth figures, country, reggae, funk and cumbia articulation.

MuseScore was also searched. Public-domain/traditional examples were used only as meter/phrase sanity checks. All-rights-reserved or commercially recognizable scores were **not** transcribed into this database.

Therefore every catalogue item is marked:

```text
provenance = original_theory_derived
```

This is intentional. Do not replace original patterns with note-for-note copyrighted bass lines just because a score or tab can be found online.

## Important data fields

Per riff:

- `index`: unique stable integer
- `riff_id`: unique stable string ID
- `name`: human-readable name
- `normalized_root`: always C
- `normalized_anchor_midi`: C2 / 36
- `compatible_scales`: one or more of the 12 defined scale IDs
- `compatible_chords`: exact current Omnichord chord suffix IDs
- `compatible_rhythms`: exact current Omnichord rhythm IDs
- `meter`
- `phrase_bars`
- `timing.ppq`
- `timing.phrase_ticks`
- `timing.events[]`
- `articulation`
- `selection_weight`
- `source_refs`
- `provenance`

## Runtime regression requirements

Tests must prove at minimum:

1. the JSON parses;
2. riff `index` values are unique;
3. `riff_id` values are unique;
4. every referenced rhythm ID exists in `rhythms.json`;
5. every referenced chord suffix exists in `chords.csv`;
6. every referenced scale ID exists in `scale_vocabulary`;
7. every event tick lies inside its phrase;
8. every event duration is positive;
9. every current rhythm/chord combination has each authored activity rank
   `1..5`;
10. preserve the present stronger invariant of **5..10 total candidates** per
    context;
11. transposition changes pitch only, never event timing;
12. the riff subsystem does not read `bass_levels` to create or modify riff events;
13. live riff changes do not stop/reset the AMY sequencer or affect drum/chord lanes.

## Current runtime choices

The current runtime owns the GUI, the fixed five-position selector, preset
rank storage, immediate lane-local replacement and AMY tag allocation as
described by the authoritative documents above. A selector value is an
authored activity rank, not a position in a changing candidate list. This
makes the same control mean progressively denser and more adventurous material
for every rhythm and chord while stable riff IDs still prevent unnecessary
changes during compatible live transitions. Synth selection remains the
existing bass-role responsibility.

The four simple activity levels select pitch source independently of timing:
APG uses the active chord-tone collection and LDR uses the existing audited
chord-specific ladder collection. They do not follow individual strum gestures
and do not copy timing from the independent riff catalogue.

The catalogue contains TB-303 articulation annotations. The loader retains
them without changing ordinary-bass behavior; their bass-only interpretation
and conservative accent-on-slide limit are specified in [`tb303.md`](tb303.md).

The invariant is: **a bass riff is its own musical phrase, with its own
rhythm**. It must not be collapsed into the simple bass accompaniment.
