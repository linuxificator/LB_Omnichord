# Codex handover: test-process and platform-equivalence audit

Status: current implementation audit against `test_process_architecture.md`
Audit date: 2026-09-03
Audit branch start: `main` at `20ad1ba77981d9c28a4a0821a2b178d27a7debea`

## Scope and method

This audit searched production Python, QML, launchers, packaging scripts,
release workflow and test layout for test-only modes, markers, environment
variables, injectors, assertions and duplicated platform acceptance. It also
compared the OSC/MIDI package evidence added in release `R20260903T114635`
with the actual process topology.

That release is useful evidence but does not satisfy the stricter contract:
its OSC datagram traverses the kernel UDP stack while sender and receiver still
live in one Omnichord process, and its packaged MIDI events enter through
direct QObject simulation slots.

## Violations found

### V1 — package test orchestration is shipped in production modules

`code/app_core.py` parses `--package-smoke-test`, creates checkpoints, imports
`code/package_smoke.py`, drives input/assertions and exits on the result.
`code/package_test_hooks.py`, `code/windows_launcher.py` and
`code/runtime_platform_adapters.py` implement test-only environment/status and
Android marker protocols. PyInstaller scripts deliberately bundle
`package_smoke` and `PySide6.QtTest`.

Impact: the application under test contains its own test controller and users
receive test-only QtTest/runtime code. Process, packaging and behavior can
agree with themselves while an external peer still fails.

### V2 — OSC package stimulus is self-generated

`code/package_smoke.py` creates a UDP sender socket, builds OSC packets, sends
them to its own listener and inspects its own controller model/activity state.
This proves socket/parser/Qt delivery but not an independent sender process.

Required first correction: move OSC packet generation and timing to a
test-only executable process. The Omnichord must receive only through its
ordinary configured UDP listener.

### V3 — packaged MIDI evidence bypasses every native input adapter

The same module calls `MidiPlayerBackend.injectControl()` and `injectButton()`.
The screenshot path uses related injection slots. This proves common binding
presentation only; it does not prove raw MIDI, CoreMIDI, WinMM or Android MIDI.

Linux already has a stronger source integration: a parent test process starts
the Omnichord subprocess and writes real MIDI bytes through a PTY-backed raw
reader. macOS, Windows and Android currently have no bundled native MIDI
bridge, so their honest adapter outcome is unavailable. Portable MIDI parser
contracts can run in separated processes everywhere, but they must not be
named or reported as native physical-input tests.

### V4 — test-only logging and public injection surface exist in production

`OMNICHORD_TEST_MIDI_CC_LOG` changes `midi_player.py` behavior for a test.
`injectControl`, `injectOscControl`, `injectPitchBend` and `injectButton` are
public QObject slots primarily used by tests/screenshots. Even when useful for
manual demonstrations, they are not a physical input boundary and create a
second way into external-control state.

Required follow-up: replace integration-test observation with ordinary bounded
diagnostics or external observation, move deterministic screenshot staging to
an external/test composition, then remove the test environment variable and
production injection slots when no supported user API owns them.

### V5 — pointer/chord/slider package tests are also self-driven

`code/package_smoke.py` uses `QTest` inside the Omnichord to find QML objects,
send pointer events, inspect private backend sets and verify slider geometry.
This is outside the immediate MIDI/OSC correction but violates the same rule.
It must eventually move to an external UI automation/accessibility driver or a
separately composed test executable that is not shipped to users.

### V6 — screenshot capture behavior shares the production startup runner

`--capture-screenshots-dir` and screenshot timing/capture logic live in
`app_core.py`; `screenshot_state.py` uses production injection slots. The
top-level `capture_screenshots.py` is a separate process, but delegates the
actual staging and pass/fail work back into the application. This is a
tooling/product boundary violation, though lower risk than package acceptance.

### V7 — generic and platform test responsibilities are mixed

`tests/test_packaging.py` asserts duplicated checkpoint strings embedded in
YAML, PowerShell and shell. The release workflow, Windows launcher and Android
script each own overlapping test expectations. Platform setup and semantic
assertions are therefore copied rather than driven by one generic contract.

There is no `tests/platform/<target>` ownership split. Most cross-platform
profile cases execute on Linux by passing a platform string, which is useful
unit coverage but not equivalent native-package execution.

### V8 — evidence names overstate equivalence

The previous package checkpoints combine real OSC UDP, direct MIDI simulation
and platform capability status in one in-process function. Although docs note
the limitations, identical green checkpoint treatment makes distinct evidence
strength hard to see in the release result.

Required correction: use separate scenario/result names for portable parser,
external-process transport, native adapter and physical validation.

## Implementation order

1. Establish one test-only external-input contract and result format.
2. Move OSC stimulus to a separate process on desktop and Android package
   paths; remove self-sending from `code/package_smoke.py`.
3. Move portable MIDI byte/parser stimulus to a separate sender/receiver
   process contract on every platform runner.
4. Keep Linux native PTY/raw-MIDI as its own platform adapter test. Add explicit
   unavailable adapter acceptance for macOS, Windows and Android without fake
   MIDI events.
5. Remove packaged MIDI `inject*` evidence and rename release results so their
   strength is unambiguous.
6. Consolidate shared scenarios/assertions under `tests/contracts` and native
   setup under `tests/platform`/`tests/support`.
7. In later tasks, externalize pointer/slider/chord and screenshot tests, then
   delete package-smoke/test-hook behavior from production modules and package
   manifests.

## Non-goals of the immediate correction

- implementing CoreMIDI, WinMM or Android MIDI product adapters;
- calling parser-pipe simulation physical MIDI;
- weakening existing AMY, QML or audio package gates;
- moving platform branches into shared application code;
- bundling a general test-control server in release packages.

## Implementation result on this branch

Commits `61f1f6b` and `6be53d1` establish the contract and the first boundary
correction. The following evidence now exists:

- `tests/contracts/test_external_input_processes.py` runs identical portable
  OSC and MIDI semantics without OS branches. Both scenarios assert that the
  sender PID differs from the receiver PID.
- `tests/support/external_input_peer.py` owns OSC datagrams and MIDI bytes;
  `external_input_probe.py` owns portable receiving/parsing. Neither is staged
  into application packages.
- Linux/Raspberry Pi, macOS, Windows and Android package builders run that same
  portable process contract. It proves parser/transport portability, not a
  native MIDI bridge.
- Every desktop artifact receives OSC from a separately launched Python
  process. Android receives the same binary OSC messages from a separate
  `adb shell` process inside the emulator.
- the former self-sending OSC socket and direct packaged MIDI injection were
  removed from `code/package_smoke.py`;
- Linux native MIDI moved from top-level unit discovery to
  `tests/platform/linux/test_midi_input.py`. Its controller process owns the
  PTY bytes and the Omnichord runs as an independent process.
- macOS, Windows and Android retain an honest package assertion that their
  currently unbundled native MIDI bridge is unavailable. No fake native MIDI
  event is reported under those platform names.

V2 and V3 are resolved. V7 and V8 are improved: portable versus Linux-native
evidence now has separate suite/checkpoint names, but duplicated package-smoke
checkpoint assertions and platform workflow orchestration remain. V1, V4, V5
and V6 remain open and are deliberately reported rather than hidden by this
focused change.
