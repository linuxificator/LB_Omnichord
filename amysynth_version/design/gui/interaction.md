# Qt interaction and rendering

Status: authoritative non-regression contract
Owner: Qt/QML interaction
Last verified: 2026-09-08

Qt handlers own tap, hold and drag classification. Python receives semantic
intents and must not recreate gesture timing. Mouse and touch use the same QML
control path.

Production sliders keep a stable native `Slider` object for the entire
gesture. The custom handle and fill derive from the same accepted value and
remain aligned during and after release. Manually moving a MIDI/OSC-bound
slider intentionally unlinks it before applying the value; a press without
movement does not unlink it.

Controller indicators use explicit state, not color inference. A single click
starts learning when free and unlinks when bound. Musical keyboard Note On/Off
messages are never treated as controller buttons.

The strum `Migraine` visual is transparent to input, cached, contains no
particle-emitter fan-out and updates its shape at a bounded 30 Hz while pointer
input may run at 120 Hz. Its release fade remains visual-only. Shared tests
exercise mouse and touch semantics and the render-cost contract on every
package toolchain; physical GPU/audio acceptance remains platform evidence.

