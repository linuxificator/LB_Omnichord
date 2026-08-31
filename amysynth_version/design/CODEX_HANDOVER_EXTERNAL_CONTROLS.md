# Codex handover — external controls and smooth Qt sliders

This handover records the implementation decisions and regressions found during
the `rework/external_controls` branch. It is internal LB Omnichord working
documentation for future Codex sessions; the authoritative behavior remains in
`gui.md`, `midi.md`, `midi_control.md`, `testing.md` and
`../qt_frontend/tests/USE_CASES.md`.

## Slider regression and fix

The observed failure was not a low-level mouse/touch problem. Minimal Qt
baseline apps using the same PySide6/QML environment dragged normally. The full
application only moved the handle once or a few pixels because a synth-parameter
edit republished the complete QML control-list model on every `Slider.onMoved`.
That replaced `Repeater` delegates during the active press and made Qt lose the
interactive drag path. The same churn also made MIDI-controlled slider movement
look and feel more stepped than necessary.

The design rule is now:

- Qt owns pointer classification and slider interaction. Do not add Python
  timers, movement counters or custom gesture thresholds for slider drag.
- Custom slider handles must expose `implicitWidth` and `implicitHeight`, so
  Qt's actual hit target matches the visible handle.
- While `Slider.pressed` is true, the slider owns its interactive value.
  Backend echoes may update application state, but they must not force the
  QML handle back to an older value or replace the delegate being dragged.
- UI-live synth parameter edits must still send the complete logical AMY state,
  but they must not emit the control-list model notification used for preset
  loads, instrument switches or external/API/MIDI writes.

The implementation keeps the public setter paths unchanged for non-drag cases:

- OMNI public setters (`setChordSynthControl`, `setStrumSynthControl`,
  `setBassSynthControl`) still emit the relevant synth-control model update.
- OMNI UI-live edit slots (`editChordSynthControl`, `editStrumSynthControl`,
  `editBassSynthControl`) pass `emit_controls=False`.
- MIDI public `setControl` still emits row state.
- MIDI UI-live `editControl` passes `emit_state=False`.
- QML synth sliders call the `edit*` path from `onEdited`; MIDI/automation
  paths keep using the ordinary setters.

Regression coverage is intentionally layered:

- `test_qml_gesture_controls.py` proves plain and custom sliders still drag,
  stale backend echoes do not fight a drag, replacing a parameter model during
  a press no longer prevents reaching the dragged value, and a bound drag
  releases MIDI ownership exactly once before its first UI edit.
- `test_slider_backend_contracts.py` proves public setters keep model emission
  while UI-live edit slots suppress only the model-reset side effect.
- `test_static_contracts.py` prevents future QML rewiring from bypassing the
  live-edit path or restoring the superseded double-tap unlink path.

## Intentional manual MIDI takeover

During implementation, moving a MIDI-bound slider already happened to unlink
it because `onMoved` called a generic movement hook. The behavior proved useful,
but retaining an incidental call would leave it vulnerable to cleanup or gesture
refactoring. The contract and code now name the intent directly:

- `MidiControlState.release_target_for_manual_edit()` is the sole numeric-target
  unlink transition;
- QML calls `releaseControlTargetForManualEdit()` before applying the first
  changed value from a bound mouse/touch drag;
- horizontal sliders track `midiManualTakeoverPending` per press, so only a real
  `Slider.onMoved` event unlinks and the release happens once;
- click-only volume/tuning controls release before their first value step;
- there is no double-tap unlink handler or Python gesture classifier.

The grey-bar controller indicator also has an explicit single-click state
machine in `MidiControlState.indicator_clicked()`: grey/blue starts learn, red
cancels learn, and green only unlinks to blue. In particular, green never means
“unlink and immediately relearn”. State-machine, real QML pointer and static
contract tests protect these transitions and their release-before-edit order.

## MIDI input techs

The branch implements the platform-tech display requested for the MIDI screen.
The app listens to all implemented technologies for the current platform and
merges their decoded events into the same application MIDI stream.

Current implemented runtime readers:

- Linux ALSA raw character devices (`/dev/snd/midiC*D*` by default);
- Linux ALSA sequencer client/port named `LB Omnichord` / `MIDI In`;
- Linux OSS-compatible MIDI character devices where present.

The ALSA sequencer reader is required for graph-routed applications such as
VMPK and PipeWire graph setups visible in `qpwgraph`. Each input byte stream has
its own running-status parser state before events are merged, so one device's
partial MIDI message cannot corrupt another device.

The common non-Linux MIDI APIs are deliberately represented but not pretended
to work:

- macOS: CoreMIDI;
- Windows: WinMM MIDI;
- Android: Android MIDI.

Until native bridges for those APIs are bundled, these techs are platform
relevant and visible red/unavailable on their platform. They must not start the
Linux raw or ALSA sequencer readers. Tests cover this explicitly so future
platform work can replace the unsupported bridge with a real reader without
changing the UI contract.

LED meaning:

- red: relevant to the current platform but unavailable or unimplemented;
- green: available and being listened to;
- blinking green: recent MIDI bytes arrived through that tech;
- omitted: not relevant to the active platform.

## MIDI controller buttons

Ordinary musical Note On/Off remains performance input and must not create
controller-button indicators. Treating note-transmitting pads as controller
buttons requires an explicit future whitelist/translation layer.

For admitted controller-buttons, takeover is scoped:

- tap-only actions such as panic, store-preset and cycle-channel trigger on
  press but do not create held takeover state;
- choice groups block only other choices in the same group, such as preset
  choices, percussion/chord/bass activity choices or arpeggio-rate choices;
- independent toggles block only their exact screen button while held;
- unrelated screen buttons remain usable.

This keeps hardware authority where it matters without making one held external
button freeze the rest of the UI.
