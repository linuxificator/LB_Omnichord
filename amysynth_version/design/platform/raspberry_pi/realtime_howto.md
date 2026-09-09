# Dedicated Raspberry Pi realtime audio setup

Status: physically validated on Raspberry Pi 4; Raspberry Pi 5 measurements pending
Validated release: `R20260909T010905`
Validated kernel: Raspberry Pi `6.18.34+rpt-rpi-v8`, `PREEMPT`

This procedure reserves CPU 3 for AMY's audio callback and CPU 2 for
PipeWire's audio data loops. The UI, operating system and device IRQs use CPUs
0-1. It is intended for a dedicated LB Omnichord appliance, not a general-use
desktop. It changes only Raspberry Pi host configuration; it does not patch
AMY or LB Omnichord and does not weaken the wire/socket process boundary.

Every GitHub release includes a self-contained installer named
`LB_Omnichord.RYYYYMMDDHHMMSS.Pi4-Pi5-realtime-setup.sh`. It embeds the exact
versioned helper and systemd governor unit described below, applies the
reversible `audio-split` boot profile, grants the selected desktop user a
standard PAM realtime-priority limit, and requests a reboot. The application
warning points to this asset when boot arguments, CPU 2-3 isolation, the
governor, the user's realtime permission or the read-back runtime policy for
the exact AMY child is missing.
The same installer source is committed as
`qt_frontend/tools/raspberry_pi/install_realtime_profile.sh`; the release asset
embeds and executes that file rather than maintaining a second setup sequence.
It also verifies every embedded helper against a build-time SHA-256 digest
before making host changes. The separately published checksum remains
available for users who require an independently downloaded integrity check,
but it is deliberately not part of the startup warning. The manual steps
remain documented for inspection and rollback.

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

From a source checkout, the complete setup can be applied with the committed
installer instead of performing sections 2 and 3 separately:

```sh
sudo tools/raspberry_pi/install_realtime_profile.sh --user "$USER"
```

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

## 3. Grant realtime permission and launch normally

The installer writes one standard PAM limit for the selected user:

```text
USER - rtprio 80
```

It also enables the small performance-governor service. A reboot creates a new
login session with that limit and activates the boot arguments. Confirm the
permission after reconnecting:

```sh
ulimit -r
```

Expected: `80` or greater. The installer also places standard drop-ins under
`/etc/systemd/user/{pipewire,pipewire-pulse}.service.d/` and configuration
under `/etc/pipewire/{pipewire,pipewire-pulse}.conf.d/`. Systemd supplies the
resource limit; each PipeWire process uses its own `module-rt` and
`thread.affinity` support to create its `data-loop.0` on CPU 2 at FIFO 80 or
75. Application code does not mutate PipeWire threads.

There is no privileged runtime service. Start `run_local.sh` or the AppImage
normally. Its existing wrapper starts AMY and already owns the exact child PID
returned by `Popen`/`$!`. Once the audio thread exists, the wrapper performs
one policy operation:

1. confine the frontend and AMY non-audio threads to CPUs 0-1;
2. measure the busiest non-main thread of that exact AMY child;
3. assign only that callback to CPU 3/FIFO 70;
4. verify PipeWire's own `data-loop.0` policies;
5. read every affinity, scheduler and priority back before reporting success.

The wrapper never searches for AMY by process name or command line. It has no
registration socket, polling loop, watcher daemon or lifecycle protocol. It
does not take over PipeWire policy from systemd/PipeWire. AMY's
audio callback is stable for the lifetime of the local service; restarting the
application starts a new service and repeats the one-shot operation. The
frontend receives the exact child PID only to verify the applied state for its
startup warning.

For a source diagnostic after AMY has been started by a wrapper, use the PID
that wrapper printed or exported:

```sh
python3 code/raspberry_pi_realtime.py inspect --service-pid "$OMNICHORD_AMY_SERVICE_PID"
```

The normal visible startup dialog is the aggregate check. It disappears only
when boot isolation, governor, `rtprio`, exact AMY callback, frontend and both
PipeWire loop policies all match. Serial/ESP32 mode deliberately bypasses this
host-AMY policy and warning.

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

First disable the persistent governor and remove the optional user limit:

```sh
sudo systemctl disable --now lb-omnichord-performance.service
sudo rm /etc/security/limits.d/95-lb-omnichord-realtime.conf
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
