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

The frontend and local AMY service retain the operating system's CPU scheduler
policy. Physical tracing found that pinning AMY to one otherwise lightly loaded
CPU made its normal and tail scheduler latency worse, while reserving two CPUs
did not help a backend with one active render thread. No boot-time CPU
isolation, realtime priority or Raspberry-Pi-specific musical/UI behavior is
therefore imposed. The evidence and exact acceptance boundary are recorded in
[`frontend_performance.md`](frontend_performance.md).

`run_local.sh` is source-checkout tooling. It creates/checks a clone-local
ignored virtual environment and prepares the pinned AMY dependency when
needed. Released packages never rely on that environment.

Release `R20260907T231243` was physically accepted on a 2 GiB Pi 4 at 120 Hz
with V3D acceleration in both service and `/dev/serial0` modes. This supersedes
earlier notes that Pi graphics or packaging still awaited first validation.

[`frontend_performance.md`](frontend_performance.md) records the reproducible
120 Hz physical-input benchmark, rejected alternatives and acceptance limits.
