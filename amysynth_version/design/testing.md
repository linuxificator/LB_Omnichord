# Testing Design

Tests are based on the executable use cases in
`../qt_frontend/tests/USE_CASES.md`. The Sonic Pi implementation is frozen
legacy material and is outside these tests and workflows.

`qt_frontend/tests/run_tests.py` is the single local and CI entry point. Its
`unit` suite automatically discovers every top-level `test_*.py`; integration
suites remain explicit because they have different runtime/native-AMY needs.
The native suites start AMY with the production capacity of 11 buses and 336
oscillators. CI installs a pinned revision of the LB Omnichord AMY bus-mixer
fork so a passing run tests the deployed architecture reproducibly.

## Local suites

Run commands from `qt_frontend` in the frontend virtual environment:

```bash
python tests/run_tests.py --list
python tests/run_tests.py                 # unit, the default
python tests/run_tests.py --suite all     # complete local matrix
```

The maintained suites are:

| Suite | Scope | Extra requirement |
| --- | --- | --- |
| `unit` | all top-level `tests/test_*.py` contracts | none beyond frontend dependencies |
| `frontend` | headless QML/backend interaction | PySide6 and local TCP/PTY support |
| `serial` | production pyserial output over a Linux PTY | pyserial and PTY support |
| `presets` | factory/user preset loading and migration | PySide6 and PTY support |
| `native-controls` | delivered wire commands and native synth state | pinned LB AMY fork |
| `native-rhythm` | sequencer/rhythm behavior in native AMY | pinned LB AMY fork |
| `all` | all suites above, in dependency order | all requirements above |

Top-level unit tests are discovered automatically. Integration suites are
listed explicitly because their process, PTY and native-engine requirements
differ. `test-artifacts/<suite>/` is recreated for every suite invocation and
is intentionally ignored by Git.

## GitHub Actions

Four repository workflows are maintained:

- `AMY frontend regression` runs the six component suites in parallel for AMY
  frontend pull requests, is reused as the test gate of the release workflow,
  and accepts a selected suite or `all` through manual dispatch. Native jobs
  install the AMY fork at the commit pinned in the workflow and record that SHA
  in their artifacts.
- `Test and release Linux AppImage` runs after every update of `main`. It calls
  the complete regression matrix and, only after all suites pass, builds and
  validates the x86_64 AppImage, creates the timestamped tag and publishes both
  the AppImage and its SHA-256 file as a GitHub Release. Manual dispatch is
  available for an explicitly requested release candidate from another branch;
  ordinary feature-branch pushes never publish releases.
- `ESP32-P4 firmware build` builds and validates the firmware package when the
  ESP32-P4 project changes. It is a build/package check, not part of the Python
  frontend suite.
- `Mirror to Codeberg` mirrors branches and tags. It is delivery automation,
  not a test; concurrency ensures branch-cleanup events collapse to one final
  authoritative mirror.

Pull-request frontend and firmware workflows cancel obsolete runs for the same
ref. Main-branch releases are serialized and never cancelled, so two closely
spaced merges cannot overwrite or skip one another. Regression CI uses Ubuntu
24.04; the AppImage is built on Ubuntu 22.04 for broader glibc compatibility.
Diagnostics are retained for 14 days where a workflow produces artifacts.

## Linux release naming and contents

Release timestamps are UTC. A main update at `2026-08-24 22:30:00 UTC` creates:

- Git tag and release: `R20260824T223000`
- application asset: `LB_Omnichord.R20260824223000.AppImage`
- checksum asset: `LB_Omnichord.R20260824223000.AppImage.sha256`

The AppImage bundles PySide6, the frontend assets and the pinned AMY bus-mixer
fork built with the ESP32-compatible tiny PCM bank. The executable starts AMY
as a separate child process and connects the Qt process through the existing
Unix `SOCK_SEQPACKET` wire-protocol boundary. Packaging therefore does not
collapse the application and synthesizer architectures into one process.

`packaging/build_appimage.sh` is the local and CI build entry point. The
workflow pins PyInstaller and verifies SHA-256 hashes for appimagetool and its
type-2 runtime. The packaged `--appimage-self-test` verifies imports and
required assets; CI then performs a timed headless launch and requires both the
AMY-service-ready and frontend-socket-connection markers before creating a
release. Native CI uses `tests/alsa-null.conf`: AMY runs its real audio callback
against ALSA's null PCM, so engine startup is exercised without pretending the
hosted runner has an audio card.

Each test should verify:

- initial state
- user action
- visible UI result
- AMY wire commands
- persistence behavior

Important regression tests:

- OMNI/MIDI switching does not affect sound
- tuning coupling works from both screens
- coupled tuning updates both views
- decoupled tuning stays independent
- local and serial AMY transports generate identical commands
- raw-MIDI running status, Note On/Off and velocity-zero Note Off parsing
- incoming EQ/HARM/JV MIDI conversion to exact/fractional AMY notes
- MIDI preview stays within its live voice allocation and emits no stale offs
- OMNI and MIDI reverb controls generate commands for only their owned buses
- live preset/rhythm changes preserve tempo without transport/timebase reset
