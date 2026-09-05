# Codex handover — complete drum catalogue musical audit

Status: **all 54 rhythms, all 270 fills and every allowed fill start reviewed; executable contracts added**

Branch: `feature/midi_osc_improvement`

Date: 2026-09-05

## Scope and interpretation

This was a catalogue-wide review, not an exception scan. Every rhythm was assigned to one explicit musical family, every one of its five activity levels was checked, and every fill start was recomputed from the fill's actual runtime duration.

The patterns are original accompaniment patterns. The sources establish idiom, meter, phrasing, orchestration and dynamics; they are not transcriptions that the catalogue copies.

The automated contracts are in `qt_frontend/tests/test_drum_musical_contracts.py`. They deliberately test observable musical structure rather than labels alone. They also require the audit-family map to cover every catalogue ID exactly once, so a future rhythm cannot silently escape review.

## Source basis

- **Y1 — Yamaha, Music Theory for Producers, Part 1:** conventional kick/backbeat functions, four-on-the-floor, syncopation, triplets and the distinction between simple and compound meters. <https://hub.yamaha.com/proaudio/recording/music-theory-for-producers-part-1/>
- **Y2 — Yamaha, Drumming techniques:** audible reference examples for 8-beat, 16-beat, shuffle, samba and bossa nova, plus rimshot use in bossa nova. <https://www.yamaha.com/en/musical_instrument_guide/drums/play/play003.html>
- **Y3 — Yamaha, Think Like a Drummer, Part 2:** fills as transitions, normally in the last measure and often its second half; stylistic kit compatibility; enough variation and restraint. <https://hub.yamaha.com/proaudio/recording/think-like-a-drummer-part-2/>
- **B1 — Berklee Online, Drum Set Performance 101:** stylistic time, touch, balance and dynamics across R&B, pop-rock, funk, rock, jazz, Brazilian and Afro-Cuban playing, including 2/4, 3/4, 4/4, 6/8, 9/8, 12/8 and 5/4. <https://online.berklee.edu/courses/drum-set-performance-101>
- **B2 — Berklee PULSE, Create Your Own Afro-Latin Groove:** clave, cascara, shaker and bass drum as distinct interlocking roles. <https://pulse.berklee.edu/?id=4&lesson=15>
- **B3 — Berklee, Programming and Producing Drum Beats:** style-appropriate patterns should anchor groove, reinforce form and control energy across acoustic and programmed styles. <https://online.berklee.edu/courses/programming-and-producing-drum-beats>
- **A1 — Ableton, Programming Beats 2: Linear Drumming:** standardized kick, backbeat and hi-hat functions; rock and house foundations; purposeful linear orchestration. <https://makingmusic.ableton.com/programming-beats-2-linear-drumming>
- **A2 — Ableton, Making Music, “On Looseness”:** rigid quantization suits house/techno/EDM, while hip-hop generally benefits from a more organic pattern and dynamic contour. <https://cdn-resources.ableton.com/resources/uploads/makingmusic/MakingMusic_DennisDeSantis.pdf>
- The specialist Drumeo, Native Instruments and MusicRadar references embedded in `drum_fills_timing.json` remain supplementary sources for concrete fill vocabulary. Yamaha and Berklee are now cited by every fill as the authoritative common review basis.

## Catalogue-wide decisions

### Activity identity

The complete five-level activity signatures were compared across all 54 IDs. Three pairs were identical across every level: `pop_8`/`rock`, `jazz_swing`/`jazz_shuffle` and `rnb`/`hip_hop`. They are now separated with small, source-consistent differences instead of decorative random hits:

- rock anticipates beat three with a driving kick while pop 8 remains straight;
- jazz shuffle retains the triplet ride grid but gives its low and soft-backbeat anchors more weight than jazz swing;
- R&B uses a straighter beat-three low anchor while hip-hop retains its late-sixteenth displacement.

Other styles may legitimately share a foundation at low activity—for example the four-on-the-floor family—but their complete five-level catalogues are distinct. A regression now rejects any two IDs whose entire activity catalogues become identical.

### Fill placement

Every fill now ends at the next written bar boundary. This makes all start positions musically transitional and removes starts on beat 1 or 2 that merely interrupted the middle of a bar. The runtime-authoritative formula is:

`start_beat = meter_numerator - duration_ticks / written_beat_ticks + 1`

For odd meters, full- and multi-beat fills begin on the documented group boundaries whenever their duration permits it: 5/4 is 3+2, 7/8 is 2+2+3, 7/4 is 4+3, 9/8 is 2+2+2+3 and 11/8 is 3+3+3+2. A one-beat pickup may start inside the final group because its purpose is specifically to lead into the downbeat.

The old rotating-start policy was removed. Runtime rotation still selects different fills, while each fill itself has one unambiguous phrase-ending position.

### Fill dynamics

Before correction, 3,750 fill events had mean velocity 93.22 and median 102; 2,144 events were at least 100. The complete level-3 groove catalogue had mean 50.68 and median 44. This confirmed that the perceived imbalance was systemic rather than confined to a few fills.

All fill velocities received one proportional `0.82` trim. The proportional operation preserves accents, crescendi and within-fill contrast. After rhythmic de-duplication the 3,738 retained events have mean 76.44, median 84 and maximum 102. This leaves fills energetic relative to light timekeeping while putting their strongest hits near the 80–98 range of normal groove anchors.

### Fill diversity

Different Gamma9001 profiles alone did not guarantee different rhythms: 111 within-rhythm pairs initially had the same duration and onset grid. Each rhythm now has five distinct `(duration, onset contour)` signatures as well as five distinct logical orchestrations and Gamma9001 profiles.

The corrections create deliberate rests and layered accents on the existing rhythmic grid. Straight fills remain straight and triplet fills remain triplet-based; no arbitrary “humanization” timing was introduced. Fills still contain at most 40 events.

### Metadata repair

In 113 fills, the descriptive top-level `duration_beats` disagreed with the runtime-authoritative `timing.duration_ticks`. Several old `leading_rest` descriptions also disagreed with the generated timing. Both copies are now consistent and permanently tested. Runtime behavior had followed `timing.duration_ticks`, but leaving conflicting documentation would make subsequent musical review unsafe.

## Per-rhythm review record

`F3@1(4)` means fill 3 starts on written beat 1 and lasts four written beats. “Pass” means the meter, family anchors, five cumulative complete activity levels, phrase-ending starts, dynamics and five distinct fill contours meet the contracts above.

| Rhythm | Meter | Reviewed idiom/source family | F1–F5 allowed starts and lengths | Result |
|---|---:|---|---|---|
| `pop_8` | 4/4 | pop/rock — Y1,Y2,B1,A1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `pop_16` | 4/4 | pop/rock — Y1,Y2,B1,A1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `slow_ballad` | 4/4 | ballad/backbeat — Y1,Y3,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `six_eight_ballad` | 6/8 | compound ballad — Y1,B1 | F1@4(3) F2@1(6) F3@1(6) F4@4(3) F5@1(6) | Pass |
| `rock` | 4/4 | rock — Y1,Y2,B1,A1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `shuffle` | 4/4 | triplet shuffle — Y1,Y2,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `punk` | 4/4 | energetic rock — Y1,B1,A1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `metal` | 4/4 | energetic rock/metal — Y1,B1,A1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `country_train` | 4/4 | country/train continuity — B1,Y3 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `country_waltz` | 3/4 | country waltz — B1,Y3 | F1@3(1) F2@2(2) F3@1(3) F4@2(2) F5@1(3) | Pass |
| `waltz` | 3/4 | waltz — B1 | F1@3(1) F2@2(2) F3@1(3) F4@2(2) F5@1(3) | Pass |
| `polka` | 2/4 | two-beat dance/march — B1 | F1@2(1) F2@1(2) F3@1(2) F4@1(2) F5@1(2) | Pass |
| `march` | 4/4 | march/rudimental — B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `straight_blues` | 4/4 | straight blues/backbeat — Y1,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `twelve_eight_blues` | 12/8 | compound blues — Y1,B1 | F1@10(3) F2@7(6) F3@1(12) F4@10(3) F5@1(12) | Pass |
| `jazz_swing` | 4/4 | ride/foot swing — Y1,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `jazz_waltz` | 3/4 | jazz waltz — B1 | F1@3(1) F2@2(2) F3@1(3) F4@2(2) F5@1(3) | Pass |
| `jazz_shuffle` | 4/4 | ride/foot shuffle — Y1,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `funk` | 4/4 | syncopated funk — B1,B3 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `jazz_funk` | 4/4 | syncopated jazz-funk — B1,B3 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `soul` | 4/4 | syncopated soul/backbeat — Y1,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `soul_shuffle` | 4/4 | soul shuffle — Y1,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `gospel_6_8` | 6/8 | compound gospel — Y1,B1 | F1@4(3) F2@1(6) F3@1(6) F4@4(3) F5@1(6) | Pass |
| `rnb` | 4/4 | syncopated R&B — Y1,B1,B3 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `disco` | 4/4 | four-on-floor dance — Y1,A1,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `house` | 4/4 | four-on-floor/offbeat hats — Y1,A1,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `techno` | 4/4 | quantized four-on-floor — Y1,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `trance` | 4/4 | quantized four-on-floor — Y1,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `garage_2step` | 4/4 | syncopated breaks — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `breakbeat` | 4/4 | broken backbeat — B3,A1,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `drum_and_bass` | 4/4 | fast broken backbeat — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `dubstep` | 4/4 | half-time backbeat — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `hip_hop` | 4/4 | organic syncopated backbeat — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `boom_bap` | 4/4 | organic syncopated backbeat — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `trap` | 4/4 | half-time with controlled fast detail — B3,A2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `bossa` | 4/4 | bossa kick/cross-stick — Y2,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `samba` | 4/4 | interlocking samba voices — Y2,B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `salsa` | 4/4 | clave/timeline/hand percussion — B1,B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `cha_cha` | 4/4 | timeline/hand percussion — B1,B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `mambo` | 4/4 | timeline/hand percussion — B1,B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `merengue` | 2/4 | fast two-beat Latin roles — B1,B2 | F1@2(1) F2@1(2) F3@1(2) F4@1(2) F5@1(2) | Pass |
| `cumbia` | 4/4 | shaker/low/backbeat interplay — B1,B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `bolero` | 4/4 | restrained Latin ballad roles — B1,B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `tango` | 4/4 | dry articulated dance pulse — B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `son_clave_3_2` | 4/4 | explicit 3-2 son timeline — B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `rumba_clave_3_2` | 4/4 | explicit 3-2 rumba timeline — B2 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `afro_cuban_6_8` | 6/8 | compound interlocking hand/timeline roles — B1,B2 | F1@4(3) F2@1(6) F3@1(6) F4@4(3) F5@1(6) | Pass |
| `reggae` | 4/4 | one-drop foundation — B1,B3 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `calypso_soca` | 4/4 | Caribbean hand/low/backbeat interplay — B1 | F1@4(1) F2@3(2) F3@1(4) F4@3(2) F5@1(4) | Pass |
| `five_four` | 5/4 | 3+2 grouping — B1 | F1@5(1) F2@4(2) F3@1(5) F4@4(2) F5@1(5) | Pass |
| `seven_eight` | 7/8 | 2+2+3 grouping — B1 | F1@5(3) F2@3(5) F3@1(7) F4@5(3) F5@1(7) | Pass |
| `seven_four_funk` | 7/4 | 4+3 funk grouping — B1 | F1@7(1) F2@5(3) F3@1(7) F4@5(3) F5@1(7) | Pass |
| `nine_eight` | 9/8 | 2+2+2+3 grouping — B1 | F1@7(3) F2@5(5) F3@1(9) F4@7(3) F5@1(9) | Pass |
| `eleven_eight` | 11/8 | 3+3+3+2 grouping — B1 | F1@10(2) F2@7(5) F3@1(11) F4@10(2) F5@1(11) | Pass |

## Runtime response contract

Changing fill enablement, order or density replaces the fill scheduler on the next bar boundary, not at the end of its possibly many-bar supercycle. Consequently:

- a fill already running is allowed to finish;
- disabling produces no new fill after the next boundary;
- enabling schedules the first selected fill in the next bar (at its authored phrase-ending position);
- the selected density interval starts from that new bar;
- no host-side sequencer phase or timer is introduced.

The generic tagged-lane compiler retains its former least-common-multiple alignment by default. Only the fill scheduler opts into one-bar replacement alignment, so unrelated bass, chord and arpeggio scheduling behavior is unchanged.

## Validation commands

- `python tests/test_drum_musical_contracts.py`
- `python tests/test_drum_patterns.py`
- `python tests/test_command_plans.py`
- `python tests/test_catalogue_provenance.py`
- `python tests/test_repository_data_hygiene.py`
- `python tests/drum_kit_audio_smoke.py gamma9001` with the matching local AMY build
- `python tests/run_tests.py --suite unit --coverage`

The audio smoke test now passes each fill ID to the resolver, so all fill-specific Gamma9001 realization profiles are exercised rather than only the per-rhythm fallback profile.

## Remaining human acceptance test

Automated tests prove structural correctness, source-backed idiom markers, timing, mapping coverage, non-silence and numeric balance. They cannot prove subjective mix preference. Before merging to `main`, audition representative short, half-bar and full-bar fills across acoustic, electronic, Latin, compound and odd-meter families on the Gamma9001 build.
