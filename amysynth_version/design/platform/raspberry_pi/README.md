# Raspberry Pi runtime

Status: physically validated platform contract
Owner: Raspberry Pi integration
Last verified: 2026-09-13

The aarch64 AppImage targets Pi 4 and Pi 5 and is self-contained. It must use
the hardware Wayland/OpenGL path when available; `--software-renderer` is a
diagnostic fallback, not the supported performance configuration.

Default invocation starts the packaged Gamma9001 AMY service as a separate
process and connects over a private Unix socket. `--serial` suppresses that
service and sends the identical wire stream to ESP32-P4; `--serial-port` and
`--serial-baud` select the UART. No runtime download occurs in either mode.

For a dedicated instrument, a reversible Pi 4 host profile has been physically
measured and is provisionally shared with Pi 5: CPUs 0-1 handle the frontend,
OS and IRQs, CPU 2 handles the two PipeWire data loops, and CPU 3 handles only
AMY's detected audio callback. CPU frequency scaling remains under Raspberry
Pi OS's normal `ondemand` governor; no product service holds the shared clock
at its maximum. The installer uses the standard Linux PAM
realtime-priority limit to grant the desktop user permission. Systemd grants
the same limit to its PipeWire user services; PipeWire's own `module-rt` and
data-loop affinity configuration own those threads. The existing source or
AppImage launch wrapper applies policy once only to itself and the exact AMY
child PID it started, then reads every relevant setting back. There is no
privileged watcher, name-based AMY selection, polling or private lifecycle
protocol.
Serial/ESP32 mode does not request or warn about host-AMY policy. An incomplete
profile produces a visible warning and names the matching release installer.
See [`realtime_howto.md`](realtime_howto.md); pinning the complete audio chain
to one core was measured to be substantially worse.

`run_local.sh` is source-checkout tooling. It creates/checks a clone-local
ignored virtual environment and prepares the pinned AMY dependency when
needed. Released packages never rely on that environment.

AppImage `R20260909161844`, built by the complete successful platform run
`34375905899`, was physically accepted on a 2 GiB Pi 4 after a clean reboot.
The packaged launcher applied the exact runtime layout above and an external
20-second 120 Hz touch sweep produced no warning, overload, dropout, binding
loop or throttling. Source and `/dev/serial0` modes were also physically
validated. This is the current setup; earlier watcher- and process-discovery
designs are not supported deployment alternatives.

On a Pi 5 Model B Rev 1.1, the revised `ondemand` startup contract was also
validated against an exact packaged AMY child. It selected one callback on
CPU 3 at FIFO 70, left both other AMY threads on CPUs 0-1 at normal priority,
retained PipeWire's two loops on CPU 2 at FIFO 80/75, and produced no startup
warning after complete read-back.

[`frontend_performance.md`](frontend_performance.md) records the reproducible
120 Hz physical-input benchmark, rejected alternatives and acceptance limits.
[`realtime_research.md`](realtime_research.md) contains the newer isolated-core
and targeted realtime measurements.
