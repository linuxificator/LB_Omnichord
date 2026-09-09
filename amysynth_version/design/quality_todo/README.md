# QML modernization handover

Status: proposed quality cycle; no implementation started
Owner: Qt/QML presentation and build tooling
Recorded: 2026-09-09

## Purpose

This handover records a bounded follow-up based on KDAB's modern QML guidance
and an audit of the current production QML. It is not evidence of an active
performance problem. The Raspberry Pi 4 currently runs without audio dropouts,
and the measured strum improvement came from reducing scene-graph work rather
than from QML-language or Python execution changes.

Any future implementation must preserve the existing architecture contracts:

- QML remains presentation and framework-owned gesture handling;
- Python owns application state and produces AMY wire commands;
- AMY remains a separate process or serial target;
- mouse, touch and external-control behavior remains identical;
- portable application behavior must not acquire platform branches;
- performance claims require before/after measurements.

## Current evidence

The following command was run from `qt_frontend/gui` using PySide 6.10.3:

```sh
pyside6-qmllint *.qml physical_controls/*.qml
```

It completed successfully but reported:

- 352 `unqualified` warnings;
- 6 `missing-property` warnings;
- 1 `index` warning;
- 96 occurrences of `property var`;
- 75 QML/JavaScript function declarations without a fully typed signature;
- only 3 files with `pragma ComponentBehavior: Bound`.

These numbers are an investigation baseline, not 455 confirmed defects.
Several unqualified warnings concern Python objects published through
`QQmlContext.setContextProperty()`, which `qmllint` cannot type. Some `var`
properties legitimately carry Python `QObject` instances, maps, callbacks or
heterogeneous model values. They must not be converted mechanically.

The six generic-parent warnings are more concrete. Expressions such as
`parent.text`, `parent.font` or `parent.selectedState` ask the tooling to find
properties that do not exist on the declared generic `Item` type. Those should
refer to a specifically named object instead.

No `.qmlc` or `.jsc` files are currently generated or packaged. Production
loads `gui/Main.qml` through `QQmlApplicationEngine` and relies on normal Qt
runtime/disk-cache behavior.

## Applicability of the ten recommendations

### Directly useful

1. Avoid generic `parent` property access when the property belongs to a
   concrete subtype. Use an explicit object ID.
2. Qualify property lookups with their owning ID. This reduces accidental
   context coupling and lets linting distinguish real properties.
3. Add parameter and return types to QML functions where the value contract is
   concrete.
4. Introduce `pragma ComponentBehavior: Bound` file by file where delegates or
   inline components intentionally refer to their lexical surroundings.
5. Run `pyside6-qmllint` as a maintained quality check.
6. Experiment with ahead-of-time QML bytecode using
   `pyside6-qmlcachegen --only-bytecode` and package adjacent `.qmlc` files only
   if measurement and all package tests justify it.

### Useful with qualification

- Concrete QML property types improve documentation and tooling, but many
  current `property var` values cross the Python/QML boundary or intentionally
  carry maps. Convert only values with a stable homogeneous contract.
- Required delegate properties are preferable to implicit `modelData`, but a
  delegate conversion must retain the current model and interaction behavior.
- Publishing the backends as explicit root properties instead of implicit
  context names may remove many warnings. Treat that as an architecture change
  with characterization tests, not as a search-and-replace operation.

### Not directly applicable

KDAB's CMake/C++ recommendations around `qt_add_qml_module`, `QML_ELEMENT`,
declarative C++ dependency registration and fully qualified C++ `Q_PROPERTY`
types target a native C++ QML module. LB Omnichord is a PySide application and
does not own such a CMake target. Do not introduce a C++ application layer just
to follow those items.

Qt for Python does provide `pyside6-qmlcachegen`, but its supported Python use
is QML bytecode generation. It does not provide the same QML-to-C++ lowering
described for a native `qt_add_qml_module` target.

## Recommended task order

### 1. Establish a reproducible lint inventory

- Add a script that runs the PySide tool matching the active build environment.
- Store warning category and source-location data in test artifacts.
- Create a reviewed baseline/ratchet similar to the existing mypy ratchet:
  existing warnings may decrease, and new warnings fail the quality gate.
- Do not hide categories globally to obtain a green result.

Acceptance:

- the check runs locally and on all package-host platforms where the pinned
  PySide tool is available;
- path and Qt-version noise is normalized without discarding diagnostics;
- current production QML remains unchanged in this first task.

### 2. Repair definite generic-parent errors

- Resolve the six `missing-property` warnings using concrete IDs.
- Add or retain rendered interaction tests for the affected controls.
- Confirm mouse and touch behavior and visual state before reducing the lint
  baseline.

This is the smallest and least ambiguous source change.

### 3. Make delegate ownership explicit

- Convert implicit delegate roles to `required property` values where their
  model contracts are homogeneous.
- Qualify delegate-owned `index` and `modelData` access.
- Add `pragma ComponentBehavior: Bound` only where lexical ID access is
  intentional.
- Process one component family per diagnostic commit.

Run the QML gesture, slider, screenshot and package-smoke tests after every
component family. Do not combine this with visual redesign.

### 4. Type pure QML calculations

- Start with small numeric helpers such as normalized coordinates, clamps and
  slider conversions.
- Add `real`, `int`, `bool`, `string` and return annotations only where the
  contract is unambiguous.
- Leave Python objects, MIDI target dictionaries and callbacks dynamic unless a
  real typed QML interface is introduced and tested.
- Measure the 120 Hz strum path; do not infer a speedup from fewer warnings.

### 5. Replace implicit backend context lookup deliberately

Investigate declaring required root properties for backend/controller objects
and supplying them before component completion. This could make ownership
clearer even if Python objects still require `var` at the QML boundary.

Before changing it, characterize:

- startup and QML object creation ordering;
- every backend object and list currently published with
  `setContextProperty()`;
- headless, screenshot, AppImage, DMG, Windows and Android startup paths;
- PySide 6.7 aarch64 meta-object behavior already handled by the narrow
  `PerformanceQmlAdapter`.

This task must not replace the existing single composition root or recreate
backend state in QML.

### 6. Measure precompiled QML bytecode

Build a disposable package experiment that generates `.qmlc` with the exact
PySide version used by that package job. Compare at least:

- cold startup to first complete frame;
- warm startup;
- frontend CPU during the external 120 Hz strum workload;
- package size;
- behavior on Linux x86-64, Raspberry Pi aarch64, macOS, Windows and Android.

Only retain QML bytecode when the engine demonstrably consumes it, the source
and cache cannot become version-skewed, package tests cover its presence, and
there is a useful measured benefit. Bytecode is not expected to fix complex or
frequently invalidated scene-graph content.

### 7. Use runtime tools only for remaining measured problems

After the static cleanup, use the QML profiler or GammaRay on an actual slow
interaction. Profile first and preserve traces outside production code. Do not
optimize infrequent setup bindings merely because lint can see them.

## Required regression coverage

Every implementation task must retain or extend coverage for:

- mouse drag, touch drag, tap and framework-classified hold behavior;
- slider handle/fill/backend synchronization;
- MIDI/OSC learn, takeover and manual unlink behavior;
- OMNI/MIDI screen state independence;
- the bounded 30 Hz migraine visual over 120 Hz pointer input;
- the separate-process wire boundary and identical local/serial commands;
- QML load and packaged startup on every supported platform;
- screenshots and current visual-density/error-image checks.

Run at minimum:

```sh
python tests/run_quality.py
python tests/test_qml_gesture_controls.py
python tests/test_labeled_slider_sync.py
python tests/test_migraine_render_budget.py
python tests/run_tests.py --suite frontend
```

The final change must pass `python tests/run_tests.py --suite all` and the full
package matrix. Physical Pi acceptance repeats the external 120 Hz input test;
hosted CI cannot substitute for GPU and audio-deadline evidence.

## Non-goals

- no wholesale QML rewrite;
- no new C++ or Rust frontend layer solely for lint or speculative speed;
- no hand-written gesture timing in Python;
- no visual redesign;
- no platform-specific QML behavior;
- no claim that eliminating warnings automatically improves frame time;
- no weakening or regeneration of a baseline to accept new warnings.

## Sources

- KDAB, *10 Tips to Make Your QML Code Faster and More Maintainable*:
  https://www.kdab.com/10-tips-to-make-your-qml-code-faster-and-more-maintainable/
- Qt for Python, `pyside6-qmlcachegen`:
  https://doc.qt.io/qtforpython-6/tools/pyside-qmlcachegen.html
- Qt for Python tooling overview:
  https://doc.qt.io/qtforpython-6/tools/index.html
- Existing physical performance evidence:
  `../platform/raspberry_pi/frontend_performance.md`
- Test and architecture contracts:
  `../arch/testing.md`, `../arch/principles.md`, `../gui/interaction.md`
