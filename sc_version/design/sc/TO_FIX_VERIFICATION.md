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
- `sc-audio` renders all 109 SCLOrk definitions and enforces the drum-kit
  balance window.
- Screenshot-state tests drive public controller methods, not private QML
  state. A production bootstrap with real `sclang`, `scsynth` and Qt captured
  representative OMNI and MIDI PCM families, playing styles, Piano sustain and
  independent drum kits without QML warnings or SC server failures.

The automated evidence establishes bounded signal production and behavioral
ownership. It does not replace a long subjective performance test across
polyphony, transitions and sample-cache pressure; that remains a release
qualification activity.
