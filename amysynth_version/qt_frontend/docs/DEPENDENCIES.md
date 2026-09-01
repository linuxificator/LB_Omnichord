# Dependency ownership and build inputs

Status: authoritative dependency-source contract
Owner: frontend runtime and release packaging
Applies to: Python source, tests, tools and all five release targets
Last verified: 2026-09-01

## Python requirement groups

| Group | Source | Current direct intent | Consumers |
| --- | --- | --- | --- |
| Portable runtime | `requirements.txt` | `PySide6>=6.6`, `pyserial>=3.5` | Linux x86_64, Raspberry Pi aarch64, macOS arm64, Windows x86_64 and the staged Android app |
| Desktop build | `requirements-build.txt` | runtime group plus `PyInstaller==6.22.2` | Linux/Raspberry Pi AppImage, macOS DMG and Windows zip jobs |
| Test and quality | `requirements-test.txt` | runtime group, NumPy 2.5.2, Ruff 0.16.5, mypy 2.3.1 and pyserial stubs | local and reusable regression/quality jobs |
| Android host | `requirements-android-host.txt` | runtime group, `PySide6==6.11.2`, `Cython==0.29.36` | the Linux host that runs `pyside6-android-deploy` |

An included `-r requirements.txt` means the runtime file remains the single
authority for shared direct dependencies. A workflow must install a named
requirements group instead of repeating a Python package/version literal.

## Direct-import inventory

The machine-readable inventory is
[`python_dependency_groups.json`](../packaging/python_dependency_groups.json).

| Import root | Distribution or exception | Owner | Reason |
| --- | --- | --- | --- |
| `PySide6` | `PySide6` | runtime | Qt Core/GUI/QML/Quick/Test/Network APIs used by the app, tests, diagnostics and screenshot tooling |
| `serial` | `pyserial` | runtime | UART transport is an enabled portable application capability |
| `numpy` | `numpy` | test and quality | `instrument_balance.py` directly renders and measures native AMY output; declaring it removes reliance on AMY's transitive unpinned requirement |
| `amy`, `c_amy` | pinned LB AMY component exception | AMY release contract | native service and native integration tests require the fork build, not an unqualified PyPI dependency |

Every other direct Python import currently resolves to the standard library or
a repository module. `PyInstaller`, `Cython`, Ruff and mypy are invoked tools
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
`releases/amy_omnichord_R20260831T042456`, immutable commit
`14240031c135fdcd76a7a3a8ec81da8ef405c4b0`. CI proves that the commit belongs
to the declared branch before using it.

This is intentionally not a normal Python requirement. It supplies the C AMY
engine, the Python extension used by native regression tests, the Windows
service, the Android Oboe service AAR and the ESP32-P4 component. It also owns
LB-required sequencer behavior and therefore must advance as one tested release
input across all platforms.

Python/native test and desktop service builds select the tiny PCM bank with
`AMY_PCM_BANK=tiny` where `setup.py` is used. Windows, Android and ESP32 build
the same pinned source through their native build definitions; their exact
options and verification are owned by
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
- Workflow actions, runner images and system packages are platform build
  inputs recorded in the workflow. T24 will add resolved manifests and
  provenance; T04 does not change their versions.

## Change rule

Before proposing another external package, copy the
[assessment template](../../design/dependency_assessments/README.md), date it,
and reach an explicit
adopt/use-existing/implement-locally/defer outcome. An adoption must declare
the package in the correct group and pass every platform where its importing
code runs. The full selection criteria remain in
[`CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md`](../../design/CODEX_HANDOVER_DEPENDENCY_SELECTION_AND_REUSE.md).
