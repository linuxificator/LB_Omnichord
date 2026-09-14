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

Nineteen reviewed drum definitions used by the selectable synth drum kits are
also present in the playback profile. Category membership, not profile
membership, keeps them out of the pitched browser. Both the yellow OMNI rhythm
row and purple MIDI percussion row offer the same fifteen explicit kits: the
legacy VSCO PCM kit, five native SC kits and nine reviewed PCM expansion kits.
Their musical-data contract is in
[`MUSIC_EXPANSION.md`](MUSIC_EXPANSION.md).

## SCLOrk measurement and gain staging

`tools/build_sclork_playback_profile.py` consumes raw 32-bit-float NRT reports
at MIDI notes 45, 69 and 81 (A2, A4 and A5). MIDI 107 is a separate ceiling
report: it constrains stability and peak gain across the public strum range
without treating an extreme register as a loudness target. For each eligible definition it
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

A live all-feature pass exposed three upstream filter graphs that become
non-finite at the strum's MIDI-107 boundary (`acidOto3091`, `acidOto3092` and
`combs`) and an unstable `tubularBell` low-pass cutoff. Small owned adapters
preserve their source topology and controls while bounding filter cutoffs to
45% of the actual sample rate. The exact upper-register set is now an NRT
regression test. `doubleBass` also receives a ceiling-constrained playback gain.

Selected drum programs are rendered with their production default frequency,
not the fixed pitched-register probes. Their checked-in gains must keep a
single hit between RMS 0.010 and 0.075; all rendered programs must remain finite
and below full-scale clipping. An extra peak balance threshold would be flaky
for noise-based percussion, so the NRT output stage mirrors the production
5 ms master limiter and enforces its 0.95 output ceiling. The profile builder accepts repeatable
`--drum-program` arguments and records their exact set, so a new roller mapping
cannot bypass either calibration or the NRT balance gate.

## Voice lifetime repair

Some upstream SCLOrk definitions free themselves. The owned output wrapper
also has to release naturally and on explicit note-off. Each live record now
tracks whether its source node is alive before requesting a free. This makes
cleanup idempotent and prevents delayed `/n_end` notifications from producing
the repeated `FAILURE IN SERVER /n_free Node ... not found` messages.

Sample regions may naturally reach the end of their files before a UI release,
program change or retune arrives. Each region node now records its `/n_end`
state; later operations visit only live nodes. This prevents harmless user
actions from becoming `/n_set Node ... not found` server failures while the
lightweight musical handle remains available for owner-scoped release layers.

All dry bus strips and both room returns meet on one private master bus. A
single 5 ms look-ahead limiter at 0.95 protects the physical output from hard
digital clipping under valid polyphonic combinations. Role gains, velocity,
calibration and room balance remain independent upstream controls; the limiter
is a final safety boundary rather than another user-visible volume mechanism.

The program configured as a role's default is prepared on first startup even
when its name equals the initial Python state. Previously that equality caused
the first configuration to be skipped, which could make initial chord, strum
or bass attacks target an unprepared revision.

### Immutable sequencer program lifetime

A program selection and an already-published sequencer execution have
different lifetimes. Changing a PCM chord program immediately publishes a new
immutable lane definition, but the previous root or a finite phrase may still
have events carrying the old `program@revision`. Each SC execution therefore
retains the exact sample revisions referenced by its definition. A root also
inherits the revisions used by the finite definitions it can launch. Releasing
the frontend selection only marks that revision for release; its buffers are
reclaimed after the final root or finite execution has ended.

This ownership stays entirely inside SuperCollider. Python still publishes
immutable musical plans and does not inspect beat phase, infer remaining
events or retain sample buffers. A pure-SC regression proves independent root
and finite ownership, including replacement while a child phrase is running.

Native output wrappers and chokeable PCM drums also use stable control buses
for their release gates. The buses outlive the nodes they control, so natural
sample or SynthDef completion cannot race a later `/n_set` addressed to an
already-freed node. Existing owner-scoped note and release behavior is
unchanged.

## Samples and percussion

The pitched VSCO manifest has 3,163 regions and the PCM drum expansion adds 262
verified sample identities, so `scsynth` receives 8,192 buffer-number slots
before boot. Buffer identifiers and decoded sample memory are separate
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

All 75 SFZ mappings and 3,163 compiled regions are accounted for. The wider
local VSCO checkout also contains 1,134 source audio files that are not
referenced by those mappings, mostly archive/raw material. They are reported
as `unmapped-source-audio`; the application does not invent undocumented key
or articulation semantics merely to expose every file.

## Evidence and remaining limits

Automated compiler, frontend, sequencer, bank, package and three-register audio
suites pass. A real local production bootstrap was also driven through all 76
admitted SCLOrk programs, every percussion role and VSCO notes below, inside
and above a recorded range; shutdown contained no server failure, duplicate
free or buffer exhaustion.

A focused real-process regression keeps automatic arpeggios and rhythm active
while switching repeatedly among PCM chord programs. A ten-cycle run selected
ordinary Flute 120 times among 370 public frontend actions. Its continuous
recorded-audio windows completed without server failure, clipping,
missing-node or buffer-lifetime error. This directly exercises the rapid-switch
symptom while keeping the process boundary identical to a normal local run.

This is technical qualification, not a claim that every timbre is equally
useful in every musical role. Subjective review of polyphonic balance, tails,
long performances and physical latency/load remains appropriate. Changes to
catalogue admission or calibration must update the profile reproducibly and
rerun the same fixed-register evidence rather than relying on a renamed patch
or a single audible spot check.
