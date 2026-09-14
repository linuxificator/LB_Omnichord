# SuperCollider playback qualification

Status: implemented contract and reproducible evidence

Last verified: 2026-09-14 on Linux x86_64 with SuperCollider 3.13.0

## Catalogue boundary

The SuperCollider edition has its own instrument catalogue. It never loads the
AMY patch catalogue. Old AMY keys remain accepted as invisible migration
aliases so existing user presets can open, but the selected and transmitted
identity is always a canonical `sc.*` or `sample.*` program.

The pinned SCLOrk source inventory contains 109 definitions. Compilation and
source audit intentionally cover all of them. The pitched browser is a stricter
boundary:

- 31 raw drum definitions belong to the percussion path, not the pitched
  instrument browser;
- `metalPlate` and `noQuarter` are excluded because float renders expose
  unstable or non-finite output at ordinary musical pitches;
- the remaining 76 SCLOrk definitions are admitted through the checked-in
  playback profile;
- four owned acid voices and 66 canonical VSCO pitched choices complete the
  146 program identities behind the compact `SYN`/`PCM` browser. The PCM
  roller itself stays at 22 families; variant and articulation buttons expose
  every non-duplicate recorded choice.

This separation keeps upstream material inspectable without presenting every
compilable graph as a safe musical instrument.

## SCLOrk measurement and gain staging

`tools/build_sclork_playback_profile.py` consumes raw 32-bit-float NRT reports
at MIDI notes 45, 69 and 81 (A2, A4 and A5). For each eligible definition it
uses the median RMS and worst peak to choose one fixed gain, bounded by:

- target RMS `0.05`;
- peak ceiling `0.65`;
- maximum gain `16`;
- maximum admissible raw peak `64`.

The generated `supercollider/sclork-playback.json` is both browser admission
data and runtime calibration. The gain is applied in the owned output wrapper,
after the source SynthDef, and remains separate from velocity and live mixer
gain. It therefore does not rewrite upstream definitions or interfere with UI
volume control. Runtime loading rejects overlapping include/exclude entries,
non-finite gains, non-positive gains and gains beyond the recorded bound.

The `sc-audio` suite renders every source definition. For browser-admitted
voices it rejects non-finite, silent, inaudibly quiet or full-scale-clipped
output. The complete suite was additionally run with each of 110, 440 and
880 Hz fixed across the catalogue.

## Voice lifetime repair

Some upstream SCLOrk definitions free themselves. The owned output wrapper
also has to release naturally and on explicit note-off. Each live record now
tracks whether its source node is alive before requesting a free. This makes
cleanup idempotent and prevents delayed `/n_end` notifications from producing
the repeated `FAILURE IN SERVER /n_free Node ... not found` messages.

The program configured as a role's default is prepared on first startup even
when its name equals the initial Python state. Previously that equality caused
the first configuration to be skipped, which could make initial chord, strum
or bass attacks target an unprepared revision.

## Samples and percussion

The VSCO manifest has 3,163 regions, so `scsynth` receives 8,192 buffer-number
slots before boot. Buffer identifiers and decoded sample memory are separate
resources: the existing byte-budgeted cache still owns admission and eviction.

VSCO instruments do not all cover the full keyboard. If a requested note lies
outside a program's recorded range, selection uses its nearest valid region
while playback rate still targets the requested note. The same rule applies to
release layers. This makes a full strum audible without falsifying the bank's
inventory.

The VSCO `GM-Style Percussion` source name does not imply General MIDI key
semantics. Its key 42 is a gong scrape and key 46 is a gong hit, for example.
The checked-in drum-role map is therefore based on the actual indexed sample
names: kick, snare, tambourine, suspended cymbal, cowbell, claves, log drums,
congas and related sources. A semantic test prevents gong recordings from
silently returning to timekeeper roles.

## Evidence and remaining limits

Automated compiler, frontend, sequencer, bank, package and three-register audio
suites pass. A real local production bootstrap was also driven through all 76
admitted SCLOrk programs, every percussion role and VSCO notes below, inside
and above a recorded range; shutdown contained no server failure, duplicate
free or buffer exhaustion.

This is technical qualification, not a claim that every timbre is equally
useful in every musical role. Subjective review of polyphonic balance, tails,
long performances and physical latency/load remains appropriate. Changes to
catalogue admission or calibration must update the profile reproducibly and
rerun the same fixed-register evidence rather than relying on a renamed patch
or a single audible spot check.
