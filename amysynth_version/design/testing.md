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
- `Test and release desktop packages` runs after every update of `main`. It
  calls the complete regression matrix and, only after all suites pass, builds
  and validates Linux x86_64, Raspberry Pi aarch64 and macOS arm64 packages.
  One timestamped tag/release contains all three packages and their SHA-256
  files. Manual dispatch is available for an explicitly requested release
  candidate from another branch; ordinary feature-branch pushes never publish
  releases.
- `ESP32-P4 firmware build` builds and validates the firmware package when the
  ESP32-P4 project changes. It is a build/package check, not part of the Python
  frontend suite.
- `Mirror to Codeberg` mirrors branches and tags. It is delivery automation,
  not a test; concurrency ensures branch-cleanup events collapse to one final
  authoritative mirror.

Pull-request frontend and firmware workflows cancel obsolete runs for the same
ref. Main-branch releases are serialized and never cancelled, so two closely
spaced merges cannot overwrite or skip one another. Regression CI uses Ubuntu
24.04. The x86_64 and Raspberry Pi AppImages are built natively on Ubuntu 22.04
x86_64/aarch64 runners; the DMG is built natively on a macOS 15 arm64 runner.
Diagnostics are retained for 14 days where a workflow produces artifacts.

## Linux release naming and contents

Release timestamps are UTC. A main update at `2026-08-24 22:30:00 UTC` creates:

- Git tag and release: `R20260824T223000`
- Linux asset: `LB_Omnichord.R20260824223000.Linux-x86_64.AppImage`
- Raspberry Pi asset: `LB_Omnichord.R20260824223000.RaspberryPi-aarch64.AppImage`
- macOS asset: `LB_Omnichord.R20260824223000.macOS-arm64.dmg`
- one matching `.sha256` file for each package

The AppImages bundle PySide6, the frontend assets and the pinned AMY bus-mixer
fork built with the ESP32-compatible tiny PCM bank. The executable starts AMY
as a separate child process. Linux uses the existing Unix `SOCK_SEQPACKET`
wire-protocol boundary. macOS uses newline-framed Unix `SOCK_STREAM`, because
Darwin does not support Unix-domain `SOCK_SEQPACKET`. Packaging therefore does
not collapse the application and synthesizer architectures into one process.

`packaging/build_appimage.sh` builds either Linux AppImage;
`packaging/build_macos_dmg.sh` builds the Apple Silicon application/DMG. The
workflow pins PyInstaller and verifies SHA-256 hashes for each architecture's
appimagetool and type-2 runtime. `--package-self-test` verifies imports and
required assets on all platforms. CI starts each final package and requires
both the AMY-service-ready and frontend-socket-connection markers before
publishing. The DMG is first verified and mounted read-only; CI starts the app
from that mounted release image. Native/headless Linux CI uses
`tests/alsa-null.conf`: AMY runs its real audio callback against ALSA's null PCM
without requiring an audio card.

The Raspberry Pi package targets 64-bit Raspberry Pi OS on Pi 4 and Pi 5. It is
built natively as aarch64 using Pi 4 as the minimum CPU baseline; Pi 5 does not
need a separate build. Pi 3 and older are outside the packaging contract. The
macOS package targets Apple Silicon (`arm64`). It is ad-hoc signed for bundle
integrity but is not Apple-notarized; Intel/universal packaging and notarization
are separate future work.

## Validated release baseline

The first end-to-end release-candidate run was validated on 2026-08-24:

- all 79 tests passed on GitHub Actions, including both native 11-bus suites;
- CI built, self-tested and headless-started the AppImage from a clean home;
- clean startup installed the packaged MIDI factory presets M1–M18;
- tag `R20260824T204611` and its x86_64 AppImage/SHA-256 assets were published;
- that published x86_64 AppImage was downloaded from GitHub Releases and
  physically tested on Linux with working UI and audio.

This proves the release mechanism and that particular x86_64 artifact. The
first complete three-platform release, `R20260824T212125`, subsequently passed
all 80 tests and final-package startup on native x64 Linux, native aarch64 Linux
and native Apple-Silicon macOS runners. It published all three packages and
their checksums only after AMY and Qt connected successfully. The Raspberry Pi
and macOS packages still require their first physical-device/audio test.
Future releases are not automatically considered physically tested merely
because the pipeline succeeded.

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
- legacy user data migrates to separate OMNI/MIDI preset directories
- editable user configuration is seeded once and has startup priority
- APG and chord-family LDR strum note sets remain deterministic
- MIDI CC running status updates indicators without changing musical state;
  indicators fill the available width before least-recently-used replacement
- instrument balance captures cover low/middle/high registers and report RMS,
  peak, crest factor and clipping
