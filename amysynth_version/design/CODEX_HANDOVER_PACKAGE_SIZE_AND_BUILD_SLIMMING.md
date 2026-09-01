# Codex handover: package size and build slimming

Status: implemented; final hosted all-platform validation in progress
Owner: frontend release packaging
Recorded: 2026-09-01
Branch: `rework/code_quality`
Applies to: Linux x86_64, Raspberry Pi aarch64, macOS arm64, Windows x86_64
and Android arm64 packages

## Outcome

PySide6/Qt is intrinsically a substantial runtime, but the current packages
contain much more Qt than LB Omnichord uses. The published sizes are not a
reasonable lower bound for this application. The dominant cause is broad
collection of the complete Qt QML/plugin distribution on desktop and the
complete target PySide6 wheel on Android.

This work must preserve the existing architecture: the portable Qt frontend
remains a wire-only process, and AMY remains a separate service/target. Package
slimming must not link or import AMY into the frontend and must not weaken the
five-platform package/runtime tests.

## Implemented state

The machine-readable policy is `packaging/qt_runtime_manifest.json`. Source QML
imports are scanned and compared with its reviewed allowlist. Every package is
then audited by `packaging/package_audit.py`; the JSON evidence records package
size, the largest members, Qt inventory and forbidden-family matches. The
budgets are deliberately above the first observed reduced outputs but below
the former complete-SDK packages, so restoring the old collection behavior
fails the build.

Desktop PyInstaller builds use local `QtQml` and `QtGui` collection hooks. The
first reduced Linux x86_64 AppImage is 89,643,512 bytes, down from 205,273,592
bytes in the measured release (56.3% smaller). Its package self-test passes and
an offscreen final-bundle launch reaches the packaged QML application over the
separate AMY Unix-socket service. During that final-image test a pre-existing
hidden schema-path dependency was exposed: catalog validation computed an
asset path from `__file__`. Schema ownership is now explicit, and the frozen
entrypoint forwards both the generated AMY socket argument and its resolved
asset root through the normal application composition boundary.

Android first verifies the unchanged official target-wheel SHA-256, then
`packaging/android/prune_pyside_wheel.py` creates a separate valid wheel. It
uses the reviewed bindings/QML/platform roots and recursively follows actual
ELF `DT_NEEDED` entries. For the official arm64 6.11.2 input this reduced the
wheel from 83,924,266 to 22,860,307 bytes (72.8%) while retaining 41 native
libraries and all 11 reviewed QML modules. The extra retained binding is
`QtWidgets`, imported transitively by the packaged `QtTest` acceptance path.
It rewrites wheel `RECORD`; the
source/output hashes and retained native inventory are package evidence. The
APK receives a second nested-bundle content audit.

The release workflow now supports a non-publishing manual all-platform run on
the selected branch. Normal push and publication rules are unchanged. Android
also has pip caching and an ABI-specific immutable python-for-Android cache,
pinned to `actions/cache` commit
`0400d5f644dc74513175e3cd8d07132dd4860809`. Staging preserves only its
`.buildozer` cache and recreates all application/deployment inputs.

`tools/clean_package_outputs.py` is dry-run by default and can delete only the
exact ignored `qt_frontend/build` and `qt_frontend/dist` roots. It refuses a
symlink or non-directory at either location. No file below those roots is
tracked; release retention remains GitHub's responsibility rather than Git's.

## Validation ledger

- the complete local frontend test runner passes;
- all local quality guardrails pass, including the mypy ratchet;
- the final reduced Linux PyInstaller tree passes package self-test and starts
  the actual QML application against the separate AMY socket service;
- the official arm64 wheel was pruned, `RECORD`-checked and ZIP-verified;
- hosted unit run `33552227475` passes at commit `3282569`;
- the MIDI raw-input/QML integration test now waits for real QML readiness and
  uses the ordinary AMY socket transport instead of an unrelated unused AMY
  pseudo-terminal; it passed ten consecutive local runs before the hosted run;
- the ignored local output cleanup removed 2,075,167,508 bytes in total;
- the final non-publishing all-platform workflow is the remaining acceptance
  gate; add its package sizes and run identity here when it completes.

## Measured release baseline

Release `R20260831T210652` published these compressed packages:

| Platform | Bytes | Approximate MiB |
| --- | ---: | ---: |
| Android arm64 APK | 158,133,682 | 150.8 |
| Linux x86_64 AppImage | 205,273,592 | 195.8 |
| Raspberry Pi aarch64 AppImage | 195,176,968 | 186.1 |
| macOS arm64 DMG | 178,225,454 | 170.0 |
| Windows x86_64 zip | 176,145,364 | 168.0 |

The locally retained Linux AppImage with the same package shape is 196 MiB
compressed and 573 MiB extracted. Its extracted PySide6 tree is 429 MiB. The
single unused `libQt6WebEngineCore.so.6` is 195 MiB extracted and about 62 MiB
when independently compressed with zstd level 19. The package also contains
unused Qt3D, Quick3D, Charts, Graphs, PDF, Multimedia, Location, WebView,
VirtualKeyboard and multiple unused Quick Controls styles.

The application-owned GUI, instrument and music assets are only several MiB.
The Python interpreter, standard library, required Qt Quick runtime and AMY
service still make a genuinely small single-digit package unrealistic, but
they do not justify the current complete Qt distribution.

## Android package evidence

The arm64 APK contains 266,377,439 uncompressed bytes. Its largest member is
`lib/arm64-v8a/libpybundle.so`, an 88,354,397-byte gzip stream which expands to
a 245,657,600-byte tar archive. The extracted Python bundle is approximately
242 MiB; approximately 231 MiB is `site-packages/PySide6`.

The complete PySide6 tree inside the Python bundle contains:

- approximately 136 MiB of `PySide6/Qt/lib`;
- approximately 27 MiB of QML modules;
- approximately 14 MiB of Qt plugins;
- approximately 16 MiB of translations;
- Python bindings for many unused Qt modules.

Native Qt libraries are then copied again to the APK's `lib/arm64-v8a`
directory. That directory includes 3D, Bluetooth, Charts, DataVisualization,
Designer, Graphs, Location, Multimedia, PDF, Quick3D, Sensors, SerialBus,
SpatialAudio, TextToSpeech, VirtualKeyboard, WebView and many other unrelated
modules. The explicit `QT_MODULE_LOAD_ORDER` currently controls and verifies
JNI load order; it does not prune the wheel or native library directory.

The official PySide6 6.11.2 Android arm64 wheel is 83,924,266 bytes. Downloading
that complete verified upstream build input is acceptable; copying all of it
into the shipped application is not required.

The AMY AAR contains both supported ABIs as required by its reusable service
contract. Consequently, the arm64 APK also contains the x86_64 AMY, Oboe and
C++ runtime libraries. Their combined compressed overhead is only about one
MiB and is not the principal size problem. ABI filtering can still remove
that product-package duplication after the AAR itself has passed its two-ABI
input check.

## Actual Qt/QML surface

Portable Python directly needs these PySide modules:

- `QtCore`;
- `QtGui`;
- `QtNetwork`;
- `QtQml`;
- `QtQuick`;
- `QtQuickControls2`;
- `QtTest` only for the packaged acceptance path.
- `QtWidgets` only as the binding imported transitively by that `QtTest`
  acceptance path.

Android additionally loads `OpenGL` explicitly. The product QML imports only
QtQuick, QtQuick.Controls, QtQuick.Window and QtQuick.Shapes. Application
startup selects `QQuickStyle.setStyle("Basic")`, so Fusion, Material, Imagine,
Universal, Fluent and native control-style payloads are not product inputs.

The transitive QML runtime allowlist is therefore:

- `QtQml`;
- `QtQml/Models`;
- `QtQml/WorkerScript`;
- `QtQuick`;
- `QtQuick/Window`;
- `QtQuick/Shapes`;
- `QtQuick/Controls`;
- `QtQuick/Controls/Basic`;
- `QtQuick/Controls/Basic/impl`;
- `QtQuick/Controls/impl`;
- `QtQuick/Templates`.

This allowlist must be machine readable, checked against the source QML
imports and shared by desktop and Android packaging. Native library dependency
closure must still be derived from the selected bindings/plugins rather than
guessed from filenames.

## Build-time cost

The latest complete release workflow took approximately 13 minutes 46
seconds. The arm64 Android job took approximately 8 minutes 39 seconds; its
main Buildozer/python-for-Android step took 6 minutes 11 seconds. SDK/NDK setup
took 47 seconds, target-wheel download four seconds and AMY AAR construction
25 seconds in that run. The recurring cost is therefore mainly the uncached
python-for-Android distribution/build, not only network transfer.

Two Android variants are intentionally built: x86_64 is installed in the
emulator and arm64 is published. Do not remove the emulator build merely to
make CI faster. Cache immutable host requirements, verified target wheels and
ABI-specific Buildozer/python-for-Android state with keys derived from every
relevant pinned input instead.

## Local build and dist directories

At initial audit time `qt_frontend/build` occupied approximately 1.1 GiB and
`qt_frontend/dist` approximately 965 MiB. `dist` held five development
AppImages of about 193 MiB each. Further package trials changed the local
figures to 791,604,052 bytes in `build` (1,546 files) and 1,283,563,456
bytes in `dist` (eight AppImages) immediately before cleanup. Both directories
are ignored by
`qt_frontend/.gitignore`; `git ls-files` reports no tracked files below them.
They consume local disk but do not enlarge Git history or the GitHub checkout.

Build scripts should continue to recreate their own platform build roots.
Provide an explicit safe cleanup command for all ignored package outputs and
document that `dist` is output/retention space, not a package archive. Never
make publication depend on stale local contents.

## Signing boundary

The current published Android artifact is built through Buildozer's `debug`
path and is debug-signed. That is an explicit experimental-distribution
decision in `packaging/SIGNING_DECISION.md`, not a size optimization.

Android application signing does not normally use a public CA. A directly
distributed APK is signed with a stable private application keystore; Android
uses the same certificate/key identity to authorize future updates. Play
distribution may delegate storage and operational signing to Play App Signing,
but still requires an owned upload/app-signing identity.

Do not generate a disposable release key, commit a keystore, expose one to pull
requests or silently switch the published package to an unsigned `release`
artifact. Production signing remains blocked on the existing D04 decision:
distribution channel, human key owner, protected secrets, backup/recovery,
rotation/revocation and physical acceptance must be approved first. Package
slimming proceeds independently and retains the accurately labelled debug
artifact.

## Implementation order

1. Add a deterministic content/size audit which emits JSON, rejects forbidden
   Qt families and enforces per-platform compressed-size budgets.
2. Run Qt's QML import scanner as evidence, then apply the reviewed Basic-style
   transitive allowlist rather than copying every installed QML module.
3. Replace desktop PyInstaller's unrestricted QtQml hook with a pinned local
   hook that collects only the allowlisted QML modules and their actual native
   dependencies. Run package self-test and startup smoke on the final image.
4. Produce a pruned copy of the verified Android target wheel. Retain selected
   bindings/QML/plugins and recursively derive the ELF dependency closure;
   keep the original wheel hash verification before pruning. Verify that the
   final APK contains every required module and no forbidden family.
5. Keep `QtTest` and package-smoke code only where package acceptance uses it.
   The x86 emulator artifact may retain test-only support; removing it from an
   arm64 product requires a separately tested staged-source split.
6. Do not implement production signing until D04 is approved. Keep the
   experimental debug-signing statement accurate.
7. Cache Android host requirements, target wheels and ABI-specific p4a state
   using complete immutable keys. Preserve two-ABI emulator/release coverage.
8. Add a safe local output-cleanup tool and keep ignored build/dist output out
   of source/release manifests.

Items 1 through 8 are implemented. Item 6 deliberately means preserving the
existing signing boundary, not adding signing credentials.

## Acceptance criteria

- final package reports name compressed/uncompressed totals, largest members,
  Qt module inventory and policy violations;
- WebEngine, 3D/Quick3D, Charts/Graphs, PDF, Multimedia, Location, Designer,
  VirtualKeyboard and unrelated Qt bindings are absent unless a future source
  import and reviewed manifest change requires one;
- Qt Quick Basic controls, Window and Shapes render in packaged QML;
- package self-test and existing pointer/tap/hold smoke remain green;
- Android still proves app-private socket delivery and exact AMY/Oboe sample
  equality in the emulator;
- frontend/AMY process separation and ordinary wire commands are unchanged;
- all five packages remain described by the exact release manifest and SBOM;
- size budgets fail on regression and are tightened only from observed green
  packages, not speculative targets;
- no production-signing claim or secret is introduced.

## Initial stop conditions

Stop and report rather than weaken tests if pruning removes a transitive QML
plugin, Android JNI dependency or platform plugin required by a final-package
smoke. Stop before signing changes or protected-secret creation. Do not delete
unrecognized user files outside the ignored `qt_frontend/build` and `dist`
output roots.
