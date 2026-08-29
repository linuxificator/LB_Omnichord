# MIDI Control Learn and Binding

This document is the behavioral contract for MIDI Control Change indicators,
MIDI-learn slider bindings, preset ownership and the corresponding OMNI status
LED. It resolves the implementation notes in `midi_control.txt`.

## Controller identity and genuine movement

A controller is identified by the pair `(MIDI channel, controller number)`.
Channels 1–16 and controllers 0–127 are independent identities, even when the
controller numbers match.

The first received value establishes a baseline. A repeated identical value is
ignored. Only a later different value is genuine controller movement. This
prevents controller snapshots sent during a channel or preset switch from
creating indicators, selecting instruments or changing audio state.

## Indicator bar and LRU behavior

The grey MIDI bar fills from left to right to the capacity calculated from its
current width. Every visible indicator shows its channel, controller number and
latest value. The radio knob rotates across 270 degrees for MIDI values 0–127.

When the bar is full, a genuinely moving controller which is not visible takes
the slot of the least recently moved eligible controller. Pointer interaction
does not update LRU age; only genuine incoming CC movement does. Before the new
controller is displayed, the outgoing knob becomes red and flashes twice.

Visibility and binding are separate state:

- idle and green/bound indicators are normally eligible for LRU replacement;
- a red/learn indicator is never replaced;
- blue/unbound indicators are protected for up to 30 seconds;
- if every available slot is red or blue, the oldest blue indicator may be
  removed before 30 seconds so new activity can be shown;
- an invisible green binding remains active;
- genuine activity from an invisible bound controller tries to make it visible
  using the same LRU rules.

## LED states and selection

Each MIDI indicator has one LED:

| State | LED | Meaning |
| --- | --- | --- |
| `idle` | dark grey | visible activity indicator, not selected or bound |
| `learn` | blinking red | the one controller waiting for a slider target |
| `bound` | steady green | controller has a persistent slider binding |
| `blue` | steady blue | binding was manually removed |
| `evicting` | red outgoing knob | old indicator is flashing before replacement |

Clicking an idle, green or blue indicator makes it the single red learn
controller. Selecting another indicator transfers the red learn state. Clicking
the already-red indicator cancels learn and turns it off. Starting relearn from
a green indicator removes its old binding without creating an intermediate blue
state.

## Binding and manual unlink

While one indicator is red, touching any supported numeric control binds that
controller to the touched target. The binding gesture is consumed: it does not
also edit or unlink the target. The slider handle and MIDI indicator LED become
green.

Bindings are globally one-to-one:

- one channel/controller pair controls at most one target;
- one target is controlled by at most one channel/controller pair;
- assigning an occupied target to another controller unbinds the old controller
  and makes that old indicator blue.

A green target consumes every normal edit gesture, including slider movement,
and remains visually synchronized to its MIDI-owned value. Qt Quick's standard
double-click/double-tap recognition defines the explicit unlink gesture, using
the platform style hints for time and distance instead of an application-owned
timer. The second press may unlink, but that same gesture is still consumed and
cannot edit the value; a later gesture may edit after ownership has been
released. This also works for click-only numeric controls such as volume and
tuning.
Unlinking makes the controller LED blue and ensures that controller is visible
when capacity allows.
The blue state is an inactivity notice, not a latch: the next genuine CC
movement ends it immediately and leaves the controller visible as an ordinary
unbound grey indicator. Without new movement, the blue state and its indicator
are removed after 30 seconds.

## Supported targets and range mapping

Every continuous numeric control is bindable:

- MIDI and OMNI instrument parameters;
- all MIDI and OMNI role volumes, including percussion;
- the independent OMNI and MIDI master-volume sliders;
- OMNI and MIDI reverb level, liveness and damping;
- OMNI and MIDI tuning reference;
- rhythm tempo;
- bass voicing.

Buttons, switches (including `MUT`/`UMT`), activity selectors, instrument
tumblers and tuning-mode selectors are not slider targets.

MIDI 0–127 maps over the complete visible slider travel. Linear sliders map
linearly. Logarithmic controls such as frequency map logarithmically, matching
the QML slider path. The result is rounded to the control's declared step and
clamped to its current catalogue/application range. Instrument catalogue ranges
are authoritative.

Binding does not immediately jump the slider to the controller's remembered
value. The next genuine incoming CC movement applies the mapped value through
the same backend setter used by manual UI editing. Backend notify signals must
also resynchronize the visible QML control after the binding touch, including
the three OMNI and MIDI reverb sliders.

## Controller authority

A green binding gives MIDI exclusive write authority over its numeric value.
Manual sliders/tap controls, direct frontend setter calls, tempo/tuning
UP/DOWN holds, copy operations and any other non-MIDI edit must leave that
value unchanged. Tempo and tuning UP/DOWN buttons are disabled and grey while
their effective value is bound. A section `RST` may restore the preset's
instrument selection and every unbound value, but it must preserve bound
parameters and the bound section volume. A hidden instrument-specific
parameter remains protected without selecting that instrument.

A runtime preset switch preserves the current value of every target bound
immediately before the switch and every target declared by the destination
preset. The destination preset still replaces that screen's binding set as
specified below; only the protected numeric values survive the transition.
Initial application startup may load all stored values because it is not a
live preset switch. After either operation, the next genuine CC movement
continues through the normal mapped setter path.

There is one deliberate exception. If the same channel/controller pair is
currently bound to target A and the destination preset assigns it to a
different target B, the destination preset owns the handoff. Its stored value
for B is applied instead of B's pre-switch value. If A belongs to that same
preset screen, A also takes its destination-preset value instead of retaining
its previous live value; state on the other preset screen is never loaded or
numerically changed as a side effect. This exception applies only to an actual
same-controller/different-target conflict. An unchanged binding retains the
normal live-value protection above.

Live rhythm continuity has higher priority for the rhythm controls it protects.
While rhythm transport is running, neither rhythm tempo nor bass voicing takes
a destination-preset numeric value, including during a binding-conflict
handoff. The binding handoff and its visual feedback still occur; only the
currently effective musical value survives until genuine controller movement.

Coupled OMNI/MIDI tuning treats a binding on either reference as ownership of
the effective shared reference, so both screens' UP/DOWN controls are locked.
When recoupling, a bound side is the synchronization source even if the link
was pressed on the other screen. Two independently bound references that have
diverged cannot be coupled, because doing so would overwrite one MIDI-owned
value.

## Instrument-specific targets

An instrument parameter binding stores the stable instrument key as part of its
target, in addition to its MIDI row or OMNI role and control key. Selecting
another instrument does not move or delete that binding. When its controller
moves, the relevant MIDI row or OMNI role first switches back to the bound
instrument and then applies the mapped parameter through the normal
`SynthState`/AMY-wire convergence path.

## Presets

Only green bindings are persisted. Red learn selection, blue timers, indicator
LRU age and current CC values are runtime state.

- MIDI-target bindings are stored in the selected MIDI preset.
- OMNI-target bindings are stored in the selected OMNI preset.
- the optional JSON field is `midi_control_bindings`;
- presets without the field load with no bindings for that screen;
- loading a preset replaces only that screen's bindings;
- runtime loading preserves bound numeric values according to the controller
  authority rule above, except for the explicit preset-conflict handoff;
- valid loaded bindings are admitted to the indicator bar as capacity permits;
- global one-to-one ownership still applies if separately stored presets assign
  the same controller to different screens.

### Binding-location feedback

Genuine movement of a controller also helps the performer find a binding whose
slider is not currently visible. An active in-memory binding remains
authoritative: when its target belongs to the other screen, the visible
`MIDI`/`OMNI` mode button flashes a green location LED. Movement of an active
binding on the visible screen keeps the existing behavior: an
instrument-specific target reselects its stored instrument, and no preset
location LED is needed for the already-selected preset.

If the moving controller has no active in-memory binding, the stored binding
metadata of non-selected OMNI and MIDI presets is consulted without loading a
preset. Every non-selected preset containing that controller identity flashes
a small green LED in its round preset button when that screen is visible. If a
matching preset belongs to the other screen, the visible mode button flashes
instead. The selected preset of either screen is excluded from this stored
lookup because unsaved in-memory binding changes are authoritative for selected
presets. If several inactive presets contain the same controller identity, all
of those valid locations are reported.

Screen routing is deliberately independent of preset status. As soon as either
the active binding set or the inactive-preset index locates the controller on
the other screen, the visible `MIDI`/`OMNI` mode button flashes. The mode button
therefore does not distinguish between a binding in that screen's selected
preset and one in any of its non-selected presets; its purpose is to say
"look on the other screen". Only after that screen is visible does preset
status affect the indication: a non-selected destination preset flashes its
own round button, while the selected preset needs no preset LED.

The preset LED sits between the label and the top edge of the round button. The
mode-button LED sits to the left of its label in the red part of the rainbow
button and is vertically centered. A location indication flashes for about two
seconds and fresh genuine movement restarts it. Baseline or repeated-identical
CC packets never start it. Location feedback does not select or load a preset,
switch screens, apply a value from an inactive preset, or otherwise change
musical state.

### Preset-conflict handoff feedback

When a destination preset assigns an already-bound channel/controller pair to
a different slider, its new assignment becomes effective immediately and wins
the global one-to-one conflict. For approximately two seconds both affected
slider handles flash rapidly: the displaced target flashes red and the incoming
preset target flashes blue. The blue incoming handle is already actively bound;
blue is only a temporary handoff color here, not the normal unbound-controller
state. During the handoff neither target accepts a manual edit.

After the handoff expires, the displaced target becomes an ordinary free
control with its normal handle color. The incoming target becomes steady green
and remains bound to the controller. The animation uses 110 ms fade-out and
110 ms fade-in halves, giving roughly nine rapid flashes in two seconds. A
preset load without a same-controller/different-target conflict does not show
this feedback.

## OMNI learn LED

On the OMNI screen, a blinking red learn LED appears inside the large `MIDI`
mode button, immediately to the right of the `MIDI` label so it does not sit on
the red end of the rainbow background. It is completely invisible whenever no
controller is in learn state. The existing green binding-location LED remains
on the left side of the button and follows its independent location-feedback
rules.

Blue/unbound state remains visible on the detailed MIDI-screen controller
indicator; it does not create a separate OMNI status LED. Switching screens
does not change learn, binding or musical state.

## Thread and AMY boundaries

Raw MIDI bytes are parsed on the existing background reader. Genuine CC changes
are queued onto the Qt object thread before they mutate application state.
Mapped updates call the existing MIDI/OMNI setters under a narrow in-call MIDI
authority flag; they do not introduce a second synth-state path, call AMY
directly or change the socket/serial wire boundary. The same setters reject
non-MIDI writes while their target is bound.

## Implementation map

The behavior is intentionally split along existing responsibilities:

- `../qt_frontend/code/midi_control.py` contains the transport-independent
  `MidiControlState` state machine for controller identity, genuine movement,
  LRU visibility, LED states, one-to-one bindings and serialization. It receives
  an already-classified double-tap action and owns no pointer-gesture timer.
- `../qt_frontend/code/midi_player.py` owns that state, queues raw CC changes
  onto the Qt object thread, resolves target ranges, calls the existing
  MIDI/OMNI setters and captures/restores bound numeric values around live
  preset and RST operations.
- `../qt_frontend/code/midi_integration.py` connects OMNI preset ownership and
  exposes the narrow integration-test actions. It does not create a second
  binding state.
- `../qt_frontend/gui/MidiScreen.qml` renders the MIDI indicator bar;
  `Main.qml` supplies OMNI learn state to the red LED in
  `RainbowModeButton.qml`. `UtilitySection.qml`, `MidiUtilitySection.qml` and
  the same rainbow button render binding-location feedback. `ParameterSlider.qml`,
  `LabeledSlider.qml`, `VerticalVolume.qml` and `TapNumber.qml` implement the
  shared bind/unlink gestures used by their owning sections.
- `../qt_frontend/tests/test_midi_control_bindings.py` tests the pure state
  machine; `test_midi_engine.py` tests mapping; `test_midi_cc_qt.py` tests real
  Qt/raw-MIDI indicator behavior; `test_static_contracts.py` protects QML
  wiring and layout; integration tests in `tests/integration/test_frontend.py`
  and `test_presets.py` cover AMY convergence and screen-owned persistence.

Executable user scenarios are `MIDI-CC-01` through `MIDI-CC-13` in
`../qt_frontend/tests/USE_CASES.md`.
