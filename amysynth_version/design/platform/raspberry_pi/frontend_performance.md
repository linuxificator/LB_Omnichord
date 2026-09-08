# Raspberry Pi frontend/audio scheduling evidence

Status: physically measured implementation evidence
Owner: Raspberry Pi integration
Last verified: 2026-09-09

## Problem and reproducer

On a 2 GiB Raspberry Pi 4 running the hardware Wayland/V3D path at 1920x1080
and 120 Hz, holding and moving the pointer on the OMNI strum caused audible
dropouts. The frontend exceeded one CPU in `top`; both the static control
surface and the moving contact visual were being submitted through the same
changing scene-graph subtree.

The benchmark uses an external Linux `uinput` process. It emits a real
single-contact multitouch sweep over the production strum at 120 updates per
second. The sender is outside the Omnichord process and the normal QML gesture,
Python semantic action, wire socket and AMY service paths remain intact. CPU
figures are normalized to one CPU and sampled from `/proc`; debug wire logging
is disabled. This is physical Pi evidence, not a portable CI timing threshold.

## Results

| Variant | Qt total | Qt main | QSG render | AMY service |
|---|---:|---:|---:|---:|
| Published AppImage before isolation | 101.3% | 25.7% | 69.3% | 10.0% |
| Same source revision before isolation | 90.1% | 23.4% | 61.2% | 9.5% |
| Static UI cached, moving vector layer separate | 67.3% | 40.0% | 19.1% | 9.9% |
| Six pre-rendered migraine frames | 58.0% | 33.6% | 16.2% | 10.5% |

With no pointer input, the final source frontend used about 2.3% and the
continuously rendering AMY service about 8.4%. The published-versus-source
difference is retained rather than hidden; the exact-source comparison proves
that the dominant improvement comes from the QML change, not from debug-log or
packaging differences.

The bounded sprite sequence preserves the pointed hollow RGB image, motion and
half-second fade. Pointer input can remain at 120 Hz while the six already
loaded frames advance at no more than 30 Hz. No path is constructed or
tessellated during interaction. The complete mostly-static control surface is
cached independently, so moving the contact visual cannot invalidate it.

## CPU partition decision

Measurements with the fixed frontend compared the default scheduler with one
and two CPUs withheld from Qt. Reserving two CPUs did not improve AMY: the host
backend has one active render thread, and removing a second CPU only reduces
Qt/OS headroom. The selected policy therefore gives the highest-numbered CPU
(CPU 3 on the tested Pi) to the local AMY process and CPUs 0-2 to Qt. CPU 3
also had the lowest observed interrupt count on this test system.

This is process affinity, not realtime scheduling and not a boot-time isolated
CPU. It reduces direct Qt/AMY competition without changing global kernel
parameters, priorities, audio formats or application behavior. Failure to
apply the hint is nonfatal and visible. An AppImage using `--serial` retains all
CPUs because its AMY renderer is the ESP32-P4.

## Regression boundary

Portable CI does not assert a CPU percentage from heterogeneous virtual
runners. It does enforce the causes that can be checked deterministically:

- the static control surface and moving overlay are separate;
- all six sprite assets load and remain a bounded scene-graph subtree;
- 120 synchronous pointer updates cannot produce 120 shape/frame changes;
- no runtime `QtQuick.Shapes` or particle-emitter fan-out is used;
- mouse/touch gestures still traverse the shared production strum path;
- the affinity planner is pure, respects enclosing cpusets, is Pi-only and
  fails open with a diagnostic.

Physical acceptance repeats the external 120 Hz `uinput` sweep while observing
frontend/AMY CPU and listening for dropouts. It is evidence in addition to the
cross-platform behavioral suite, not a platform-specific product fallback.
