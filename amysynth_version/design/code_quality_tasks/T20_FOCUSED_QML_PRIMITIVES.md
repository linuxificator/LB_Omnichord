# T20 result: focused QML interaction primitives

Status: complete
Recorded: 2026-09-01
Branch: `rework/code_quality`
Owner: native QML numeric interaction and passive shared presentation

## Outcome

- Added `BindableSlider.qml` as the single native horizontal-slider delegate.
  It owns stable press/move/release synchronization, `Slider.moved` intent,
  release-before-manual-edit, semantic binding presentation, handle/fill
  geometry and tracing.
- Kept `LabeledSlider.qml` and `ParameterSlider.qml` as thin, distinct
  wrappers. Labels/value lists and linear/log/note conversion remain in their
  appropriate wrapper; the primitive has no OMNI/MIDI musical branches.
- Added a meaningful Qt accessibility name to the native slider from each
  wrapper's label.
- Added one passive `SectionBackground.qml` for the exactly duplicated orange
  utility frame and one presentation-only `PointerNormalization.js` function
  for the two strum surfaces.
- No custom pointer timing, thresholds, universal boolean-heavy control or
  musical policy was introduced.

## Compatibility and proof

- Existing real offscreen Qt tests prove plain and bound handle drags, track
  clicks, press without movement, single manual unlink, backend echo during a
  drag, model replacement during a parameter drag and full reverb-panel input.
- A new rendered-component test proves both fill width and handle position are
  derived from the native `visualPosition` at an exact domain value.
- Static boundary tests prove both wrappers use the one primitive, both utility
  sections use the passive frame, both pads use the same normalizer and no
  domain-controller policy leaked into those passive helpers.
- The complete quality and behavior gates are run before this task is committed;
  their measured result is recorded in the commit handoff.

## Findings and progressive insight

- The useful reuse boundary is one native interaction delegate, not a merged
  OMNI/MIDI parameter component. Conversion and display rules vary; drag,
  takeover and geometry do not.
- Wrapper model replacement no longer needs a separate synchronization
  implementation. A changing wrapper `currentValue` is ignored while the
  native control is pressed and rebound once at release.
- QML source-location tests had encoded the duplicated implementation as a
  requirement. They now test that policy exists once and wrappers delegate to
  it. T23 should move the remaining detailed source assertions toward rendered
  behavior or structured QML inspection.
- Passive visual sharing is intentionally narrow. The utility sections and
  strum pads still own different commands and state, avoiding a universal
  screen component with invalid policy combinations.

## Follow-up task effects

T21 can extract complete root sections while treating these primitives as leaf
components. It must retain wrapper signal signatures and must not bypass
`BindableSlider` with local gesture handlers. T23 should retain the rendered
multi-move tests as the primary slider proof.
