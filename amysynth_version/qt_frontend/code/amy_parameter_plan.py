from __future__ import annotations

from collections.abc import Mapping, Set

from control_limits import clamp_control_value


def format_amy_float(value: float) -> str:
    return f"{float(value):.9g}"


def compile_parameter_commands(
    *,
    patch: int,
    synth: int,
    parameters: Mapping[str, float],
    selected_keys: Set[str] | None = None,
) -> tuple[str, ...]:
    """Compile shared Juno/DX7 controls without transport or UI policy."""

    params = {str(key): float(value) for key, value in parameters.items()}
    commands: list[str] = []

    def nonnegative(name: str, *, ignore_selection: bool = False) -> float | None:
        if not ignore_selection and selected_keys is not None and name not in selected_keys:
            return None
        value = params.get(name)
        if value is None or value < 0:
            return None
        return float(clamp_control_value(name, value))

    lfo = nonnegative("lfo_hz")
    portamento = nonnegative("portamento_ms")
    if 0 <= patch <= 127:
        cutoff = nonnegative("filter_hz")
        resonance = nonnegative("resonance")
        if cutoff is not None:
            commands.append(f"v0F{format_amy_float(cutoff)}i{synth}Z")
        if resonance is not None:
            commands.append(f"v0R{format_amy_float(resonance)}i{synth}Z")
        if lfo is not None:
            commands.append(f"v1f{format_amy_float(lfo)}i{synth}Z")

        vibrato = nonnegative("vibrato_depth")
        if vibrato is not None:
            depth = max(0.0, min(0.05, vibrato))
            for oscillator in (2, 3, 4):
                commands.append(f"v{oscillator}f,,,,,{format_amy_float(depth)}i{synth}Z")
        filter_lfo = nonnegative("filter_lfo_depth")
        if filter_lfo is not None:
            commands.append(f"v0F,,,,,{format_amy_float(filter_lfo)}i{synth}Z")
        pulse = nonnegative("pulse_width")
        if pulse is not None:
            commands.append(f"v2d{format_amy_float(max(0.05, min(0.95, pulse)))}i{synth}Z")
        pwm = nonnegative("pwm_depth")
        if pwm is not None:
            commands.append(f"v2d,,,,,{format_amy_float(max(0.0, min(0.45, pwm)))}i{synth}Z")
        if portamento is not None:
            milliseconds = max(0, int(round(portamento)))
            for oscillator in (2, 3, 4):
                commands.append(f"v{oscillator}m{milliseconds}i{synth}Z")

        envelope = tuple(
            nonnegative(name) for name in ("attack_ms", "decay_ms", "sustain", "release_ms")
        )
        if any(value is not None for value in envelope):
            attack, decay, sustain, release = envelope
            fields = (
                format_amy_float(attack) if attack is not None else "",
                "",
                format_amy_float(decay) if decay is not None else "",
                format_amy_float(max(0.0, min(1.0, sustain))) if sustain is not None else "",
                format_amy_float(release) if release is not None else "",
                "",
            )
            commands.append(f"v0A{','.join(fields)}i{synth}Z")

    elif 128 <= patch <= 255:
        algorithm = nonnegative("algorithm")
        feedback = nonnegative("feedback")
        if algorithm is not None:
            commands.append(f"v0o{max(1, min(32, int(round(algorithm))))}i{synth}Z")
        if feedback is not None:
            commands.append(f"v0b{format_amy_float(max(0.0, min(1.0, feedback)))}i{synth}Z")
        if lfo is not None:
            commands.append(f"v1f{format_amy_float(lfo)}i{synth}Z")
        vibrato = nonnegative("vibrato_depth")
        if vibrato is not None:
            commands.append(f"v0f,,,,,{format_amy_float(max(0.0, min(0.05, vibrato)))}i{synth}Z")
        if portamento is not None:
            commands.append(f"v0m{max(0, int(round(portamento)))}i{synth}Z")

        envelope_keys = {"attack_ms", "decay_ms", "sustain", "release_ms"}
        if selected_keys is None or bool(selected_keys & envelope_keys):
            attack, decay, sustain, release = (
                nonnegative(name, ignore_selection=True)
                for name in ("attack_ms", "decay_ms", "sustain", "release_ms")
            )
            if any(value is not None for value in (attack, decay, sustain, release)):
                a = 0.0 if attack is None else max(0.0, attack)
                d = 0.0 if decay is None else max(0.0, decay)
                s = 1.0 if sustain is None else max(0.0, min(1.0, sustain))
                r = 60000.0 if release is None else max(0.0, release)
                commands.append(
                    f"v0a,,,1A{format_amy_float(a)},1,{format_amy_float(d)},"
                    f"{format_amy_float(s)},{format_amy_float(r)},0i{synth}Z"
                )
    return tuple(commands)
