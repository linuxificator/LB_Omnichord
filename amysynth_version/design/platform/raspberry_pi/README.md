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

On a Raspberry Pi with at least four CPUs, local-service mode reserves the
highest-numbered CPU from the Qt process and pins the complete AMY service to
that CPU before AMY creates its audio threads. The frontend keeps the remaining
CPUs. This process-level partition is deliberately implemented in the Linux/Pi
runtime adapter rather than portable application or musical code. It is not a
kernel `isolcpus` claim: operating-system work and interrupts may still run on
the AMY CPU. If affinity is unavailable, restricted by an enclosing cpuset or
cannot be changed, startup remains functional, prints a diagnostic and retains
the operating system's policy. Serial mode does not reserve a CPU because AMY
runs on the external ESP32-P4.

`run_local.sh` is source-checkout tooling. It creates/checks a clone-local
ignored virtual environment and prepares the pinned AMY dependency when
needed. Released packages never rely on that environment.

Release `R20260907T231243` was physically accepted on a 2 GiB Pi 4 at 120 Hz
with V3D acceleration in both service and `/dev/serial0` modes. This supersedes
earlier notes that Pi graphics or packaging still awaited first validation.

[`frontend_performance.md`](frontend_performance.md) records the reproducible
120 Hz physical-input benchmark, rejected alternatives and acceptance limits.
