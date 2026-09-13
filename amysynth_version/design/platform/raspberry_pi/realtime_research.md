# Raspberry Pi realtime audio research

Status: Pi 4 measurement complete; Pi 5 default-governor/core policy validated
Branch: `research/rt_pi`
Measurement baseline: `R20260909T010905`
Current packaged acceptance: `R20260909161844` (GitHub run `34375905899`)

## Scope and invariants

This research changes only Raspberry Pi host configuration and external test
tooling. It does not change AMY, LB Omnichord's musical behavior, the frontend,
or the wire/socket process boundary. Every benchmark uses the checksum-verified
published aarch64 AppImage.

The stock scheduler is a required control. CPU isolation, the performance
governor, IRQ placement and targeted `SCHED_FIFO` are independent variables;
results must not attribute the combined effect to just one of them.

## Initial Pi 4 inventory

- Hardware: Raspberry Pi 4 Model B Rev 1.1, four Cortex-A72 cores, 2 GiB RAM.
- OS: 64-bit Raspberry Pi OS / Debian 13.
- Kernel: `6.18.34+rpt-rpi-v8`, `CONFIG_PREEMPT=y`.
- `CONFIG_CPU_ISOLATION=y` and `CONFIG_IRQ_FORCED_THREADING=y` are available.
- `CONFIG_PREEMPT_RT`, `CONFIG_NO_HZ_FULL` and `CONFIG_RCU_NOCB_CPU` are not
  enabled. Unsupported `nohz_full`/`rcu_nocbs` arguments must therefore not be
  presented as effective tuning.
- The four CPUs share one cpufreq policy and initially use `ondemand`.
- No boot CPU isolation was active and no thermal/undervoltage flags were set.
- AMY reaches the HDMI sink through miniaudio, PulseAudio compatibility and
  PipeWire. The service has one active callback thread; PipeWire and
  pipewire-pulse each have a separate `data-loop.0` support thread.
- None of those threads initially has realtime scheduling; their process
  `RLIMIT_RTPRIO` is zero.

## Unmodified capacity control

The published service was started without the frontend and driven through its
normal Unix wire socket. Both shared reverb processors were active and the
load was split between Omnichord bus 0 and MIDI bus 4. Levels were deliberately
very low to keep the test acoustically safe; this does not skip rendering.

| Workload | Configured/active limit | Callback CPU at limit | Overload |
|---|---:|---:|---:|
| Sine oscillators + two reverbs | 336 oscillators | 26.1% | none |
| 24 dB filtered saws + two reverbs | 336 oscillators | 27.0% | none |
| DX7 patch 129 + two reverbs | 42 voices / 336 oscillators | about 28% | none |

Patch 129 consumes eight oscillators per voice; asking for a 43rd voice reaches
the configured oscillator pool before it reaches the Pi 4 CPU limit. Thus the
release's sustained synthesis ceiling is its configured 336-oscillator limit,
not continuous Pi 4 compute. The physical dropout problem is instead a tail
latency/scheduling problem under concurrent GUI activity and event bursts.

An early exploratory loop reset and reallocated synths without waiting for the
render thread and caused a service segmentation fault. That is not a valid
capacity result. Subsequent capacity points each used a fresh service process,
which both removes the race and matches a cold application start.

## Reproducibility tools

- `tools/raspberry_pi/rt_pi_config.py` prepares reversible `stock`,
  `audio-one`, and `audio-split` boot cmdlines, captures checksummed originals,
  verifies the active boot and changes the runtime governor explicitly.
- `tools/raspberry_pi/rt_pi_benchmark.py` replays timestamped production wire
  logs from a separate process, generates bounded synthetic loads and samples
  per-thread CPU/run-queue delay through `/proc`.

All measurement helpers remain external to both application processes. The
production integration grants the desktop user a standard PAM
`RLIMIT_RTPRIO=80` allowance. Systemd user-unit drop-ins grant that limit to
PipeWire; PipeWire's own `module-rt` and `thread.affinity` settings create its
two data loops with the measured policies. The already existing
source/AppImage wrapper knows the immutable PID returned when it starts AMY,
measures that exact child's active non-main worker, and applies realtime
policy only to that callback. The frontend receives the exact child PID and
independently reads back AMY, frontend and PipeWire state. No registration
protocol, privileged watcher or repeated AMY process scan is involved.

Two watcher prototypes were rejected. A 0.5-second process-table poll consumed
about 6.6% of one core. A later credential-bound Unix-socket design avoided
name matching, but introduced a daemon, registration protocol, lifecycle
tokens and drift state for a policy needed only once after a wrapper-created
child starts. Continuing to repair that design would have been "headbanging":
complexity caused by the chosen mechanism rather than by the requirement. PAM
realtime permission plus one-shot wrapper application uses the Linux mechanism
intended for this case and has materially less state and failure surface.

## Production-log replay: first comparisons

The last physical Pi session contains 12,949 wire commands over 148.488
seconds, including 1,470 strum events plus rhythm, fill, bass and chord
changes. Replaying it at original timestamps from a separate process provides
the first repeatable scheduling comparison. `run_delay` is the Linux
`schedstat` aggregate for the callback thread, not an individual worst-case
latency; PipeWire's error-counter delta and AMY's overload log remain the
deadline checks.

| Boot/runtime policy | Callback CPU | Callback run delay | PipeWire client errors | AMY overload |
|---|---:|---:|---:|---:|
| Stock boot, `ondemand`, unrestricted | 12.384% | 12.059 ms | +2 | none |
| Stock boot, `performance`, unrestricted | 6.154% | 5.161 ms | +0 | none |
| CPU3 isolated, complete audio chain pinned, normal policy | 6.725% | 274.138 ms | +0 | none |
| CPU3 isolated, PipeWire FIFO 80/75 and AMY FIFO 70 | 6.603% | 1,931.416 ms | +0 | none |
| CPUs 2-3 isolated, AMY CPU3 / PipeWire CPU2, normal | 6.224% | 1.181 ms | +0 | none |
| CPUs 2-3 isolated, AMY CPU3 / PipeWire CPU2, FIFO | 6.117% | 0.215 ms | +0 | none |

The performance governor is already a clear improvement. One-core isolation
eliminates observed PipeWire errors but substantially increases aggregate
callback wait because AMY and the two PipeWire stages serialize on the same
core. FIFO protects deadlines but does not manufacture CPU time; its aggregate
wait is worse still behind the deliberately higher-priority audio-server
stages. This one-core profile is therefore not a candidate. Splitting the
stages between two isolated cores removes
that artificial queue. The targeted FIFO split is the accepted Pi 4 profile.

## Tail latency with the complete application

The final test ran the published AppImage on hardware Wayland/V3D at 120 Hz.
An independent Linux `uinput` process delivered 7,200 real touch updates over
the production strum in 60 seconds. The frontend and AMY stayed separate
processes and communicated only over the packaged Unix wire socket.

- AMY callback CPU was 6.982% of one core; aggregate run delay was 0.069 ms.
- The frontend used about 27-36% of one core-equivalent across repeated runs;
  its largest contributors were the main and QSG render threads.
- PipeWire client and sink error counters did not increase.
- AMY reported neither overload nor slot exhaustion, and firmware reported
  `throttled=0x0`.

A 30-second scheduler trace captured 6,761 complete callbacks:

| Callback metric | Median | p99 | Maximum |
|---|---:|---:|---:|
| Wake to scheduled | 0.006 ms | 0.011 ms | 0.026 ms |
| Scheduled to switch-out | 0.372 ms | 0.511 ms | 1.024 ms |

The trace is observational and was collected after the policy was applied; its
output is not emitted from the realtime thread. IRQ deltas during active audio
showed both relevant DMA IRQs on housekeeping CPU 0. CPU 2/3 saw timer and
inter-processor activity but no device IRQ leakage.

## Capacity under isolation and targeted realtime policy

Each capacity point used a fresh packaged AMY service, its normal wire socket,
both shared reverb processors, and a deliberately quiet level. Quiet is only
for hearing safety; these oscillators are active and rendered.

| Workload | Active AMY capacity | Callback CPU | p99 callback runtime | Result |
|---|---:|---:|---:|---|
| Sine | 336 oscillators | 14.569% | not traced | configured limit reached |
| 24 dB filtered saw | 336 oscillators | 15.285% | not traced | configured limit reached |
| DX7 patch 129 | 42 voices / 336 oscillators | 28.483% | 1.778 ms | configured limit reached |

The DX7 maximum callback runtime was 2.226 ms. Even this worst tested sustained
load remains below the callback period, so the 336-oscillator build limit is
reached before the Pi 4 compute limit. This is not permission to increase the
product limit without a separate transient/event-burst study.

## Kernel decision

The installed Raspberry Pi kernel provides kernel preemption, threaded IRQ
support and CPU isolation, but not `PREEMPT_RT`, `NO_HZ_FULL` or
RCU callback offload. Debian offers a generic `linux-image-rt-arm64` 6.12
package while this board runs Raspberry Pi's 6.18 kernel and firmware/driver
integration. Installing that generic kernel remotely would create a boot and
hardware-support experiment, not a controlled scheduler comparison. It was
therefore deliberately not installed. The measured stock Pi kernel plus
`threadirqs`, isolation and targeted FIFO already meets the observed deadline.

## Conclusion

The measured Pi 4 latency layout is `audio-split`: CPUs 2-3 isolated from
normal scheduling, IRQ default affinity on CPUs 0-1, PipeWire data loops on
CPU 2 at FIFO 80/75, and only the detected AMY callback on CPU 3 at FIFO 70.
The original experiment held the shared clock at maximum, but the delivered
profile now leaves frequency scaling at Raspberry Pi OS's normal `ondemand`
default to avoid unnecessary idle power and heat. The application and all its
logic remain portable. The profile is a reversible host-integration choice documented in
[`realtime_howto.md`](realtime_howto.md), not an application default.

On 2026-09-09 a clean reboot physically verified the simplified production
route. The `lawaai` login and both PipeWire services inherited
`RLIMIT_RTPRIO=80`; PipeWire created its own loops at CPU2/FIFO80 and
CPU2/FIFO75. `run_local.sh` then assigned its exact AMY child callback to
CPU3/FIFO70 and confined frontend and non-audio service work to CPUs 0-1. The
frontend produced no realtime warning or QML binding-loop diagnostic. An
external 120 Hz kernel-uinput sweep ran for 20 seconds without policy drift,
AMY overload/dropout output or throttling (`throttled=0x0`). This validates the
native PAM/systemd/PipeWire plus one-shot wrapper design; the measured audio
layout itself is unchanged.

The same source checkout was then started with `--serial`. It opened
`/dev/serial0` at 1,000,000 baud, created no local AMY service and emitted no
host-realtime warning. This proves the platform check does not confuse the
external ESP32-P4 transport with a missing host-AMY policy.

A separate post-boot control also drove a clean packaged AMY service over its
Unix wire socket and its bounded 440 Hz oscillator was physically heard
through the HDMI sink. This distinguishes the intentionally near-silent
capacity workloads from an audio-routing failure.

The final packaged acceptance exposed one boundary defect that the source
launcher could not reproduce: AppImage/PyInstaller sets `LD_LIBRARY_PATH` to
its private libraries, and host `systemctl` inherited that loader path. The
host binary consequently exited before querying the user manager. The Linux
adapter now invokes canonical `/usr/bin/systemctl` with AppImage loader
injections removed while retaining user-session variables. A regression test
covers that environment boundary. AppImage `R20260909161844` then found both
systemd-owned PipeWire loops, applied the exact AMY policy and completed an
external 20-second 120 Hz sweep with no warning, overload, dropout, binding
loop or throttling.

On 2026-09-13 the revised runtime contract was checked on a Pi 5 Model B Rev
1.1 with its shared frequency policy at the Raspberry Pi OS `ondemand`
default. CPUs 2-3 and IRQ placement remained isolated as designed. The exact
packaged AMY child had one callback on CPU 3/FIFO70 and its remaining threads
on CPUs 0-1/SCHED_OTHER; PipeWire retained CPU 2/FIFO80 and
PipeWire-Pulse CPU 2/FIFO75. The revised aggregate startup check was silent.
This is evidence for correct policy placement under dynamic scaling, not a new
Pi 5 maximum-capacity measurement.
