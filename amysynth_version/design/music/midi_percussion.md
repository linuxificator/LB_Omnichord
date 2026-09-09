# MIDI percussion mapping and level contract

Status: authoritative runtime contract

The MIDI screen's `Drum Kit 0` is selected per row. Its configured channel,
including channel `A`/omni, decides which incoming notes it receives. MIDI
channel 10 has no hidden special status and a melodic row on channel 10 remains
melodic.

## Note coverage

Every General MIDI percussion note 35 through 81 resolves before entering
AMY's lightweight shared PCM drum synth. Positive-velocity Note On triggers a
one-shot. Note On with velocity zero is normalized to release at the MIDI byte
boundary, and Note Off neither retriggers nor truncates the one-shot tail.
Notes outside the GM range are ignored rather than wrapped.

For Gamma9001, `code/drum_gamma9001.py` is the single source for the exact
direct-PCM realization of AMY's patch 384. The following sounds are added from
the same Gamma9001 bank because patch 384 does not define them:

- note 58: Gamma9001 `Vibrablib` (vibraslap);
- notes 71/72: Gamma9001 whistle at two pitches;
- notes 80/81: the two Gamma9001 triangle samples.

Gamma9001 has no dedicated guiro or cuica samples. These substitutions are
therefore explicit in `code/gm_percussion.py` and covered by tests:

- 73/74 use short/long shaker variants;
- 78/79 use high/low conga variants.

Tiny and legacy General-MIDI builds resolve every note through intentional
families in the existing configured sample map. Those are compatibility
substitutions; they are not claimed as an authentic 47-sound sampled kit.

Incoming notes identify percussion instruments. They are never chord-tuned,
transposed or passed through APG/LDR logic. The resolved native sample pitch is
sent to AMY.

## Velocity-60 reference

There is no universal default sequencer velocity: authored rhythms use lower
timekeeper and ghost velocities and stronger kick/snare accents. The stable
comparison is therefore the same sample at the same event velocity.

At the shipped M1 MIDI drum-row level of `0.28`, an incoming velocity-60 hit
has the same effective dry gain as a velocity-60 OMNI sequencer hit at the
shipped percussion bus level of `0.5`. The equality holds for every velocity,
not only 60; 60 is the audible acceptance reference supplied for this repair.
The MIDI row level remains a relative user control, MIDI master is still
applied once at its bus, and velocities below/above 60 retain a linear dynamic
response. No per-hit normalization, compressor or automatic gain control is
used.

Tests cover all 47 GM notes, the reported controller note set including repeat
note 60, configured and omni-channel routing, release semantics, monotonic
velocity, zero row volume, and the equal-gain reference calculation.
