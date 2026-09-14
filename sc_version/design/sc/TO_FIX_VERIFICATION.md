# SuperCollider usability follow-up verification

Status: implemented and regression-tested

Last verified: 2026-09-14 on Linux x86_64

This document closes the concrete items in `design/sc/to_fix`. It records the
current contract and evidence; the implementation and executable tests remain
the authority.

## Implemented behavior

1. Manual strum attacks are never stolen by a frontend voice limit. Each
   attack receives its own handle and SuperCollider owns the exact release.
2. PCM choice buttons inherit their containing role/row colour. They are not
   orange status controls. One source variant with several playing styles is
   an inert upper label with actionable lower style buttons.
3. Reverb exposes native SC controls: wet level, room size and damping, all in
   the normalized 0..1 domain.
4. OMNI and MIDI percussion each have the same six explicit kit choices,
   covering the VSCO PCM map, an owned basic kit and four qualified SCLOrk
   families. The ordinary pitched browser excludes drum-category SynthDefs.
5. The five pitched MIDI rows use the same `SYN`/`PCM` catalogue, choices and
   effective parameter sliders as OMNI roles. Piano PCM rows additionally
   expose the existing owner-scoped sustain behavior.
6. Riff, arpeggio, leader and chord-activity replacement preserves transport
   phase. The old root stops at the aligned boundary and the replacement starts
   at that same phase; UI code does not calculate musical time.
7. Drum velocity is clamped after every fill and kit contribution. Rhythm
   start can therefore never send a value outside the typed 0..1 protocol.
8. Synth drum output calibration is owned by the same reproducible playback
   profile as pitched SCLOrk programs. No second hidden volume mechanism was
   introduced.

## Defects found by live qualification

The first external PipeWire capture found a sustained full-scale failure when
the highest strum note selected an upstream filter graph outside its numeric
range. Four minimal routing adapters now bound those filters by sample rate,
and the playback builder has a distinct MIDI-107 ceiling report. A targeted NRT
test reproduces the exact register rather than relying on mid-register renders.

The next pass found brief hard clipping only when several individually valid
parts summed. Dry strips and room returns now cross one private master limiter;
the test asserts there is exactly one final bounded stage. This preserves all
upstream mix controls and prevents the sound device from doing uncontrolled
integer clipping.

Rapid PCM program replacement then exposed `/n_set Node ... not found`: a
sample could naturally end before its owner handle was released. Region nodes
carry an explicit live flag updated by `/n_end`, and release/retune iterates
only live regions. The sample-loader test freezes that rule.

The first multi-cycle run exposed two further lifetime boundaries. Dense bass
activity produced provenance text longer than the typed protocol's 192-byte
identity limit. Bass definitions now use a deterministic SHA-256 identity;
this metadata does not cross the OSC wire or alter musical behavior. A
32-event regression fixture proves identities remain stable and bounded.

Rapid native-program replacement also raced a naturally completed SCLOrk
source against wrapper cleanup, producing duplicate `/n_free` requests. Each
native voice now owns one persistent node group containing its source and
output wrapper. Cleanup frees that group instead of addressing a source node
which may already have ended, while explicit alive/release state prevents late
parameter or gate messages. The package contract freezes this ownership rule.

## Coverage and balance boundary

The compiler still audits all 109 pinned SCLOrk definitions. The pitched
browser exposes 76 qualified SCLOrk programs and four owned acid programs. The
drum rollers use nineteen separately qualified SCLOrk drum programs plus the
basic and VSCO paths. NRT renders require finite audio; every selected synth
drum hit must have RMS 0.015..0.075 and peak below 0.85 at its real runtime
default frequency.

The generated VSCO manifest covers all 75 SFZ mappings and all 3,163 referenced
regions. The 1,134 local audio files not referenced by those mappings remain
explicitly reported as unmapped source material. This is a deliberate audit
boundary: no unreviewed pitch, role or articulation mapping is inferred from a
filename.

## Executable and visual evidence

- `sc-frontend` checks typed endpoints, exact handle ownership, drum routing,
  catalogue separation and reproducible playback-profile membership.
- `sc-sequencer` checks phase-preserving replacement and unchanged note/gate
  lifetimes in a separate real `sclang` process.
- `sc-audio` renders all 109 SCLOrk definitions, enforces the drum-kit balance
  window and renders the exact repaired programs at MIDI 107.
- Screenshot-state tests drive public controller methods, not private QML
  state. A production bootstrap with real `sclang`, `scsynth` and Qt captured
  representative OMNI and MIDI PCM families, playing styles, Piano sustain and
  independent drum kits without QML warnings or SC server failures.

The automated evidence establishes bounded signal production and behavioral
ownership. It does not replace a long subjective performance test across
polyphony, transitions and sample-cache pressure; that remains a release
qualification activity.

`tests/endurance/sc_endurance.py` is the repeatable live qualification driver.
It keeps the test driver, Qt graph, SC runtime and PipeWire recorder in separate
processes, drives only public controller actions, records action/progress logs,
and rejects server errors, prolonged silence, dropouts and hard clipping. Four
cycles rotate through the complete synth and PCM catalogues for every OMNI role
and every pitched MIDI row; zero cycles means it continues until interrupted.
Its `--gui` mode additionally loads the production `Main.qml` scene through
Qt's offscreen platform and captures both screens after every cycle. Captures
must have the expected dimensions and non-degenerate colour content. The
ordinary SC frontend process regression also loads this same production QML
scene and validates an actual PNG, so a controller-only graph cannot
accidentally be mistaken for GUI coverage.

The 2026-09-14 finite release qualification completed all four catalogue
cycles: 3,254 public actions in 351.294 seconds and twelve independently
captured audio windows. It reported no server failure, persistent clipping or
dropout. Except for the initial startup window (394 ms), the longest measured
silence was 31 ms and then 21 ms. The runner now establishes explicit running
state at cycle boundaries; blind toggles previously manufactured a 4.9-second
silent interval and are covered by an idempotence regression test.
