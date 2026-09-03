# Resume: external-input test architecture

Status: implemented and validated checkpoint
Recorded: 2026-09-03, Europe/Amsterdam
Repository: `/home/jeroen/omnichord/LB_Omnichord`
Branch: `rework/external_input_test_architecture`
Remote: `origin` (`linuxificator/LB_Omnichord`)

## Exact branch state

The implementation and documentation before this checkpoint are committed and
were pushed through the working SSH deploy key. The relevant history is:

- `61f1f6b` — Define test process architecture
- `6be53d1` — Separate external input test processes
- `9d02120` — Document portable and platform input evidence
- `68bd738` — Separate unit and platform input suites
- `bc0e0e2` — Record external input architecture resume state
- `9adcbe2` — Install Android OSC test peer dependency
- `2b75cb9` — Keep Android test dependency declaration explicit
- `6b6bfc3` — Route Android OSC test across emulator network
- `6613941` — Avoid Android OSC sender teardown race

Do not resume from `main`; resume from the remote branch above. This branch is
based on `main` commit `20ad1ba` and has not been merged to `main`.

## Implemented state

- The authoritative contract is
  `amysynth_version/design/test_process_architecture.md`.
- The detailed audit and remaining violations are in
  `amysynth_version/design/CODEX_HANDOVER_TEST_PROCESS_ARCHITECTURE_AUDIT.md`.
- Portable MIDI and OSC contracts require distinct sender/receiver PIDs and
  live in `qt_frontend/tests/contracts/test_external_input_processes.py`.
- Test-only senders and probes live under `qt_frontend/tests/support/` and are
  not staged into user packages.
- Desktop package tests receive OSC from a separate Python process. Android
  receives it from a separate host process through emulator UDP redirection.
- Linux native MIDI and the Unix source-package smoke are isolated under
  `qt_frontend/tests/platform/linux/`.
- `unit`, `portable-input-processes` and `platform-input-linux` are separate
  runner/CI suites.
- Linux/Raspberry Pi, macOS, Windows and Android package-build jobs invoke the
  same portable process contract. CoreMIDI, WinMM and Android MIDI remain
  explicitly unavailable; the portable parser test is not labelled physical
  or native MIDI evidence.

## Verification already completed

The following passed locally at `68bd738`:

- complete `unit` suite;
- `portable-input-processes`;
- `platform-input-linux`;
- `tests/run_quality.py` (`37/42` legacy mypy errors; 29 new modules strict);
- packaging, static-contract, repository-hygiene and program-architecture
  tests;
- Python compilation of the new helpers/tests;
- YAML parsing of both changed workflows;
- `bash -n` for the changed Android package test.

The remote branch was verified at
`68bd7387bc1c57482892fa8b48a132f3e84d962b` before adding this resume file.

## Remote platform validation

GitHub CLI authentication was restored. The definitive non-publishing
five-platform workflow is
[run 33767634170](https://github.com/linuxificator/LB_Omnichord/actions/runs/33767634170)
at commit `6613941dc94e8f1e1fc54ae7dd76399d9cd45f53`. It completed successfully.

The successful run covers:

- all nine regression suites, including the portable external-process and
  Linux platform-input suites;
- Linux x86_64 AppImage and Raspberry Pi aarch64 AppImage;
- the Windows native service plus portable application;
- the macOS DMG;
- Android x86_64 and arm64 APKs; and
- the installed x86_64 Android application in an emulator.

The Android evidence contains an independent host sender process targeting
`127.0.0.1:8000` through emulator UDP redirection. The app observed the OSC
rotary, button and activity events and also passed its AMY/Oboe audio,
chord-input and slider-drag checkpoints. The sender is deliberately terminated
when the app finishes; the test therefore requires its start record and the
three receiver-side observations, not an unreachable normal-exit record.

This manual feature-branch run did not publish a release and this branch has
not been merged to `main`.

## Remaining architecture violations

The current work intentionally does not conceal these open findings:

1. `app_core.py`, `package_smoke.py`, `package_test_hooks.py` and runtime
   adapters still ship package-test orchestration/checkpoints.
2. `PySide6.QtTest` is still bundled for internal chord/slider package smoke.
3. `OMNICHORD_TEST_MIDI_CC_LOG` and public `inject*` slots remain in production
   code for integration/screenshot tooling.
4. Screenshot staging and `--capture-screenshots-dir` remain in production
   startup code.
5. Package checkpoint lists remain duplicated across YAML, Bash, PowerShell
   and the Linux source-package test.
6. Evidence classes are described accurately, but are not yet emitted through
   one central machine-readable evidence manifest.

The focused process-separation work is validated. A merge remains a separate
decision. CoreMIDI, WinMM and Android physical/native MIDI input remain
unverified because those product adapters do not currently exist; portable
parser evidence is not presented as physical-input evidence.

## Validation continuation after `gh` recovery

GitHub CLI authentication was restored and manual run `33761942285` was
started for checkpoint `bc0e0e2`. All regression suites, both Linux packages,
macOS, Windows and both Android APK builds passed. The Android emulator alone
failed before sending a packet because its host-side test controller invoked
`external_input_peer.py` without installing its declared `python-osc`
dependency (`ModuleNotFoundError: No module named 'pythonosc'`). The repair
installs the shared pinned `requirements-portable.txt` only in the emulator
test job; it does not add anything to the Android application package.

Run `33763712771` confirmed that dependency repair and progressed to the real
Android app, but the `toybox nc` guest-shell sender produced no observable
datagrams. The follow-up replaces that implementation with Android Emulator's
documented `redir add udp:host-port:guest-port` boundary and runs the shared
Python OSC peer as an independent host process. Run `33765963115` proved that
this boundary delivers all three OSC event classes to the app, then exposed a
false teardown assertion: the sender was intentionally terminated before it
could write its normal-exit packet count. Commit `6613941` removed only that
assertion, retaining the sender-start and receiver-observation requirements;
the definitive run above is green.
