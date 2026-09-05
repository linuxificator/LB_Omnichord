# Codex handover — Gamma9001 drum activity refresh

Status: **data authored and validated; materialization into the canonical runtime JSON is the next bounded step**  
Repository: `linuxificator/LB_Omnichord`  
Branch: `feature/gamma9001-drum-pattern-refresh`  
Target subsystem: active `amysynth_version` only  
Date: 2026-09-05

## 1. User intent

Replace the current comparatively sparse/flat drum activity catalogue with a new set covering all existing rhythm types and all five percussion activity levels.

The user explicitly requires:

- all current rhythm IDs remain covered;
- five activity levels remain;
- activity level 1 must no longer be an unusably empty skeleton;
- Gamma9001 is now the default and should be the **musical quality reference**;
- the richer Gamma9001 palette may be used wherever the existing logical-role architecture supports it;
- do not invent stylistically arbitrary percussion;
- levels 4 and 5 may be substantially more colorful;
- level 5 remains a repeating groove, **not an automatic fill**.

## 2. Architectural decision

Do **not** undo the existing split between timing and kit realization.

Canonical timing continues to contain only:

- tick;
- logical role;
- velocity.

Concrete Gamma9001/Tiny/GM choices continue to live in the kit-specific instrument JSONs.

The important change in authoring policy is:

> **Gamma9001 sets the musical quality bar. Tiny compatibility is a degradation path, not an authoring constraint.**

Do not simplify a Gamma9001-capable groove merely because Tiny realizes a role with a surrogate. As long as the existing logical role resolves for Tiny, Gamma9001 and General MIDI, it is valid to use that role in timing.

No new logical roles were introduced in this refresh. The complete existing 21-role interface is reused.

## 3. Files staged with this handover

Temporary transport files are placed next to this handover under:

`amysynth_version/design/rhythm_rework/new_patterns/`

- `drum_activity_timing.refresh.json.gz.b64.part1`
- `drum_activity_timing.refresh.json.gz.b64.part2`
- `drum_activity_timing.refresh.json.gz.b64.part3`
- `drum_activity_timing.refresh.json.gz.b64.part4`
- `materialize_gamma9001_drum_refresh.py`

The payload is a lossless gzip+base64 transport encoding of the complete replacement JSON.

Decoded canonical JSON SHA-256:

`e7d3e14374d90a290fc19fa6f202c0776cccc299ce301b68fdc96af40877f0fc`

Staging text SHA-256:

`fdcef143285eac273ee05d93d8121ae371e133894acf77ccee78b0da15a213d1`

The staging files exist only because the handoff channel cannot safely write the ~855 KiB reviewed JSON through GitHub's text-content connector in one operation. **They are not a new runtime format and must not become a second authority.**

## 4. Materialization procedure

From the repository root on this branch:

```bash
python amysynth_version/design/rhythm_rework/new_patterns/materialize_gamma9001_drum_refresh.py --check
python amysynth_version/design/rhythm_rework/new_patterns/materialize_gamma9001_drum_refresh.py
```

The second command must:

1. decode and SHA-verify the payload;
2. validate the structural musical-data invariants;
3. replace:
   `amysynth_version/qt_frontend/music/drums/drum_activity_timing.json`
4. update the drum timing hash in:
   `amysynth_version/design/rhythm_rework/new_patterns/canonical_drum_data_manifest.json`
5. update the drum timing provenance hash/process in:
   `amysynth_version/qt_frontend/music/catalogue_provenance.json`

After the canonical file is materialized and tests pass, delete the temporary staging payload parts and materializer:

```bash
rm amysynth_version/design/rhythm_rework/new_patterns/drum_activity_timing.refresh.json.gz.b64.part*
rm amysynth_version/design/rhythm_rework/new_patterns/materialize_gamma9001_drum_refresh.py
```

Do **not** retain the compressed payload as a parallel data source. T02 established `qt_frontend/music/drums/` as the single runtime authority.

## 5. Catalogue invariants already validated

The decoded replacement data has:

- exactly **54 rhythm IDs**;
- exactly **5 complete activity patterns per rhythm**;
- level numbers exactly `1..5`;
- only the existing logical-role vocabulary;
- every tick even at 96 PPQ, so conversion to AMY 48 PPQ is exact;
- every event inside its rhythm period;
- velocities in `1..127`;
- activity levels cumulative by `(tick, role)`;
- maximum complete-pattern size **56 events**;
- no level exceeds the existing percussion lane capacity;
- every level-1 pattern has at least **5 events**;
- every level-1 pattern uses at least **2 distinct logical roles**.

The maximum 56-event level occurs at level 5 for:

- `pop_16`
- `punk`
- `metal`
- `funk`
- `jazz_funk`
- `drum_and_bass`
- `trap`

Do not add a single onset to those level-5 patterns without first removing/reworking another onset or changing the explicitly documented sequencer capacity.

## 6. Level semantics

### Level 1 — foundation

This is now a **restrained but complete accompaniment groove**.

It must already communicate both meter and style. It must not revert to "kick only" or another diagnostic skeleton.

Examples of the intended principle:

- pop/rock: kick + backbeat + restrained timekeeper;
- 6/8 ballad: low anchor + backbeat + 6/8 timekeeper;
- jazz swing: ride/sustain pulse + foot closure + light low anchor;
- house: four-on-the-floor + backbeat + offbeat timekeeping;
- Latin: defining timeline/hand/low relationship;
- reggae: one-drop-oriented complete groove;
- odd meters: explicit grouped accents plus a usable timekeeping pulse.

### Level 2 — core groove

Adds characteristic offbeats, subdivisions, pickups, secondary lows or hand-percussion relationships.

### Level 3 — normal

Normal accompaniment density. Adds the genre's ordinary hat/ride/shaker motion, ghost notes or supporting pulse.

### Level 4 — active

Adds style-appropriate color: open/foot hats, ride/bell functions, hand percussion, dry rim/click detail, syncopated secondary low pulses or brighter accents.

### Level 5 — maximum activity

Adds controlled tonal, ghost, cymbal, hand or electronic detail.

**Hard rule:** this remains a stable repeating groove. Do not turn it into a periodic fill. Explicit fills remain owned by `drum_fills_timing.json`.

## 7. Musical basis

These are original LB accompaniment patterns based on established genre idioms, not note-for-note copies of commercial recordings.

The design intentionally uses familiar conventions:

- pop/rock/punk/metal/soul: conventional kick/backbeat relationship with density-appropriate quarter/eighth/sixteenth timekeeping;
- shuffle/blues/jazz: triplet or swing subdivision; jazz favors ride/foot and light comping rather than a rock backbeat;
- disco/house/techno/trance: four-on-the-floor foundation, backbeat/clap and offbeat/open-hat development;
- hip-hop/boom-bap: syncopated kick with beats-2-and-4 backbeat;
- dubstep/trap: common half-time backbeat organization; fast hat/electronic detail is reserved for higher levels;
- bossa/samba/salsa/cha-cha/mambo/merengue/cumbia/bolero/Afro-Cuban: timeline, shaker and hand-drum functions are used where idiomatic;
- `son_clave_3_2` and `rumba_clave_3_2`: explicit two-bar 3-2 timelines are retained, with the rumba third stroke displaced relative to son;
- reggae: level 1 is one-drop-oriented; upper levels add restrained steppers/rockers color;
- odd meters use explicit grouping:
  - 5/4 = 3+2 quarter-note groups;
  - 7/8 = 2+2+3 eighth-note groups;
  - 9/8 = 2+2+2+3;
  - 11/8 = 3+3+3+2;
  - 7/4 funk = 4+3.

Do not "improve" these by sprinkling random Gamma samples. Richness must remain subordinate to the style.

## 8. Gamma9001 use

Do not edit Gamma9001 patch/sample IDs into the timing file.

Continue resolving roles through:

`amysynth_version/qt_frontend/music/drums/drum_activity_instruments_gamma9001.json`

Existing Gamma profiles already provide style-dependent realization through:

- TR-808;
- TR-909;
- Linn 9000;
- Tokyo Synthetics;
- 80s Power Kit;
- Percussion/Latin patch 390;
- the existing jazz/reggae profile variants.

The refresh deliberately uses more of the already-supported roles such as:

- `sustain_primary`
- `sustain_bell`
- `section_accent`
- `tonal_low/mid/high`
- `timeline_primary`
- `texture_shaker`
- `hand_low/high/accent`
- `dry_click`
- `electronic_detail`

This is how Gamma9001 becomes more colorful without coupling timing to concrete sample IDs.

## 9. Tiny compatibility

Tiny must remain loadable/resolvable unless the user explicitly changes that product requirement later.

But Tiny no longer defines what may be composed.

If a timing role maps to a Tiny surrogate, that is acceptable and preferable to weakening the Gamma9001 arrangement. Do not rewrite a musically correct Gamma-oriented pattern merely to make the Tiny surrogate sound as rich as Gamma.

Do not introduce a separate Tiny timing catalogue.

## 10. Existing behavior that must not change

This task is drum **data**, not a transport redesign.

Preserve:

- five complete activity alternatives selected directly;
- AMY wire-only frontend boundary;
- live rhythm continuity;
- no sequencer timebase reset on activity/rhythm/preset changes;
- percussion-lane isolation;
- fill subsystem and its 270 fills;
- fill continuation policy;
- bass and automatic-chord lanes;
- current kit resolver architecture;
- current 56 percussion onset-tag capacity;
- current 96 PPQ data / exact 48 PPQ conversion.

Do not modify the Sonic Pi tree.

## 11. Required tests after materialization

At minimum run the existing drum catalogue tests:

```bash
cd amysynth_version/qt_frontend
python tests/test_drum_patterns.py
```

Then run the maintained frontend suite according to `design/testing.md`.

In addition, verify explicitly:

1. 54 rhythms;
2. five levels each;
3. each level <=56 events;
4. every level-1 pattern >=5 events;
5. every level-1 pattern >=2 distinct roles;
6. levels remain cumulative by `(tick, role)`;
7. all Tiny/Gamma9001/General-MIDI role resolutions succeed;
8. Gamma9001 direct-PCM resolution succeeds for every used role;
9. kit selection does not change timing;
10. activity level 5 does not invoke or embed fills.

The existing `test_drum_patterns.py` already covers the most important runtime resolution, exact event emission, kit independence and direct Gamma PCM realization. Add a small focused regression assertion for the new foundation-richness rule if it is not already present by the time this branch is resumed.

## 12. Review checklist for listening

Automated validation proves structure, not taste. Before merging, audition at least levels 1, 3 and 5 for each broad family:

- pop/rock;
- shuffle/jazz;
- funk/soul;
- four-on-the-floor electronic;
- breakbeat/DnB;
- hip-hop/trap/dubstep;
- Brazilian;
- salsa/Afro-Cuban;
- reggae/Caribbean;
- odd meter.

Specifically reject:

- level 1 that sounds like a metronome or diagnostic skeleton;
- level 5 that sounds like a fill every bar;
- excessive simultaneous cymbal layers;
- random tom runs;
- Latin patterns whose timeline is obscured by decorative percussion;
- jazz patterns that turn into rock backbeats;
- trap/DnB density that exceeds the accompaniment role and masks strum/chords.

Listening refinements may change velocity or remove/reposition events, but must retain all hard structural constraints.

## 13. Definition of done

This handover is complete when:

- the decoded JSON is the canonical runtime `drum_activity_timing.json`;
- manifest and provenance hashes match `e7d3e14374d90a290fc19fa6f202c0776cccc299ce301b68fdc96af40877f0fc`;
- temporary `.b64.part*` and materializer files have been removed;
- all drum tests pass;
- full maintained frontend tests pass;
- no architecture or transport behavior was changed;
- listening review finds level 1 useful and levels 4/5 richer without becoming fills;
- final commit hash and test evidence are recorded in this handover or a successor result handover.
