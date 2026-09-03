# Codex handover: production/test process separation implementation

Status: implemented on `architecture/test_separation`
Date: 2026-09-03
Authority: `test_process_architecture.md`

## Objective

This branch implements architecture items 1, 2, 3, 5 and 6 from the test
process audit. The user explicitly accepted item 4: deterministic repository
screenshot functionality may remain in the production application. That
exception does not turn screenshots into MIDI, OSC or physical-input evidence.

## Result

Production code and shipped packages no longer contain the package-smoke
driver, checkpoint/status protocol, Android smoke marker, QtTest pointer driver,
synthetic external-input QObject slots, test-only MIDI log or native Windows
self-test. QtTest remains available to source tests, while QtTest and QtWidgets
are absent from the reviewed product runtime manifest and package builders.

Headless source integration retains synthetic actions through
`tests/support/backend_control_surface.py`. That adapter is composed only by
`tests/integration/headless_app.py`; it is not reachable from the production
dependency graph or included in release packages. The Linux native MIDI test
now observes the mapped AMY wire effect through the real Unix-socket boundary
instead of asking production code to write a test log.

Package launch validation now uses the documented screenshot operation. Linux,
Raspberry Pi, macOS and Windows launch the final artifact and validate two
rendered PNGs. Android starts the installed APK normally, sends a long press
from the separate adb process, captures frames externally and retains its real
Oboe render/output comparison.

## Central scenarios and evidence

`qt_frontend/tests/support/package_evidence.py` is the single owner of package
scenario names and expectations. Platform scripts only create native endpoints,
launch processes and collect evidence files. The evaluator checks:

- non-empty final artifact and SHA-256;
- matching package audit with no forbidden Qt runtime;
- reviewed/scanned or Android-pruned QML module evidence;
- successful independent-process portable MIDI/OSC contract;
- platform-appropriate runtime/service markers and no Python traceback;
- at least two non-trivial PNG files with real PNG signatures;
- success of the shared regression prerequisite;
- optional platform-native audio evidence.

It emits one `<artifact>.evidence.json` (or Android
`package-evidence.json`) with separate evidence classes. It never describes a
portable parser pipe as native MIDI or a staged screenshot control as physical
OSC/MIDI input.

## Commit sequence

- `ac2d0ec` removes package-test orchestration from application startup.
- `91f6838` removes production inject/log hooks and adds a test-only adapter.
- `c3f5af8` removes QtTest/QtWidgets from product package policy.
- `11aa72f` externalizes package acceptance and adds the central evidence
  evaluator; subsequent commits document and harden that result.

## Validation and continuation

Focused composition, runtime, MIDI-engine, screenshot-state, package-policy,
Android-packaging, packaging-contract and evidence tests passed during the
implementation. `tests/run_quality.py` also passed.

The complete regression and package workflow passed for implementation commit
`5ae403d` in GitHub Actions run `33783248461`. The run built and exercised the
Linux x86_64, Raspberry Pi aarch64, Windows x86_64, macOS arm64, Android x86_64
and Android arm64 outputs. Every runnable desktop package emitted a passing
seven-scenario evidence manifest. The installed Android x86_64 APK emitted a
passing eight-scenario manifest, including separate-process OSC input, rendered
UI, AMY/Oboe audio and byte-identical AMY/Oboe output evidence.

An earlier hosted emulator run also exposed an important timing boundary: the
Android QPA-ready message can precede the first rendered QML frame. Input sent
at that boundary was correctly external, but arrived while the surface was
still blank and therefore generated no audio. The Android harness now waits
for a detailed screenshot from the installed application before sending its
adb long press. Both the pre-input and post-input captures in the successful
run contain the rendered application, and the captured audio peaked at
`-15.765 dBFS` with zero AMY/Oboe sample mismatches.
