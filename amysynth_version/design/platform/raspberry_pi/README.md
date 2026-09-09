# Raspberry Pi runtime

Status: physically validated platform contract
Owner: Raspberry Pi integration
Last verified: 2026-09-09

The aarch64 AppImage targets Pi 4 and Pi 5 and is self-contained. It must use
the hardware Wayland/OpenGL path when available; `--software-renderer` is a
diagnostic fallback, not the supported performance configuration.

Default invocation starts the packaged Gamma9001 AMY service as a separate
process and connects over a private Unix socket. `--serial` suppresses that
service and sends the identical wire stream to ESP32-P4; `--serial-port` and
`--serial-baud` select the UART. No runtime download occurs in either mode.

The portable application does not silently impose an operating-system
scheduler policy. For a dedicated instrument, a reversible Pi 4 host profile
has been physically measured and is provisionally shared with Pi 5: CPUs 0-1
handle the frontend, OS and IRQs, CPU 2 handles the two PipeWire data loops,
and CPU 3 handles only AMY's detected audio callback. Both source and packaged
startup inspect boot arguments, active CPU isolation, governors and the
runtime-policy service. An incomplete profile produces a visible warning and
names the matching release installer. See
[`realtime_howto.md`](realtime_howto.md); pinning the complete audio chain to
one core was measured to be substantially worse.

`run_local.sh` is source-checkout tooling. It creates/checks a clone-local
ignored virtual environment and prepares the pinned AMY dependency when
needed. Released packages never rely on that environment.

Release `R20260907T231243` was physically accepted on a 2 GiB Pi 4 at 120 Hz
with V3D acceleration in both service and `/dev/serial0` modes. This supersedes
earlier notes that Pi graphics or packaging still awaited first validation.

[`frontend_performance.md`](frontend_performance.md) records the reproducible
120 Hz physical-input benchmark, rejected alternatives and acceptance limits.
[`realtime_research.md`](realtime_research.md) contains the newer isolated-core
and targeted realtime measurements.
