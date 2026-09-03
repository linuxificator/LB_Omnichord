# Codex handover: QML and UI architecture analysis

Status: analysis; no visual or interaction behavior changed
Audit base: `c46b93b607722dd429ac54cab163deb61801632a`

## UI responsibility rule

QML owns presentation, layout and framework-native interaction. Python owns
musical/application policy and I/O. The boundary should exchange stable view
state and semantic intents such as “user moved attack control” or “begin MIDI
learn”, not raw pointer timing or private backend dictionaries.

This matches the established slider lesson: Qt's control and pointer framework
classifies movement; Python must not reimplement tap/hold/swipe timing. A
control's visual delegate must remain stable for the full drag, and user intent
uses interaction-specific signals such as `Slider.moved`.

Qt's official QML guidance explicitly distinguishes `moved` from
`valueChanged`: the latter can also occur through binding, clamping or rounding
and is therefore unsafe as a proxy for user interaction.

Primary references:

- [Qt Best Practices for QML and Qt Quick](https://doc.qt.io/qt-6/qtquick-bestpractices.html)
- [Qt Quick performance considerations](https://doc.qt.io/qt-6/qtquick-performance.html)

## Current strengths

- Reusable controls exist rather than all visuals living in `Main.qml`.
- Native Qt `Slider` behavior is now retained for mouse and touch drag.
- Backend echo is separated from user movement in the repaired numeric-control
  contract.
- MIDI learning is presented consistently in grey/blue indicators.
- OMNI and MIDI screen ownership remains visible in separate components.
- The baseline diagnostic sliders are valuable for isolating framework versus
  application behavior.

## Inventory and hotspots

The active QML set has 25 files and approximately 7,600 lines, with 76
JavaScript functions, 11 `Connections`, 3 `Timer`s, 22 `Repeater`s, 8
`TapHandler`s and one `MouseArea`. `Main.qml` is approximately 1,671 lines,
contains roughly 32 handlers and 33 backend calls. `MidiScreen.qml` contains
another 14 backend calls.

Similarity analysis found strong related pairs:

- `LabeledSlider.qml` and `ParameterSlider.qml`;
- `UtilitySection.qml` and `MidiUtilitySection.qml`;
- `StrumPad.qml` and `MidiStrumPad.qml`;
- `SynthSection.qml` and `MidiSynthSection.qml`;
- several activity/tap/volume controls with shared geometry or indicator
  behavior.

Similarity alone does not justify merging OMNI and MIDI policy. It identifies
shared visual and interaction primitives beneath separate domain components.

## Finding U1 — root QML is an orchestration hotspot

`Main.qml` composes the application but also contains substantial event
routing, formatting and backend calls. A root should primarily construct
screens, connect navigation and apply top-level layout.

Recommendation:

- extract complete page/section components with typed properties and semantic
  signals;
- let each page talk to one view-model/facade rather than call many unrelated
  backend methods;
- move repeated formatting/normalization to reusable pure JS only when it is
  presentation-specific;
- move musical/control decisions to Python domain/application services;
- retain an explicit root connection for truly global state such as active
  screen or fatal transport status.

## Finding U2 — duplicated controls should share behavior, not policy

Create focused primitives for:

- bindable numeric interaction: stable handle, visual fill, display formatting,
  `onMoved`, learn indicator and release-before-manual-edit intent;
- utility-section framing/layout;
- pointer normalization for strum surfaces;
- transient indicator/LED rendering;
- label/value typography and disabled-state presentation.

Then keep `OmniParameterSlider` and `MidiParameterSlider` as thin semantic
wrappers if their backing state or learn targets differ.

Do not build one “universal control” with many booleans and domain branches.
That merely relocates coupling and makes invalid combinations possible.

## Finding U3 — MIDI learn handshake is distributed

Control visuals, indicator taps, backend learn state, binding state and manual
takeover form one state machine. The visual contract is now clear:

- unbound grey/blue tap enters learn and flashes red;
- green (bound) tap unlinks and returns to blue/grey;
- moving a bound numeric UI control intentionally unlinks before applying the
  user value;
- backend echo never masquerades as manual movement;
- keyboard note-on/off is not a hardware controller-button candidate.

Encode this state machine once in Python (`BindingService`/existing
`MidiControlState`) and expose an immutable presentation state. QML dispatches
`requestLearn`, `requestUnlink` and `manualMove`; it should not infer binding
transitions from colors.

Add Qt Quick/QML tests for the visual state plus Python state-machine tests for
the transition table.

## Finding U4 — value, visual position and event value need one mapping

The slider regression showed three values can diverge:

- backend/control value;
- native Qt `Slider.value`/`visualPosition`;
- a wrapper's displayed/event value.

Every numeric control should define exactly one invertible mapping between
domain value and normalized Qt value. Fill geometry and handle geometry must
both derive from `visualPosition`, especially under inverted/vertical layouts.
Pitch-bend center is a domain value mapped to a visual handle pointing upward;
binding pitch bend should immediately initialize the controlled slider to its
center, not wait for the first MIDI packet.

Tests should exercise press, multiple moves, release, external echo during
drag, inverted ranges, pitch-bend center and re-created delegates. A single
tap test is insufficient.

## Finding U5 — QML imperative work should remain bounded

Qt recommends simple declarative bindings, event-driven work and profiling
before optimization. It warns against giant singletons and doing everything in
QML. For this application:

- do not parse musical catalogues or build AMY commands in QML;
- do not run blocking filesystem/socket work from a QML handler;
- keep delegates lightweight and stable during interaction;
- avoid manually spinning the event loop;
- profile Android/embedded startup and frame behavior before introducing
  loaders or shaders;
- keep rendering simple: the knob lighting/shadow experiment showed decorative
  complexity can harm clarity as well as GPU cost.

## Finding U6 — facade surface should be inspectable

The QML-facing QObject API is currently a large part of `InstrumentBackend` and
`MidiPlayerBackend`. Freeze it during refactoring with an introspection test
that records intended properties, notify signals and slots, while avoiding
literal whole-source assertions.

Then group the facade by screen or use case. QML should not need private Python
implementation knowledge, and Python should not reach into instantiated QML
items by object name except for narrowly documented startup/diagnostic cases.

## Accessibility and input parity

The current contracts emphasize pointer, touch and MIDI. Code quality also
requires explicit keyboard/focus/accessibility behavior where Qt supports it:

- every interactive control has a meaningful accessible name and role;
- focus order follows the visual/task order;
- disabled/learn/bound state is not conveyed by color alone;
- mouse, touch and keyboard interaction invoke the same semantic intent;
- minimum touch targets remain usable on Android;
- LED animation does not become the only state feedback.

These are proposed quality scenarios, not claims that every item currently
fails. Audit them with Qt accessibility inspection before changing visuals.

## UI test layering

1. Pure Python mapping/state-machine tests.
2. QML component tests for value mapping, stable delegate and emitted intent.
3. Headless frontend tests for facade/property integration.
4. Real pointer/touch regression tests on a rendered window.
5. Package smoke on all supported platforms.
6. A small manual visual checklist for appearance/accessibility that cannot yet
   be asserted robustly.

Screenshots catch gross layout drift but are not a substitute for interaction
tests. Avoid pixel-perfect tests for antialiasing/shadow differences across
renderers unless exact pixels are a stated contract.

## Extraction acceptance criteria

- all sliders preserve current smooth drag and visual alignment;
- backend updates never trigger a manual-unlink action;
- manual movement of a bound control always unlinks exactly once;
- learn/unlink behavior is driven by semantic state, not LED color parsing;
- shared primitives contain no OMNI-versus-MIDI musical branch;
- `Main.qml` loses orchestration logic without growing a global singleton;
- real mouse/touch/QML/package tests remain green on all five targets.
