# Codex handover: Raspberry Pi AppImage graphics and QML backend

Status: fix validated in source mode and as a rebuilt AppImage on the physical
Pi; branch is not merged to `main`
Recorded: 2026-09-06
Affected release: `R20260905T204515`
Hardware/OS: Raspberry Pi 4, 64-bit Debian 13 (Trixie) Raspberry Pi OS,
Broadcom V3D 4.2

## User-visible failure

The released Raspberry Pi AppImage initially started its independent AMY
service and connected the frontend socket, but Qt reported `EGL not available`
and could not create its QRhi OpenGL context. Forcing Qt's software renderer
produced a poor and incomplete rendering and is not an acceptable product
fallback.

Preloading `/usr/lib/aarch64-linux-gnu/libstdc++.so.6` made the real Wayland
OpenGL window appear. That window was still largely unusable: MIDI/OSC-backed
controls were absent and the log contained repeated accesses to an undefined
`backend.midiPlayer` plus a missing `finishMidiPreview()` method.

These were two independent package/runtime defects.

## Failure 1: mismatched C++ and Mesa/V3D runtimes

Host `eglinfo` proved that the Pi's GBM, Wayland, X11 and surfaceless EGL paths
all worked with Mesa 26.2.1 and V3D. The AppImage also contained and loaded
Qt's `libqwayland-egl.so` and Wayland EGL client integration. Context creation
failed only while the AppImage's Ubuntu 22.04 build copy of
`libstdc++.so.6` preceded the current Pi OS runtime used by Mesa. Starting the
same artifact with the Pi system C++ runtime immediately created a Broadcom
OpenGL 3.1 context.

An AppImage can carry application libraries, but cannot replace the running
kernel, compositor or hardware driver. The Raspberry Pi target now removes
PyInstaller's `libstdc++.so.6` from its AppDir. Dynamic linking therefore uses
the system C++ runtime that belongs to the host graphics stack. This is scoped
to `RaspberryPi-aarch64`; the x86 AppImage policy is unchanged without matching
physical evidence.

`qt_runtime_manifest.json` names this forbidden Pi package basename, and the
ordinary final-tree package audit rejects any future Pi artifact that bundles
it. This makes the fix a package-content contract rather than an incidental
shell side effect.

## Failure 2: subclass Qt meta-object members on PySide 6.7

The Raspberry Pi release is constrained to PySide6 6.7.3 because newer aarch64
wheels require a newer glibc than the Ubuntu 22.04 native build runner. The
Omnichord integration backend subclasses the core performance backend. The
source already carried a partial compatibility measure: MIDI integration
signals were declared in the base class because the older aarch64 binding did
not reliably append subclass signals after inherited slots.

The physical log proved that the same compatibility boundary also affected
subclass properties, slots and signals. Base-class properties remained
available, but QML saw parts of the MIDI integration and live-performance
surface as undefined. The missing surface included `midiPlayer`, MIDI preview,
chord gate text/actions, arpeggio direction/actions, bass-riff selection and
tuning coupling. CI accepted partial screenshots because its package capture
checked that non-trivial PNG files existed, not that every expected QObject
member was resolvable.

The application composition root now publishes the already-independent
`MidiPlayerBackend` QObject directly as the `midiBackend` QML context property.
It also publishes a narrow direct-`QObject` `PerformanceQmlAdapter`. That
adapter exposes only existing performance and integration behavior; all calls
delegate to the existing backend and no musical state is duplicated. QML
therefore no longer depends on properties or slots appended by either Python
subclass.

The first rebuilt PySide6 6.7.3 artifact rendered complete screens, but its log
reported a Qt meta-object sort warning when the adapter connected to the three
signals declared by the performance subclass. Moving those signals into the
base and reusing them as subclass property notifiers looked smaller, but the
full process test correctly exposed a silent `SIGSEGV` (`-11`). That rejected
approach is not retained.

The final design adds one generic `performanceChanged` signal to the stable
base meta-object. The performance layer emits it beside its existing specific
signals whenever adapter-visible state changes. The direct adapter listens
only to this safe signal and fans it out to its own property notifiers. The
specific signals, state and behavior remain owned by the performance layer.
The process-separated Linux MIDI regression reproduces the earlier crash and
now passes, protecting this boundary in addition to the adapter meta-object
surface test.

This is smaller and clearer than moving the complete MIDI facade or
performance implementation into the application core merely to work around an
old binding generator. The Python integration facade remains available to
source-level callers, but the QML contract no longer depends on subclass
meta-object extension. No MIDI, OSC, musical or AMY behavior changed, and no
platform branch entered portable UI code.

## Source-mode AMY provisioning

`run_local.sh` intentionally starts a separate Python AMY service, so `c_amy`
is a dependency of that service process rather than of the Qt frontend. A bare
`ModuleNotFoundError` previously obscured this distinction on a fresh Pi
checkout.

The initial repair added `prepare_local_amy.sh --checkout` as an explicit
release-input checkout and install step. Follow-up source-bootstrap work on the
same branch supersedes that launch contract: `run_local.sh` now creates and
validates an ignored clone-root `.venv` and provisions the pinned Gamma9001 AMY
under `.amy/<commit>/` when necessary. Subsequent starts are offline when the
declared requirements and stamped AMY extension digest still match. Explicit
`OMNICHORD_VENV` and `OMNICHORD_AMY_ROOT` overrides remain supported. Released
packages do not execute this source-only bootstrap.

## Validation completed

- The original AppImage with only the system C++ runtime preloaded created a
  Broadcom V3D/OpenGL context, isolating the first failure.
- The exact pinned AMY commit was compiled on the physical Pi with Gamma9001
  and installed through the documented `prepare_local_amy.sh --checkout`
  route.
- `run_local.sh` then started that AMY service and the corrected frontend as
  separate processes connected only through the Unix socket/wire protocol.
- The corrected frontend created a Broadcom V3D OpenGL 3.1 context through the
  real Wayland display.
- It captured complete OMNI and MIDI screens without `TypeError`,
  `ReferenceError`, undefined QML backend access, missing method, EGL failure
  or context-creation failure.
- The complete local suite passed outside the socket-restricted sandbox,
  including quality, QML gestures, process-separated MIDI, frontend, serial,
  native-control and native-rhythm tests.

The source validation used the Pi's existing PySide6 6.10.3 environment and
its newly compiled pinned Gamma9001 AMY service. It proves source-mode setup,
the process boundary and the physical graphics path, but it is not a substitute
for rebuilding the final PySide6 6.7.3 AppImage.

## Rebuilt package evidence

- GitHub Actions run: `34052065218`
- Built source commit: `f49f66aea5f6c7cc08a37559efc61075ef897fef`
- Package artifact: `9994908939` (`package-RaspberryPi-aarch64`)
- Evidence artifact: `9994909123` (`evidence-RaspberryPi-aarch64`)
- File: `LB_Omnichord.R20260906183334.RaspberryPi-aarch64.AppImage`
- Size: 88,799,752 bytes
- SHA-256: `5711725c128f48777c887a310e7784d78d6d58cd8aa5900a61f543708005e9aa`

The CI package audit reported no forbidden runtime matches. Its acceptance log
passed the strengthened runtime-failure policy and contained no Qt sort
warning, QML property/method failure, traceback or EGL/context failure.

That exact checksum was verified again after transfer to the physical Pi. It
was started normally from `/tmp`, without `LD_PRELOAD`, software rendering,
an OpenGL override or assistance from the source checkout. The package started
its own AMY service, connected over its private Unix socket and created a
Broadcom V3D OpenGL 3.1 context through Wayland. It captured complete OMNI and
MIDI screens of 404,869 and 364,368 bytes. The physical runtime log contained
no meta-object warning or QML/EGL error.

## Validation boundary

The observed tests prove source provisioning, package startup, process/socket
separation, Gamma9001 service initialization and complete hardware-accelerated
rendering on the target Pi. Automated capture does not prove prolonged audible
playback, physical mouse/touch behavior, MIDI hardware, latency or absence of
audio drop-outs; those remain physical interaction checks rather than claims
made by this repair.
