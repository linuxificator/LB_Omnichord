# Resume: external-input test architecture

Status: resumable checkpoint
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
  receives the same OSC fixtures from a separate `adb shell` process.
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

## Current blocker: GitHub CLI authentication

The five-platform non-publishing workflow has **not** run for this branch.
Attempting to start it with:

```bash
gh workflow run desktop-release.yml \
  --ref rework/external_input_test_architecture
```

failed with:

```text
HTTP 401: Requires authentication
```

`gh auth status` reports that the active `linuxificator` token in
`~/.config/gh/hosts.yml` is invalid. This is independent of Git transport:
`git push origin rework/external_input_test_architecture` succeeds with the SSH
deploy key. Do not change the working Git remote or SSH key to repair `gh`.

To resume platform validation, authenticate `gh` for the `linuxificator`
account with permission to dispatch Actions, then run the command above. A
manual dispatch on this featurebranch builds/tests all platforms but does not
publish a release because publication is restricted to `main`. Follow all jobs
and repair failures on this branch before proposing a merge.

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

The next action is platform CI validation, not a merge and not an unrelated
refactor. After CI is green, report the exact run and any still-unverified
physical hardware paths to the user.
