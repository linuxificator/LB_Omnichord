# QML quality cycle 002 results

Status: implementation complete for the necessary low-risk work
Branch: `rework/quality_cycle_002`
Recorded: 2026-09-09

## Outcome

This cycle implemented the first four bounded tasks from the QML modernization
handover without changing application behavior or platform architecture.

- A version-bound `pyside6-qmllint` check now runs from the normal quality gate.
- The check stores a normalized diagnostic artifact and rejects new warning
  categories or increases per file.
- All six definite generic-parent property errors were repaired.
- Delegate roles and lexical ownership are explicit throughout the current QML.
- Small, unambiguous numeric calculations in the slider, strum, migraine,
  octave and bounded-value controls have typed parameters and return values.
- The reviewed lint baseline fell from 362 warnings to 127. No warning was
  suppressed and no lint category was disabled.

The remaining 127 diagnostics are all `unqualified` lookups at the deliberate
Python/QML composition boundary:

| QML source | Count | Current owner |
| --- | ---: | --- |
| `Main.qml` | 102 | Python context properties |
| `MidiScreen.qml` | 24 | Python context properties |
| `BindableSlider.qml` | 1 | `sliderTrace` diagnostic context property |

They correspond to objects and immutable startup data published centrally by
`app_core.run_application()` using `QQmlContext.setContextProperty()`, including
the performance, MIDI and main controllers, model lists, window configuration
and diagnostics. `qmllint` cannot inspect those runtime Python objects. These
remaining warnings are therefore an explicit boundary inventory, not accepted
delegate ambiguity.

## Architecture review

The implementation preserves the existing contracts:

- QML remains presentation plus Qt-owned gesture classification.
- Python remains the composition root and owns state and AMY wire commands.
- AMY remains a separate local process or serial target.
- No platform branch or platform-specific behavior was added to QML.
- No production hook was added for tests or linting.
- Mouse and touch share the same control implementations.
- The changes do not add timers, polling, rendering work or runtime services.

`pragma ComponentBehavior: Bound` is used only in files whose nested delegates
intentionally access IDs in their lexical component. Delegate `index` and
`modelData` values are required properties and are accessed through the owning
delegate ID. This makes the existing ownership executable instead of relying on
implicit lookup.

The typing changes stop at contracts QML itself can prove. Python `QObject`
instances, heterogeneous model records, MIDI/OSC target maps and callbacks stay
dynamic; converting them mechanically would claim guarantees the interface does
not provide.

## Verification performed

The following checks passed on the development host with PySide 6.10.3:

- `python tests/run_quality.py`
- `python tests/test_qml_gesture_controls.py`
- `python tests/test_labeled_slider_sync.py`
- `python tests/test_migraine_render_budget.py`
- `python tests/test_static_contracts.py`
- `python tests/integration/test_frontend.py`
- `python tests/integration/test_presets.py`
- an offscreen production capture that loaded `Main.qml` and rendered both the
  OMNI and MIDI screens through `capture_screenshots.py`

The previously started `main` release run received `SIGTERM` from its GitHub
runner during `test_serial.py` after seven tests had passed. Re-running the
failed job completed the serial suite successfully. This was runner termination
(exit 143), not a serial regression, so no speculative code workaround was
added. Per instruction, the remaining packaging jobs were not followed.

## Deferred, non-required improvements

### Explicit root properties for Python objects

Replacing context-property lookup with properties supplied to the root object
could make the remaining boundary more visible to tooling. It is a real
composition change, not a lint cleanup. It must first characterize object
creation order and every startup route, including screenshots, AppImage, DMG,
Windows and Android. It must also preserve the narrow `PerformanceQmlAdapter`
needed by the Raspberry Pi PySide baseline. The current centralized context
publication is consistent and tested, so this migration is not required now.

### Precompiled QML bytecode

An isolated `pyside6-qmlcachegen --only-bytecode` experiment remains optional.
Keep it only if cold start, warm start, 120 Hz strum load, package size and all
platform packages demonstrate a useful improvement with exact PySide-version
matching. There is no present evidence that bytecode would improve the measured
scene-graph workload.

### Runtime profiling

Use the QML profiler or GammaRay only when a physical workload still shows a
problem. The Pi 4 acceptance test currently has no crackles, so speculative
runtime optimization would violate the measure-first and native-mechanism-first
contracts.

## Resume point

The safe next step is to leave the ratchet in place and let ordinary changes
reduce the remaining context warnings when they naturally touch composition.
If an explicit-root-property migration is approved later, implement it as a
separate architecture branch with characterization tests before source changes.
