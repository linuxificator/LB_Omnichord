# Codex handover — kit-independent drum activity and fill catalogues

## Scope

This handover defines the next drum-data architecture for the AMYsynth Omnichord.

**This task does not implement the feature and does not modify GitHub.**

Repository read-only reference:

- repository: `linuxificator/LB_Omnichord`
- branch: `main`
- commit inspected: `387776cffad7394c1fcf6add1ced5d3e69a8d382`
- current rhythm source: `amysynth_version/qt_frontend/music/rhythms.json`
- current AMY config: `amysynth_version/qt_frontend/config/amy_config.json`
- current sequencer allocation: `amysynth_version/qt_frontend/docs/SEQUENCER_TAGS.md`

The delivered data set consists of **eight JSON files**:

### Drum activity

1. `drum_activity_timing.json`
2. `drum_activity_instruments_tiny.json`
3. `drum_activity_instruments_gamma9001.json`
4. `drum_activity_instruments_general_midi.json`

### Drum fills / intermezzos

5. `drum_fills_timing.json`
6. `drum_fills_instruments_tiny.json`
7. `drum_fills_instruments_gamma9001.json`
8. `drum_fills_instruments_general_midi.json`

The architecture is deliberately symmetric: **one authoritative timing file plus one interchangeable kit-realization file**.

---

## 1. Architectural rule: timing and instruments are separate concerns

This is a hard contract, not a suggestion.

The timing files may contain:

- rhythm/fill IDs;
- meter;
- period/duration;
- allowed start beats;
- leading rest;
- tick;
- logical role;
- velocity/dynamic value.

The timing files must **not** contain:

- AMY PCM preset numbers;
- AMY sample names;
- Gamma9001 patch numbers;
- General MIDI note numbers;
- kit-specific instrument names used as executable mapping data.

The instrument files may contain:

- mapping from logical role to concrete kit sound;
- AMY tiny PCM preset/note;
- Gamma9001 kit patch + GM note;
- General MIDI note number;
- explicit surrogate/fallback information.

The instrument files must **never** move an event, add an event or delete an event.

Changing from tiny to Gamma9001 or General MIDI must therefore change orchestration/timbre only. It must not alter musical timing.

---

## 2. Logical roles are the interface between the files

The timing files address abstract roles such as:

- `low_primary`
- `backbeat_primary`
- `timekeeper_primary`
- `section_accent`
- `tonal_high`
- `timeline_primary`
- `texture_shaker`
- `hand_high`
- `dry_click`

These names describe **musical function**, not a required physical drum.

Example:

```text
timing:
    tick=192
    role=timekeeper_primary
    velocity=62
```

Possible realizations:

```text
tiny jazz:
    closed 808 hi-hat surrogate

Gamma9001 jazz:
    Linn kit, GM ride-note mapping

General MIDI jazz:
    MIDI note 51 = Ride Cymbal 1
```

Codex must not put the selected concrete instrument back into the timing JSON.

---

## 3. Drum activity is redesigned as five actual levels

The current `rhythms.json` already contains five additive `percussion_layers`, but the current UI exposes four percussion activity positions and maps them to catalogue layers `0,1,2,4`.

The new design exposes **five real activity levels**:

| Level | Meaning |
|---:|---|
| 1 | foundation |
| 2 | core groove |
| 3 | normal |
| 4 | active |
| 5 | maximum activity |

In `drum_activity_timing.json`, every level is a **complete pattern**, not merely a delta.

That means code selects exactly one complete event set for the requested activity level.

The levels are density-cumulative by design, but runtime code must not reconstruct level 4 by mechanically concatenating levels 1..4. The selected complete level is authoritative.

### Important intentional change

The old fifth percussion layer in some rhythms functioned partly as a periodic mini-fill.

That concept is removed from activity.

**Activity level 5 is a busy repeating groove, not an automatic fill.**

Fills/intermezzos are now a separate subsystem with their own timing catalogue. This avoids a high activity setting unexpectedly creating periodic fills underneath a manually triggered intermezzo.

---

## 4. Rhythm catalogue coverage

`drum_activity_timing.json` covers all **54 current rhythm IDs**.

Each rhythm has exactly **5 complete activity levels**.

The catalogue uses:

```text
PPQ = 96
```

Every event tick is even, so the conversion to AMY's current 48 PPQ sequencer is exact:

```text
amy_tick = json_tick / 2
```

Do not quantize these events against the legacy `rhythms.json` event grid.

The new activity catalogue is a **design rewrite**, not a byte-for-byte extraction of the old `percussion_layers`. It retains the current rhythm IDs, meters and musical style identities, but normalizes the structure into five complete kit-independent patterns and removes autonomous fill behavior.

---

## 5. Current sequencer capacity remains a hard implementation constraint

At repository commit `387776cffad7394c1fcf6add1ced5d3e69a8d382`, the sequencer tag allocation is:

```text
percussion           0..55       56 tags
bass                56..111      56 tags
automatic chords   112..251     140 tags
spare               252..255       4 tags
```

The new activity timing data was validated so that the largest complete activity pattern contains **56 events**.

Current maximum in the delivered design:

```text
rhythm: eleven_eight
activity: 5
events: 56
```

Therefore this redesign can fit the existing 56-tag percussion lane **for repeating activity patterns**, assuming one onset event consumes one tag as it does today.

Codex must retain a regression test that calculates this from data.

Do not silently truncate a pattern if the capacity is exceeded later.

### Fills are still a separate scheduling problem

The fill catalogue must not be installed as a second permanent percussion range. Only four tags are globally spare.

The implementation of a fill must be percussion-lane-local and must temporarily replace/suppress the relevant normal percussion events without stealing the bass or chord ranges and without resetting transport.

The data files deliberately do not prescribe the final temporary-tag algorithm.

---

## 6. Tiny kit realization

Upstream AMY `pcm_tiny` currently contains exactly **11 base PCM samples**:

- maraca;
- kick;
- four snare variants;
- closed hi-hat;
- open hi-hat;
- low tom;
- dry clap;
- cowbell.

The existing Omnichord already pitch-shifts the low tom to obtain low/mid/high tom functions.

The new tiny instrument files explicitly expose the previously underused maraca (`preset 0`) for shaker/texture functions.

Tiny cannot genuinely provide all of these acoustic roles:

- ride;
- ride bell;
- crash;
- side stick/rim;
- full conga/bongo/timbale family.

Where such functions occur, the tiny JSON marks the mapping as:

```json
"realization": "surrogate"
```

This is intentional and reviewable.

Codex must **not** pretend that a surrogate is the same acoustic instrument. It is simply the best realization available within the tiny ROM constraint.

Tiny remains the target realization for the ESP32-P4 product until a different sample-bank decision is explicitly made.

---

## 7. Gamma9001 realization

Current upstream AMY documents seven GM-mapped Gamma9001 kit patches:

| Patch | Kit |
|---:|---|
| 384 | TR-808 |
| 385 | TR-909 |
| 386 | Linn 9000 |
| 387 | Univox Micro Rythmer 12 |
| 388 | Tokyo Synthetics |
| 389 | 80s Power Kit |
| 390 | Percussion / hand drums / Latin |

The Gamma instrument files use these **GM-mapped kit patches**, rather than baking raw Gamma sample indices into Omnichord timing.

Broad policy used in the data:

- house / techno / trance / disco -> TR-909;
- hip-hop / trap / dubstep -> TR-808;
- garage / breakbeat / drum-and-bass -> Tokyo Synthetics;
- rock / metal / harder odd-meter material -> 80s Power Kit;
- pop / soul / funk / country / generic dance -> Linn 9000;
- jazz/shuffle -> Linn 9000 with ride-oriented GM role mapping;
- Latin / Afro-Cuban / Caribbean -> main Linn drum roles plus patch 390 for timeline/hand-percussion roles.

### Multi-kit Gamma profiles

A Gamma profile may resolve different logical roles to different patch numbers.

For example, a salsa profile can use:

```text
low_primary -> Linn 9000 kick
timeline_primary -> Gamma Percussion claves
hand_high -> Gamma Percussion conga
```

Do not flatten this to a single kit merely because it is easier to code if doing so materially changes the orchestration.

However, actual P4 resource allocation and Gamma9001 flash/blob integration must be verified before enabling Gamma9001 on the target hardware. This handover is data/design, not proof that the current P4 firmware already supports the Gamma sample partition.

---

## 8. General MIDI realization

The General MIDI realization follows the standard channel-10 percussion map, principally keys 35..81.

Examples:

```text
36  Bass Drum 1
37  Side Stick
38  Acoustic Snare
39  Hand Clap
42  Closed Hi-Hat
44  Pedal Hi-Hat
46  Open Hi-Hat
49  Crash Cymbal 1
51  Ride Cymbal 1
53  Ride Bell
56  Cowbell
63  Open Hi Conga
64  Low Conga
65  High Timbale
66  Low Timbale
70  Maracas
75  Claves
```

The General MIDI JSON specifies note numbers and standardized role names, but deliberately does not prescribe a specific GM sample library.

Changing the actual GM soundfont must not require editing timing data.

---

## 9. Fill/intermezzo timing

`drum_fills_timing.json` contains the existing design set of:

```text
54 rhythms × 5 fills = 270 fills
```

Each fill keeps:

- unique index;
- unique ID;
- unique kit-independent name;
- compatible rhythm(s);
- meter;
- duration in beats;
- allowed start beat(s);
- explicit leading rest;
- 96-PPQ event timing;
- velocity;
- style metadata.

The concrete voice field has been removed.

Each event now uses a logical role.

Example:

```json
{
  "tick": 144,
  "role": "tonal_high",
  "velocity": 91
}
```

The corresponding kit-specific fill-instrument file decides whether that becomes:

- a pitched tiny low-tom sample;
- a Gamma tom/conga/etc.;
- a GM high tom.

---

## 10. Syncopated fill starts

The earlier contract remains unchanged.

A fill may be technically scheduled on an integer beat but begin acoustically offbeat.

Example:

```text
allowed start: beat 3
leading rest: 1/2 beat
first audible event: beat 3-and
```

The pre-rest belongs to the fill duration.

Do not delete it and move the technical trigger to an offbeat.

This permits beat-aligned triggering while preserving the audible syncopation.

---

## 11. Kit choice must not affect fill selection

The sequence must be:

```text
current rhythm
    -> select one of that rhythm's five fill IDs
    -> select legal upcoming start beat
    -> read timing/roles
    -> resolve roles through active kit file
    -> schedule
```

Do **not** maintain separate random fill sets for tiny, Gamma and GM.

A fill has one musical identity and one timing identity. Only its orchestration is kit-dependent.

---

## 12. Live continuity and lane isolation

All existing Omnichord live-transport rules remain authoritative.

Playing an intermezzo or changing activity:

- must not issue a full sequencer reset;
- must not stop/restart the rhythm;
- must not reset the timebase;
- must not interrupt bass;
- must not interrupt automatic chords/arpeggios;
- must not modify bass tags;
- must not modify chord tags;
- must be a percussion-lane-local operation.

A kit change while stopped is straightforward.

A future live kit change while transport is running must also be treated as a percussion-only operation unless a documented AMY allocation constraint makes that impossible. Do not hide a transport restart inside a kit change.

---

## 13. Data-loading recommendation

Keep the separation visible in code.

Conceptually:

```text
activity timing loader
fill timing loader
kit realization loader
```

Do not merge the four JSON documents into one giant in-memory configuration object at parse time if that destroys the ownership boundary.

A useful runtime representation is:

```text
TimingEvent:
    tick
    logical_role
    velocity

ResolvedDrumEvent:
    tick
    concrete target resolved from active kit profile
    velocity
```

The resolver must be the only place that knows what `logical_role` means for tiny/Gamma/GM.

---

## 14. Required validation / regression tests

Future implementation must test at least:

### Activity timing

1. all 54 current rhythm IDs exist;
2. every rhythm has exactly five activity levels;
3. levels are numbered exactly 1..5;
4. each level is a complete event set;
5. all ticks are inside the period;
6. all ticks are even at 96 PPQ;
7. every level requires <=56 percussion events/tags with the current allocation;
8. no timing event contains `preset`, `sample`, `midi_note`, `patch` or equivalent concrete-kit data;
9. activity level 5 does not secretly invoke the fill catalogue or embed an autonomous fill mechanism.

### Fills

10. exactly five fills exist for every current rhythm;
11. fill indices and IDs are unique;
12. fill names are unique;
13. event ticks are inside the fill duration;
14. leading rests remain valid;
15. allowed start beats fit the duration/meter;
16. all fill event ticks convert exactly to 48 PPQ;
17. no fill timing event contains concrete kit data.

### Instrument mappings

18. every logical role used by a rhythm resolves in its selected tiny profile;
19. same for Gamma9001;
20. same for General MIDI;
21. tiny PCM presets stay in the available base range 0..10;
22. Gamma kit patches stay in the documented 384..390 range;
23. GM note numbers stay in the supported percussion-map range;
24. selecting another kit does not alter ticks/event counts.

### Runtime isolation

25. activity changes touch percussion only;
26. fill trigger/recovery touches percussion only;
27. bass continues uninterrupted;
28. automatic chords/arpeggios continue uninterrupted;
29. transport/timebase are not reset;
30. no events are silently dropped when a pattern reaches 56 tags.

---

## 15. Files that must remain conceptually authoritative

Do not make `rhythms.json -> percussion_layers` and these new files two competing sources of truth after implementation.

When this design is implemented, Codex must migrate the drum activity subsystem so the new separated data becomes authoritative, then remove/deprecate the old executable percussion representation in a deliberate migration.

Do not keep an unnoticed fallback path that sometimes uses old `percussion_layers` and sometimes the new timing/kit files.

The same applies to the earlier standalone intermezzo JSON: once the split timing + kit files are integrated, there should be one authoritative fill timing source.

---

## 16. Non-goals of this handover

This data package does **not** decide:

- GUI layout for a fifth activity selector position;
- whether kit selection is user-visible;
- whether kit choice is stored in presets;
- automatic fill frequency;
- final fill-tag replacement algorithm;
- whether Gamma9001 will actually ship on the P4;
- how a generic external GM soundfont is loaded;
- exact DSP/level compensation between different kits.

These are implementation/product decisions and must not be guessed silently.

---

## Final Codex rule

**Timing is music. Kit mapping is orchestration. Keep them separate.**

A timing change must be reviewable without any sample-bank knowledge.

A kit change must be possible without changing a single event tick.
