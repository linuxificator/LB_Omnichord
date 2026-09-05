# Codex handover — Gamma9001-first drum fill refresh

Status: **canonical fill data regenerated against the refreshed drum grooves; focused and full unit validation passed**

Repository: `linuxificator/LB_Omnichord`
Branch: `feature/gamma9001-drum-pattern-refresh`
Active implementation: `amysynth_version` only. Sonic Pi remains frozen.

## Intent

The previous 270 fills were authored against the older drum activity catalogue and no longer sat naturally inside the richer Gamma9001-first grooves. This change replaces fill timing and continuation policy while preserving the existing five-F-button behavior, wire-only frontend architecture and nested AMY sequencer implementation.

## Hard architecture rules

- `drum_activity_timing.json` remains the authority for repeating groove timing.
- `drum_fills_timing.json` contains only kit-independent tick/role/velocity fill data.
- Concrete sounds remain in the three fill instrument realization files.
- Gamma9001 is the musical quality reference.
- Tiny exists for compatibility/tests only; its missing colour is accepted degradation and must never reduce authored Gamma9001 vocabulary.
- Fill realization uses the same per-rhythm profile assignment as the corresponding base groove for every kit family.
- Musical fill policy stays in LB Omnichord; AMY owns only generic nested-sequencer mechanics.

## Musical construction

All 54 rhythms still have exactly five fills (270 total). Each fill starts from the matching final window of the current level-3 refreshed groove, retains selected groove anchors, then overlays genre-specific transition vocabulary.

Fill start rotation is deliberately preserved. In ordinary 4/4, one-beat fills rotate through beats 2 and 4 and half-bar fills through beats 1 and 3. Compound meters use dotted-quarter or half-bar positions; odd meters prefer the authored grouping boundaries. Full-bar fills start on beat 1. The base groove remains phase-continuous and resumes immediately when a shorter fill ends.

Electronic fills retain the four-on-the-floor kick where appropriate; jazz can retain ride/foot timekeeping; Latin can retain timeline/shaker and uses the Gamma9001 patch-390 hand-percussion/timbale/conga vocabulary. Pop, rock, funk and breakbeat-family fills replace progressively more of the base groove as the fill becomes larger.

## Gamma9001 / Tiny policy

The Gamma9001 profiles expose TR-808, TR-909, Linn 9000, Tokyo Synthetics, 80s Power Kit and patch-390 percussion. The new fills exploit logical tom, open-hat, electronic-detail, side-stick, hand-percussion, cowbell/accent and timbale/conga functions where musically appropriate. Tiny resolves the same logical roles through surrogates only and is expected to sound less differentiated.

## Validation

The final branch data passed:

- `python tests/test_drum_patterns.py`;
- `python tests/test_catalogue_provenance.py`;
- `python tests/test_sequencer_tags.py`;
- `python tests/run_tests.py --suite unit --coverage` in the project's pinned desktop test environment.

Permanent regression coverage retains the established maximum 10-event fill-root rotation cycle and asserts that all fill kit-profile assignments equal the corresponding base-groove assignments.

## Canonical hashes

- `drum_fills_timing.json`: `6efeb1ba54401a02355674c5990ea06c312e13e4eadaeff288330bdc54870c45`
- `drum_fill_continuation_roles.json`: `b235ab5091c1a8c31a6aed7794cb017c220ebfd512ec759fa1a2c9238515735e`
- `drum_fills_instruments_gamma9001.json`: `53110d29d6535f7218bd3386ef26d1d248e7085075a563a42f8efbfed1844047`
- `drum_fills_instruments_tiny.json`: `7550bbc7f52bb4e4ee5c31c087247e9a280460c1cb7722d16f467ad2b93aba00`
- `drum_fills_instruments_general_midi.json`: `c940f8bce950fa62115df3d0486d21c8da0de8d3e2540f6e23b439063611e768`

## Do not regress

Do not author around Tiny limitations. Do not remove fill-start rotation merely to make fills end at a bar. Do not add autonomous fills to activity level 5. Do not use host timers as a musical clock. Do not reset transport or sequencer phase to launch or edit fills.
