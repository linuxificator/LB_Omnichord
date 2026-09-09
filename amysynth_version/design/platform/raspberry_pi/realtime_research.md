# Raspberry Pi realtime audio research

Status: in progress on Pi 4; Pi 5 pending physical availability  
Branch: `research/rt_pi`  
Release under test: `R20260909T010905`

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

The final profile choice and measured latency/dropout comparison will be added
after the isolated boots and targeted FIFO experiments.
