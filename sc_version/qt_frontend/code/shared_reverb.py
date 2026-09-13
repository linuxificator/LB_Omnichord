from __future__ import annotations


# Product-level routing invariant. The native AMY host reserves exactly this
# many processors; musical policy chooses which buses feed each processor.
OMNI_REVERB_PROCESSOR = 0
MIDI_REVERB_PROCESSOR = 1
SHARED_REVERB_PROCESSOR_COUNT = 2


def _format(value: float) -> str:
    return f"{float(value):.9g}"


def processor_command(
    processor: int,
    level: float,
    liveness: float,
    damping: float,
) -> str:
    """Configure one shared AMY reverb processor without bus policy."""
    return (
        f"hR{int(processor)},{_format(level)},"
        f"{_format(liveness)},{_format(damping)}Z"
    )


def bus_commands(bus: int, processor: int, send: float) -> tuple[str, str]:
    """Disable patch-local reverb and route a weighted shared send."""
    bus = int(bus)
    return (
        legacy_disable_command(bus),
        send_command(bus, processor, send),
    )


def legacy_disable_command(bus: int) -> str:
    return f"y{int(bus)}h0Z"


def send_command(bus: int, processor: int, send: float) -> str:
    return f"y{int(bus)}hS{int(processor)},{_format(send)}Z"
