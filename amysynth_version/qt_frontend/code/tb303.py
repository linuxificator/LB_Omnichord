from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from amy_parameter_plan import format_amy_float
from control_limits import clamp_control_value


PROGRAM_KEY = "tb303"
PROGRAM_KIND = "tb303"
SAW_DOWN = 2
PULSE = 1
DOUBLE_ORDER_LOWPASS = 4
SEQUENCE_PARAMETER_KEYS = frozenset(
    {"accent_amount", "filter_env_octaves", "portamento_ms"}
)


@dataclass(frozen=True, slots=True)
class Tb303Parameters:
    waveform: int = 0
    filter_hz: float = 400.0
    resonance: float = 1.2
    filter_env_octaves: float = 2.0
    filter_decay_ms: float = 250.0
    accent_amount: float = 0.35
    portamento_ms: float = 60.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> Tb303Parameters:
        def value(key: str, default: float) -> float:
            raw = values.get(key, default)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return float(clamp_control_value(key, default))
            return float(clamp_control_value(key, float(raw)))

        return cls(
            waveform=max(0, min(1, int(round(value("waveform", 0.0))))),
            filter_hz=value("filter_hz", 400.0),
            resonance=value("resonance", 1.2),
            filter_env_octaves=value("filter_env_octaves", 2.0),
            filter_decay_ms=value("filter_decay_ms", 250.0),
            accent_amount=value("accent_amount", 0.35),
            portamento_ms=value("portamento_ms", 60.0),
        )


def compile_voice_commands(
    *,
    synth: int,
    parameters: Tb303Parameters,
    selected_keys: Collection[str] | None = None,
    initialize: bool = False,
) -> tuple[str, ...]:
    """Compile the portable AMY voice/configuration part of the instrument."""

    selected = None if selected_keys is None else frozenset(selected_keys)

    def changed(*keys: str) -> bool:
        return selected is None or bool(selected.intersection(keys))

    commands: list[str] = []
    if initialize:
        commands.append(
            f"v0G{DOUBLE_ORDER_LOWPASS}A2,1,0,1,20,0i{int(synth)}Z"
        )
    if changed("waveform"):
        wave = PULSE if parameters.waveform else SAW_DOWN
        duty = "d0.5" if wave == PULSE else ""
        commands.append(f"v0w{wave}{duty}i{int(synth)}Z")
    if changed("filter_hz", "filter_env_octaves"):
        commands.append(
            f"v0F{format_amy_float(parameters.filter_hz)},,,,"
            f"{format_amy_float(parameters.filter_env_octaves)}i{int(synth)}Z"
        )
    if changed("resonance"):
        commands.append(
            f"v0R{format_amy_float(parameters.resonance)}i{int(synth)}Z"
        )
    if changed("filter_decay_ms"):
        commands.append(
            "v0B0,1,"
            f"{format_amy_float(parameters.filter_decay_ms)},0,20,0"
            f"i{int(synth)}Z"
        )
    if initialize:
        # Slide time is an edge property. Detached attacks explicitly use
        # zero and slide continuations apply the live user setting.
        commands.append(f"v0m0i{int(synth)}Z")
    return tuple(commands)


def articulation_fields(
    parameters: Tb303Parameters,
    *,
    accent: bool,
) -> str:
    """Return per-onset amp/filter fields without timing or note ownership."""

    strength = parameters.accent_amount if accent else 0.0
    amplitude = 1.0 + 0.5 * strength
    filter_depth = parameters.filter_env_octaves + 2.0 * strength
    return (
        f"a{format_amy_float(amplitude)}"
        f"F,,,,{format_amy_float(filter_depth)}"
    )
