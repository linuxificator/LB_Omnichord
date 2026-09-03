# Testing Design

Status: authoritative test and release validation contract
Owner: frontend test/release architecture
Applies to: active `amysynth_version` implementation
Last verified: 2026-09-01

Tests are based on the executable use cases in
`../qt_frontend/tests/USE_CASES.md`. The Sonic Pi implementation is frozen
legacy material and is outside these tests and workflows.

`qt_frontend/tests/run_tests.py` is the single local and CI entry point. Its
`unit` suite automatically discovers every top-level `test_*.py`; integration
suites remain explicit because they have different runtime/native-AMY needs.
The native suites start AMY with the production capacity of 11 buses, 336
oscillators, 1024 stored patterns, 64 events per pattern and 32 active pattern
instances. CI installs the exact pinned LB Omnichord AMY release so a passing
run tests the deployed architecture reproducibly.

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
| `quality` | compileall, shipped JSON, Markdown/status/routing, import/dependency boundaries, Ruff and mypy ratchets | declared test/quality requirements; no AMY/audio/display |
| `unit` | all top-level `tests/test_*.py` contracts | none beyond frontend dependencies |
| `frontend` | headless QML/backend interaction | PySide6 and local TCP/PTY support |
| `serial` | production pyserial output over a Linux PTY | pyserial and PTY support |
| `presets` | factory/user preset loading and migration | PySide6 and PTY support |
| `native-controls` | delivered wire commands and native synth state | pinned Gamma9001 LB AMY fork, offline renderer |
| `native-rhythm` | sequencer/rhythm behavior in native AMY | pinned Gamma9001 LB AMY fork, offline renderer |
| `all` | all suites above, in dependency order | all requirements above |

The quality suite is deliberately non-mutating. Ruff checks a small
correctness-critical rule set and does not format source. Mypy compares current
legacy diagnostics by file/error-code with
`tests/quality/mypy_legacy_baseline.json`; the total and every bucket may only
decrease. A new production module is absent from that legacy list and must pass
`mypy --strict --follow-imports=skip`. Do not regenerate the baseline to make a
new error pass: fix the error, or document and review an intentional baseline
change as code-quality work.

Run the fast gate directly with:

```bash
python tests/run_quality.py
```

Every `run_tests.py` invocation atomically writes a versioned JSON report with
the selected suite, each isolated script's status/duration, total duration,
repository commit and pinned AMY commit. CI uploads it even when a script
fails. `--coverage` uses coverage.py's subprocess patch and parallel data
files, then combines them into navigational branch data without a global
percentage threshold. The reusable workflow applies this selectively to the
pure/unit suite; native/package tests remain acceptance evidence rather than
being distorted to raise a coverage number.

Top-level unit tests are discovered automatically. Integration suites are
listed explicitly because their process, PTY and native-engine requirements
differ. `test-artifacts/<suite>/` is recreated for every suite invocation and
is intentionally ignored by Git.

Musical catalogue tests exercise four separate failure boundaries: versioned
schema shape, row-local musical constraints, cross-catalogue references and
immutable constructed indexes. `test_catalogue_provenance.py` additionally
verifies the committed byte hashes and declared item counts. A catalogue edit
must therefore deliberately update its provenance record; merely accepting a
new shape at runtime is not sufficient review evidence.

## GitHub Actions

Four repository workflows are maintained:

- `AMY frontend regression` runs the quality gate and six component suites in parallel for AMY
  frontend pull requests, is reused as the test gate of the release workflow,
  and accepts a selected suite or `all` through manual dispatch. Native jobs
  install the AMY fork at the commit pinned in the workflow and record that SHA
  in their artifacts.
- `Test and release platform packages` runs after every update of `main`. It
  calls the complete regression matrix and, only after all suites pass, builds
  and validates Linux x86_64, Raspberry Pi aarch64, macOS arm64 and native
  Windows x86_64 packages plus the Android arm64 APK. One timestamped
  tag/release contains all five packages, their SHA-256 files and an exact
  `release-manifest.json`. It also publishes a release-level SPDX 2.3 SBOM and
  retained Sigstore bundles. GitHub signs build-provenance and SBOM
  attestations for the exact five manifest digests; the workflow verifies both
  predicates independently before publication. The manifest verifier rejects missing or extra
  package/checksum files before publication; the final GitHub asset-name list
  is compared with the manifest after upload. The dedicated
  `testing/windows_smoke`
  branch builds only the Windows job without publishing; `main` retains the
  complete gated release. The native package/smoke job runs on the current
  Windows Server 2025 image and verifies the Qt named-pipe boundary; Windows is
  not represented by the Linux AppImage or WSL.
  The dedicated `integration/android_build` branch runs every frontend suite,
  builds only Android x86_64/arm64 packages, and installs the x86_64 APK in an
  emulator. That smoke drives the packaged QML tap/hold path through the
  app-private socket and verifies AMY's render samples equal the samples handed
  to Oboe before Android joins the complete `main` release gate. The package
  builder also verifies Qt's compiled Android library array is dependency
  ordered, with `Quick` loaded before `QuickControls2`, so JNI initialization
  cannot depend on Python set iteration order.
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
The Windows zip is built and exercised on Windows Server 2025 build 26100 with
the newest supported installed Visual Studio generator. Diagnostics are
retained for 14 days where a workflow produces artifacts.

The README screenshot refresh retains the newest three release-tagged OMNI and
MIDI image pairs in Git. Filenames remain directly traceable to a release;
older images remain recoverable from Git history instead of accumulating in
the branch tip. The untagged capture baselines remain committed. Every new
pair must still pass PNG decoding, exact-dimension and visual-density checks
before README promotion, so retention never weakens the crash/error-image
sanity gate.

## Desktop release naming and contents

Release timestamps are UTC. A main update at `2026-08-24 22:30:00 UTC` creates:

- Git tag and release: `R20260824T223000`
- Linux asset: `LB_Omnichord.R20260824223000.Linux-x86_64.AppImage`
- Raspberry Pi asset: `LB_Omnichord.R20260824223000.RaspberryPi-aarch64.AppImage`
- macOS asset: `LB_Omnichord.R20260824223000.macOS-arm64.dmg`
- Windows asset: `LB_Omnichord.R20260824223000.Windows-x86_64.zip`
- Android asset: `LB_Omnichord.R20260824223000.Android-arm64.apk`
- one matching `.sha256` file for each package
- `release-manifest.json`, one `LB_Omnichord.<stamp>.spdx.json` and two
  retained Sigstore attestation bundles

The AppImages bundle PySide6, the frontend assets and the pinned AMY release
built with the Gamma9001 PCM bank. The executable starts AMY
as a separate child process. Unix IPC selects the best endpoint capability:
packet-preserving `SOCK_SEQPACKET` where accepted, otherwise newline-framed
`SOCK_STREAM`. The runtime has no OS-name branch for this choice. Packaging
therefore does not collapse the application and synthesizer architectures into
one process.

The Windows zip also preserves two processes: frozen `LB_Omnichord.exe`
connects through `QLocalSocket` to a private named pipe owned by native
`amy_service.exe`. The package launcher supplies a unique pipe name and owns
process cleanup. Windows CMake builds pinned AMY with `GAMMA9001`, generates
and links `drums_bin.c`, and registers it before AMY starts, matching Linux,
Raspberry Pi, macOS and Android.

The Android APK likewise preserves two processes. The PySide6 activity is a
wire-only client, while an unexported AAR provider starts AMY/Oboe in `:amy`.
CI creates private one-shot markers so the packaged QML chord smoke produces
audio, then compares the captured AMY render buffer and exact Oboe callback
buffer. The published arm64 APK is debug-signed and explicitly experimental;
stable distribution signing and physical-device validation remain separate
acceptance steps.

All five package jobs run the complete packaged-input smoke. It sends real OSC
1.0 UDP datagrams through the package's configured listener and requires a
rotary, pushbutton and green activity state to reach the shared Qt control
model. It also verifies the package's actual MIDI profile: Linux exposes only
ALSA raw, ALSA sequencer and OSS MIDI, while macOS, Windows and Android expose
their platform-relevant native technology as explicitly unavailable until a
bridge is bundled. Public MIDI simulation slots exercise the frozen package's
shared CC and controller-button model after that adapter selection. Separately,
the Linux Qt integration test writes real MIDI bytes through a PTY-backed raw
device and verifies the native reader, parser, queued Qt boundary, model and
binding path end to end.

This is the maximum deterministic hosted-CI boundary currently available. OSC
loopback proves socket creation, packet parsing and application delivery but
not firewall permission or packets from a second physical host. The simulated
MIDI portion is not physical MIDI evidence, and CoreMIDI, WinMM and Android
MIDI cannot be physical-input tested while those native bridges remain
unimplemented. Their red unavailable state is therefore an intentional,
tested capability result rather than a false support claim.

The macOS and Windows package jobs drive both a quick tap and a long press
classified by the real packaged QML `TapHandler`, using synthesized Qt pointer
events and Qt's platform long-press interval. The same package smoke drags a
visible production synth-parameter slider and verifies that its native value,
custom handle and fill remain aligned both during the drag and after release.
They require the active-border state, tap release, hold takeover, hold release
and slider-visual checkpoints before publication; hold release must be visible
on the first event-loop turn rather than after a grace timer. The Windows job
invokes the packaged `LB_Omnichord.cmd` double-click entry point, which in turn
starts the PowerShell supervisor with a process-only execution-policy bypass.
These hosted tests do not replace physical trackpad/touchscreen or
audible-output validation.

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

The first complete four-platform release, `R20260826T230234`, was built from
main commit `3345502` by GitHub Actions run `33021825480`. All six frontend
suites and all four package jobs passed before publication. The Windows job
validated native compilation, a non-silent offline AMY self-test, and the
extracted frozen frontend communicating real wire commands with the separate
service through the named pipe. It observed 209 wire commands and 13,138
nonzero rendered samples in that end-to-end smoke.

This establishes an experimental native Windows package/runtime baseline, not
physical Windows support. Real audio output, MIDI input, latency and drop-out
behavior remain unverified; native Windows MIDI is not yet implemented. The
acceptance boundary is maintained in `../qt_frontend/docs/WINDOWS_NATIVE.md`.
The WSL AppImage guide is only an optional experiment with the Linux artifact.

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
- Pitch Bend parsing and 14-bit centered MIDI-learn mapping
- incoming EQ/HARM/JV MIDI conversion to exact/fractional AMY notes
- MIDI preview stays within its live voice allocation and emits no stale offs
- OMNI and MIDI reverb controls generate commands for only their owned buses
- live preset/rhythm changes preserve tempo without transport/timebase reset
- legacy user data migrates to separate OMNI/MIDI preset directories
- editable user configuration is seeded once and has startup priority
- APG and every explicitly mapped chord-suffix LDR pitch set remain
  deterministic, contain all chord tones and preserve musical enharmonic
  spelling
- APG/LDR mode stores and reloads with OMNI presets, with APG as the legacy
  fallback
- every MIDI-bound numeric value rejects manual/tap/drag/setter/nudge/copy
  writes and survives section RST and runtime preset selection on both screens,
  including hidden instrument targets and bindings introduced by the
  destination preset
- MIDI-bound tempo and effective tuning disable and grey their UP/DOWN buttons;
  tuning recoupling takes authority from a bound side and refuses divergent
  dual-bound references
- OMNI and MIDI reverb level reaches 3.0 through UI/backend clamping, MIDI CC
  mapping and the owned AMY bus commands
- MIDI CC running status updates indicators without changing musical state;
  indicators fill the available width before least-recently-used replacement
- MIDI input tech LEDs expose only platform-relevant technologies, show red for
  unavailable/unimplemented runtime inputs, green for readable listened-to
  byte-stream inputs and blinking green after incoming bytes
- MIDI CC learn permits one red controller, binds every continuous numeric
  control family one-to-one, maps logarithmic sliders over visual travel,
  protects red/blue indicators, preserves hidden instrument-specific bindings,
  unlinks before applying the first real bound drag/edit value, keeps a bound
  press without movement coupled, gives green/blue/grey/red indicator clicks
  their state-specific single-click meanings,
  expires blue state and persists bindings in the owning MIDI or OMNI preset
- CC-style MIDI controller-button learn binds supported app buttons, presses
  through the same backend action as a screen tap, shows the same button LED
  colors as sliders, scopes on/off takeover to the target's logical button
  group, keeps tap-only actions from holding takeover state, and never treats
  ordinary musical Note On/Off as controller buttons
- the rhythm start arrow uses the same centered triangle geometry as bass and
  repaints on backend transport changes
- a preset that reuses an already-bound channel/controller for another target
  wins the mapping and its destination-owned numeric values;
  outgoing/incoming handles report red/blue feedback for two seconds and then
  settle free/green
- the red MIDI-learn LED is visible only while blinking to the right of `MIDI`;
  the separate green binding-location LED flashes to the left of `MIDI`/`OMNI`
- the public OMNI/MIDI screenshots are captured from the real production QML;
  the MIDI image contains representative controller knobs in the grey CC bar;
  after a successful `main` release the released commit is captured again, and
  changed PNGs are committed alone before one explicitly queued validation
  release; byte-identical output causes no commit and no further workflow run;
  the branch tip retains exactly the newest three release-tagged pairs
- instrument balance captures cover low/middle/high registers and report RMS,
  peak, crest factor and clipping
- packaged macOS and Windows QML chord input observes pointer-down/up, retains
  the selected chord border after a tap, promotes a hold and releases both
  gestures without leaving synth 3 active
- packaged slider input changes a production parameter through the native Qt
  mouse path and retains aligned value/handle/fill geometry after release;
  component coverage repeats the same accepted-value contract with a Qt test
  touchscreen device
