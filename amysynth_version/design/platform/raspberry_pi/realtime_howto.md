# Dedicated Raspberry Pi realtime audio setup

Status: physically validated on Raspberry Pi 4; Raspberry Pi 5 measurements pending
Validated release: `R20260909T010905`
Validated kernel: Raspberry Pi `6.18.34+rpt-rpi-v8`, `PREEMPT`

This procedure reserves CPU 3 for AMY's audio callback and CPU 2 for
PipeWire's audio data loops. The UI, operating system and device IRQs use CPUs
0-1. It is intended for a dedicated LB Omnichord appliance, not a general-use
desktop. It changes only Raspberry Pi host configuration; it does not patch
AMY or LB Omnichord and does not weaken the wire/socket process boundary.

## Why this layout

The governor made the largest single improvement. Putting AMY and both
PipeWire stages together on one isolated core was worse because every audio
period forced them to queue serially. With the split profile, a physical 120 Hz
strum test produced 0.011 ms p99 AMY wake latency and no audio error-counter
increments. See [`realtime_research.md`](realtime_research.md) for the complete
controls, rejected layout and capacity table.

Do not apply FIFO to the full frontend or AMY process. Only the callback and
two PipeWire data loops are bounded audio threads; making arbitrary workers
realtime can starve the system.

## 1. Prepare and inspect

Run from a checkout of this branch on the Pi:

```sh
cd amysynth_version/qt_frontend
python3 tools/raspberry_pi/rt_pi_config.py inspect --json
sudo python3 tools/raspberry_pi/rt_pi_config.py plan --profile audio-split
```

Confirm that the model has four CPUs and that the kernel reports
`CONFIG_CPU_ISOLATION=y` and `CONFIG_IRQ_FORCED_THREADING=y`. Keep SSH or local
console access available for the first reboot.

## 2. Apply the reversible boot profile

```sh
sudo python3 tools/raspberry_pi/rt_pi_config.py apply --profile audio-split
sudo reboot
```

Before editing the one-line boot cmdline, the helper saves a checksummed exact
copy under `/var/lib/lb-omnichord-rt/snapshots/<UTC timestamp>/`. It removes or
replaces only arguments it owns:

```text
isolcpus=domain,managed_irq,2-3 irqaffinity=0-1 threadirqs
```

After reconnecting:

```sh
python3 tools/raspberry_pi/rt_pi_config.py verify --profile audio-split
```

Expected: isolated CPUs `2-3` and active boot arguments. Verification reports
the governor separately because it is a runtime setting.

## 3. Install the runtime policy

The two small services make the performance governor persistent and apply the
measured policy whenever a packaged or local AMY service appears:

```sh
sudo install -d -m 755 /usr/local/lib/lb-omnichord-rt
sudo install -m 755 \
  tools/raspberry_pi/rt_pi_config.py \
  tools/raspberry_pi/rt_pi_runtime.py \
  /usr/local/lib/lb-omnichord-rt/
sudo install -m 644 \
  tools/raspberry_pi/lb-omnichord-performance.service \
  tools/raspberry_pi/lb-omnichord-rt-policy@.service \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now \
  lb-omnichord-performance.service \
  lb-omnichord-rt-policy@"$USER".service
```

The watcher initially places all discovered frontend and AMY threads on CPUs
0-1. Newly created frontend threads inherit that affinity. It measures the
active AMY worker before assigning only that TID to CPU 3/FIFO 70. PipeWire and
pipewire-pulse `data-loop.0` are discovered by process/thread identity and
assigned CPU 2/FIFO 80 and 75. No PID or IRQ number is hardcoded.
After applying a policy, the watcher sleeps on Linux process descriptors; it
does not continuously poll the process table. It wakes on an AMY/PipeWire
restart or for a low-frequency health check.

A parent is treated as a frontend only when it is an actual packaged
`LB_Omnichord` process. A standalone `--amy-service` commonly has systemd as
PID 1 for its parent; PID 1 and other launch supervisors are never retuned.

Check the result after starting LB Omnichord:

```sh
sudo journalctl -u lb-omnichord-rt-policy@"$USER".service -n 5 --no-pager
sudo python3 tools/raspberry_pi/rt_pi_runtime.py apply --user "$USER"
```

The second command is an explicit verification/reapply operation. It must show
one AMY candidate on CPU 3/FIFO 70 and both PipeWire data loops on CPU 2.

## 4. Repeat the physical acceptance test

Start the AppImage normally on hardware Wayland/OpenGL. In a second terminal:

```sh
sudo python3 tools/raspberry_pi/strum_uinput.py \
  --rate 120 --duration 60 --width 1920 --height 1080
```

This creates a separate kernel input device and traverses the real QML touch,
Python action, socket and AMY paths. It does not call test hooks inside the
application. Listen for dropouts and inspect:

```sh
vcgencmd get_throttled
pw-top -b -n 1
```

For diagnostic scheduler evidence, first find the AMY service and let the
runtime helper report its selected callback TID, then run:

```sh
sudo python3 tools/raspberry_pi/rt_pi_trace.py \
  --tid CALLBACK_TID --seconds 30 --output /tmp/amy-scheduler.trace
```

Tracing stores events in the kernel buffer and summarizes only after capture;
it does not print from the audio callback.

## 5. Capacity measurement

`rt_pi_benchmark.py` talks to a standalone packaged `--amy-service` through
its Unix socket. Use a fresh service for every workload. The validated build
reached its configured ceiling with two active reverbs: 336 sine oscillators,
336 filtered saw oscillators, or 42 eight-operator DX7 voices. The heaviest
case used 28.5% of callback-core time with 1.778 ms p99 runtime.

Keep the synthetic level very low: CPU cost is unchanged, while hundreds of
audible oscillators are unsafe and do not make the capacity result stronger.

## Rollback

First disable the runtime changes:

```sh
sudo systemctl disable --now \
  lb-omnichord-rt-policy@"$USER".service \
  lb-omnichord-performance.service
sudo python3 tools/raspberry_pi/rt_pi_config.py set-governor ondemand
```

Restore the exact named snapshot printed by the original `apply` command:

```sh
sudo python3 tools/raspberry_pi/rt_pi_config.py rollback \
  --snapshot /var/lib/lb-omnichord-rt/snapshots/YYYYMMDDTHHMMSSZ
sudo reboot
```

If no later profile has been applied, omitting `--snapshot` selects the latest
snapshot. Naming it explicitly is safer after multiple experiments. Verify a
stock boot with:

```sh
python3 tools/raspberry_pi/rt_pi_config.py verify --profile stock
```

Do not install Debian's generic ARM64 RT kernel as part of this procedure. It
does not match the tested Raspberry Pi kernel/firmware track. A full
`PREEMPT_RT` comparison requires its own bootable image, local recovery path
and driver validation; it is unnecessary for the Pi 4 result measured here.
