# Codex handover: Raspberry Pi AppImage graphics and QML backend

Status: fix implemented on `fix/raspberrypi-appimage-runtime`; rebuilt-package
and final physical AppImage validation pending
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

The physical log proved that the same compatibility boundary also affected the
subclass `midiPlayer` property and `finishMidiPreview` slot. Base-class
properties remained available, but QML saw the added subclass surface as
undefined. CI accepted partial screenshots because its package capture checked
that non-trivial PNG files existed, not that every expected QObject member was
resolvable.

The application composition root now publishes the already-independent
`MidiPlayerBackend` QObject directly as the `midiBackend` QML context property.
`Main.qml` and `MidiScreen.qml` use that direct object. Switching from the MIDI
screen ends its preview through `midiBackend.previewEnd()`, the owning object's
existing slot. No MIDI, OSC, musical or AMY behavior changed, and no platform
branch entered portable UI code.

This is smaller and clearer than moving the complete MIDI facade into the core
performance class merely to work around an old binding generator. The Python
integration facade remains available to source-level callers, but the QML
contract no longer depends on subclass meta-object extension.

## Validation completed

- The original AppImage with only the system C++ runtime preloaded created a
  Broadcom V3D/OpenGL context, isolating the first failure.
- The corrected frontend was then run on the same physical Pi against the AMY
  service from the released AppImage. AMY and Qt remained separate processes
  connected only through the Unix socket/wire protocol.
- The corrected frontend created a Broadcom V3D OpenGL 3.1 context through the
  real Wayland display.
- It captured complete OMNI and MIDI screens of 406,159 and 366,465 bytes.
- Its filtered log contained no `TypeError`, `ReferenceError`, undefined QML
  backend access, missing method, EGL failure or context-creation failure.
- Targeted static-contract, application-composition and package-audit unit
  tests passed locally. The frontend integration test could not bind its test
  TCP control port inside the local filesystem/network sandbox; this is an
  environment restriction rather than a product result.

The source validation used the Pi's existing PySide6 6.10.3 environment for
the corrected frontend and the packaged Gamma9001 AMY service for synthesis.
It therefore proves the architecture and physical graphics path, but it is not
a substitute for rebuilding the final PySide6 6.7.3 AppImage.

## Remaining release proof

Before merging this fix to `main`:

1. Run the feature branch's complete GitHub package workflow, including the
   native aarch64 builder constrained to PySide6 6.7.3.
2. Confirm the Pi package audit contains no `libstdc++.so.6`.
3. Download that exact AppImage to the physical Pi and start it normally,
   without `LD_PRELOAD`, software rendering or a repository checkout.
4. Verify both OMNI and MIDI screens, mouse/touch interaction and audio.
5. Preserve the physical log and exact artifact SHA as release evidence.

Do not declare the rebuilt AppImage physically validated until those steps are
observed. A CI offscreen/software screenshot does not prove Wayland, EGL, V3D,
input devices, physical audio or absence of drop-outs.
