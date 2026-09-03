# Codex handover: macOS slider visual-state regression

Status: implemented and regression-tested on `appel/frits_slider_fix`
Base: `rework/code_quality` plus `origin/main` (already an ancestor)
Observed platform/input: macOS with an ordinary mouse
Shared coverage: mouse and touchscreen through the same Qt Slider primitive

## User-visible failure

A macOS user could drag a slider and hear the application accept the changed
value, but the custom handle and filled track did not retain the new position.
The report concerned mouse input, not a trackpad or touchscreen. Touch remains
part of the contract because both device classes enter the same native Qt
Slider interaction path.

## Regression boundary and cause

Commit `6c5e1de` deliberately stopped publishing a new synth-control Repeater
model on every live edit. Replacing a delegate during a drag loses Qt's pointer
grab, so this remains required behavior. Before the focused-QML consolidation,
`ParameterSlider.qml` also deliberately kept Qt's accepted local value after a
normal release.

Commit `bef1fad` correctly consolidated the duplicated slider implementation
into `BindableSlider.qml`, but made release always restore the binding to
`currentValue`. For parameter edits, `currentValue` can intentionally remain at
the pre-drag model value until a later publication. Consequently, the backend
and AMY received the edit while release restored the visible slider to stale
state. Earlier tests asserted the emitted/backend result and geometry at a
static value, but did not assert the final rendered position after release.

## Implemented contract

- Qt owns value and pointer capture for the complete native gesture.
- A real `Slider.onMoved` event marks that press as an accepted user edit.
- After such an edit, release retains the accepted native value. Handle and
  fill continue to derive only from `Slider.visualPosition`.
- A press without movement or a gesture consumed by MIDI learn immediately
  restores backend synchronization.
- Any later external `currentValue` change remains authoritative and restores
  the declarative binding.
- Mouse and touch use this one implementation. There is no operating-system
  branch, custom gesture recognizer, Python movement threshold or duplicate
  domain state.

## Proof and release guard

`test_qml_gesture_controls.py` now drives multiple mouse moves and a registered
Qt touchscreen sequence through a real `ParameterSlider`. Both tests assert:

1. the backend edit signal receives the changed value;
2. the native value remains changed after pointer release;
3. the custom handle and fill match `visualPosition` during and after the drag;
4. a later external model update still synchronizes the slider.

Before the fix, both device tests ended with backend/edit value 852 and visible
native value 100. After the shared fix, both retain the accepted value.

The production package smoke now also locates a visible synth-parameter slider,
drags its real native QML control with a mouse, checks value/handle/fill during
the drag and after release, and writes `qml-slider-drag-visible` and
`qml-slider-release-visible`. Windows, macOS and Android package gates require
those checkpoints; Linux source-level package smoke exercises the same helper.
In particular, the macOS job executes this from the mounted final DMG, so this
regression no longer depends solely on Linux component coverage.

Physical-device testing remains useful evidence, especially for Android touch,
but it is no longer the first place this stale-model visual regression can be
detected.
