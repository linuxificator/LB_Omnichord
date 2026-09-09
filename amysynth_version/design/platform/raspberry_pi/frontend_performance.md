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
| Final source, six pre-rendered frames | 58.9% | 34.0% | 16.7% | 10.5% |
| GitHub-built aarch64 AppImage | 58.5% | 33.4% | 16.2% | 11.2% |

With no pointer input, the final AppImage frontend used about 2.6% and the
continuously rendering AMY service about 8.0%. The published-versus-source
difference is retained rather than hidden; the exact-source comparison proves
that the dominant improvement comes from the QML change, not from debug-log or
packaging differences.

The packaged measurement used
`LB_Omnichord.R20260908222746.RaspberryPi-aarch64.AppImage`, produced from
commit `e9c9af9` by GitHub Actions run `34285965445`. Its checksum passed both
before and after transfer to the Pi. The same artifact also started through
`--serial --serial-port /dev/serial0 --serial-baud 1000000`, reported the
physical serial backend and created no bundled local-AMY child process.
That workflow subsequently completed successfully across the full Linux,
Raspberry Pi, macOS, Windows, Android/emulator and ESP32-P4 matrix.

The bounded sprite sequence preserves the pointed hollow RGB image, motion and
half-second fade. Pointer input can remain at 120 Hz while the six already
loaded frames advance at no more than 30 Hz. No path is constructed or
tessellated during interaction. The complete mostly-static control surface is
cached independently, so moving the contact visual cannot invalidate it.

## CPU partition experiment

This section records the earlier experiment without boot-time isolation. Its
conclusion about merely pinning to an otherwise busy core remains valid, but it
is superseded for dedicated installations by the properly isolated two-core
experiment in [`realtime_research.md`](realtime_research.md). Isolation and
splitting AMY from PipeWire are both material differences.

Measurements with the fixed frontend compared the default scheduler with one
and two CPUs withheld from Qt. Reserving two CPUs did not improve AMY: the host
backend has one active render thread, and removing a second CPU only reduces
Qt/OS headroom. The one-CPU experiment assigned CPU 3 (the least interrupt-
loaded CPU observed before the run) to AMY and CPUs 0-2 to Qt.

Kernel `sched_wakeup`/`sched_switch` traces then alternated three 120 Hz runs per
policy. All 12,647 observed complete AMY callbacks met the approximately
5.33 ms audio period, but the fixed-core runs had consistently worse p99
wake-to-completion latency (1.30-1.75 ms) than the unrestricted runs
(1.15-1.18 ms). Tail maxima varied in both directions: 2.84-4.61 ms pinned and
2.74-4.93 ms unrestricted. Pinning to a merely quiet core is therefore not the
same as isolating it; kernel and PipeWire work can still contend there while
AMY loses the scheduler's ability to migrate.

At that stage the product therefore retained the operating system's affinity
and normal scheduling policy. The later isolated two-core experiment supplied
the missing physical latency evidence and established the current opt-in host
profile in `realtime_research.md`. It still does not add a platform-specific
affinity watchdog or place scheduler logic in portable application code.

## Regression boundary

Portable CI does not assert a CPU percentage from heterogeneous virtual
runners. It does enforce the causes that can be checked deterministically:

- the static control surface and moving overlay are separate;
- all six sprite assets load and remain a bounded scene-graph subtree;
- 120 synchronous pointer updates cannot produce 120 shape/frame changes;
- no runtime `QtQuick.Shapes` or particle-emitter fan-out is used;
- mouse/touch gestures still traverse the shared production strum path;
- local-service and serial modes retain identical application and wire-command
  behavior; the optional host policy remains in the Pi adapter and existing
  launch wrappers, outside portable application and musical code.

Physical acceptance repeats the external 120 Hz `uinput` sweep while observing
frontend/AMY CPU and listening for dropouts. It is evidence in addition to the
cross-platform behavioral suite, not a platform-specific product fallback.
