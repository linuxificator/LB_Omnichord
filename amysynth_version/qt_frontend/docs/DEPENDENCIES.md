# Dependency ownership and build inputs

Status: authoritative dependency-source contract
Owner: frontend runtime and release packaging
Applies to: Python source, tests, tools and all five release targets
Last verified: 2026-09-03

## Python requirement groups

| Group | Source | Current direct intent | Consumers |
| --- | --- | --- | --- |
| Portable pure Python | `requirements-portable.txt` | `pyserial==3.5`, `fastjsonschema==2.22.2`, `python-osc==1.10.2` | every frontend target |
| Desktop runtime intent | `requirements.txt` | portable group plus `PySide6>=6.6,<6.11` | Linux x86_64, Raspberry Pi aarch64, macOS arm64 and Windows x86_64 |
| Desktop build | `requirements-build.txt` | runtime group plus `PyInstaller==6.22.2` | Linux/Raspberry Pi AppImage, macOS DMG and Windows zip jobs |
| Test and quality | `requirements-test.txt` | runtime group, NumPy 2.5.2, Ruff 0.16.5, mypy 2.3.1, coverage.py 7.15.4 and pyserial stubs | local and reusable regression/quality jobs |
| Android host | `requirements-android-host.txt` | runtime group, `PySide6==6.11.2`, `Cython==0.29.36` | the Linux host that runs `pyside6-android-deploy` |

An included `-r requirements.txt` means the runtime file remains the single
authority for shared direct dependencies. A workflow must install a named
requirements group instead of repeating a Python package/version literal.

Release resolution is stricter than runtime intent. Linux x86_64, macOS arm64
and Windows x86_64 use `packaging/constraints/desktop-current.txt` (PySide6
6.10.3); Raspberry Pi uses `raspberrypi-aarch64.txt` (PySide6 6.7.3). Qt moved
its aarch64 wheel baseline to `manylinux_2_39` after that line, which is not
installable on the Ubuntu 22.04/glibc 2.35 Pi builder. Android's deployment
host remains a separate exact PySide6 6.11.2 toolchain and consumes only the
portable pure-Python target group. `packaging/release_inputs.json` hashes the
reviewed requirement/constraint files and records versions, licenses and
sources; publication embeds that evidence in `release-manifest.json`.
The release-level SPDX 2.3 document relates every platform package digest to
its applicable PySide6 line, portable Python runtime dependencies, AMY commit
and desktop build dependency. It is component evidence, not an assertion that
runner images, system packages and every native SDK file are byte-reproducible.

## Direct-import inventory

The machine-readable inventory is
[`python_dependency_groups.json`](../packaging/python_dependency_groups.json).

| Import root | Distribution or exception | Owner | Reason |
| --- | --- | --- | --- |
| `PySide6` | `PySide6` | runtime | Qt Core/GUI/QML/Quick/Test/Network APIs used by the app, tests, diagnostics and screenshot tooling |
| `serial` | `pyserial` | runtime | UART transport is an enabled portable application capability |
| `fastjsonschema` | `fastjsonschema` | runtime | versioned JSON Schema validation before opening runtime resources; pure-Python universal package |
| `pythonosc` | `python-osc` | runtime | OSC 1.0 packet and bundle parsing inside the portable UDP input adapter; pure-Python universal package |
| `numpy` | `numpy` | test and quality | `instrument_balance.py` directly renders and measures native AMY output; declaring it removes reliance on AMY's transitive unpinned requirement |
| `amy`, `c_amy` | pinned LB AMY component exception | AMY release contract | native service and native integration tests require the fork build, not an unqualified PyPI dependency |

Every other direct Python import currently resolves to the standard library or
a repository module. `PyInstaller`, `Cython`, Ruff, mypy and coverage.py are invoked tools
rather than imports in portable application code, but are declared in their
owning groups for the same reproducibility reason. `types-pyserial` supplies
static metadata only.

No application or launcher installs Python packages at runtime.

NumPy is test-only from LB Omnichord's perspective. The pinned AMY source also
declares NumPy (and SoundFile) as its own component dependencies; their resolved
versions in a packaged AMY service remain part of the AMY component's build
provenance, not portable frontend runtime intent.

## LB AMY component exception

All synthesis targets use
`https://github.com/linuxificator/amy.git`, release branch
`releases/amy_omnichord_R20260903T201525`, immutable commit
`3462b266e4990ab6fa617bb8fa5c5ad8b43959d5`. CI proves that the commit belongs
to the declared branch before using it.

This is intentionally not a normal Python requirement. It supplies the C AMY
engine, the Python extension used by native regression tests, the Windows
service, the Android Oboe service AAR and the ESP32-P4 component. It also owns
LB-required sequencer behavior and therefore must advance as one tested release
input across all platforms.

Python/native test and hosted desktop service builds select Gamma9001 with
`AMY_PCM_BANK=gamma9001` where `setup.py` is used. Windows and Android generate,
link and register the same Gamma data through native build definitions. ESP32
uses the same source lineage but remains an explicitly declared Tiny-bank
target until its storage profile changes. Exact options and verification are owned by
[`AMY_RELEASE.md`](../packaging/AMY_RELEASE.md) and the
platform documentation. ESP32-P4 additionally defines `AMY_SHARED_REVERB=1`.
Never update only one consumer.

## Android toolchain sources

Android remains an explicit platform build group rather than portable Python
runtime intent:

- Python 3.11 host, PySide6 6.11.2 and Cython 0.29.36;
- PySide6 and Shiboken Android wheels pinned by filename and SHA-256 for each
  ABI in `desktop-release.yml`;
- the `requirements-android.txt` shipped inside that exact PySide6 host
  distribution, used as Qt's authoritative deployer/buildozer dependency set;
- the portable pure-Python `fastjsonschema==2.22.2` target requirement, copied
  from `requirements.txt` into the generated Buildozer target recipe;
- python-for-Android commit
  `3762c88c56e3443efb8eba2a02a2604b680240fd`;
- Java 17, Gradle 8.13, Android platform 36, build-tools 35.0.0, NDK
  27.2.12479018 (`27c`) and CMake 3.22.1;
- Oboe 1.10.0 as the AMY service's Gradle dependency.

The upstream PySide deployer requirement file is inspectable only after the
pinned PySide6 distribution is installed. Treat changing that distribution as
changing its complete transitive Android host toolchain; the full Android
build and emulator gate are mandatory.

## Other release toolchains

- Python 3.12 is the desktop/test workflow interpreter.
- ESP32-P4 uses ESP-IDF 6.0.2.
- AppImage tool/runtime downloads are architecture-specific and SHA-256
  verified in the release workflow.
- Workflow actions are pinned to reviewed full commit SHAs and Dependabot may
  propose reviewed updates. Runner images and system packages remain named
  platform build inputs; byte-reproducibility is not claimed.

Consumer hash, provenance and SBOM verification commands are maintained in
[`RELEASE_VERIFICATION.md`](../packaging/RELEASE_VERIFICATION.md). Application
publisher signing is deliberately separate; its current deferred decision and
required controls are in [`SIGNING_DECISION.md`](../packaging/SIGNING_DECISION.md).

## Change rule

Before proposing another external package, copy the
[assessment template](../../design/dependency_assessments/README.md), date it,
and reach an explicit
adopt/use-existing/implement-locally/defer outcome. An adoption must declare
the package in the correct group and pass every platform where its importing
code runs. The full selection criteria remain in
[`CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md`](../../design/CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md).
