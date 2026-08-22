from __future__ import annotations

import math


# Absolute application safety limits. Catalogue entries may narrow these
# ranges, never widen them. Values are in the units shown by the UI.
CONTROL_LIMITS: dict[str, tuple[float, float]] = {
    "filter_hz": (20.0, 10000.0),
    "resonance": (0.51, 12.0),
    "lfo_hz": (0.1, 20.0),
    "vibrato_depth": (0.0, 0.05),
    "filter_lfo_depth": (0.0, 0.5),
    "pulse_width": (0.05, 0.95),
    "pwm_depth": (0.0, 0.45),
    "portamento_ms": (0.0, 1000.0),
    "attack_ms": (0.0, 3000.0),
    "decay_ms": (0.0, 10000.0),
    "sustain": (0.0, 1.0),
    "release_ms": (0.0, 10000.0),
    "algorithm": (1.0, 32.0),
    # DX7 operator feedback uses AMY's normalized 0..0.5 range.
    "feedback": (0.0, 0.5),
    # Karplus-Strong uses the AMY oscillator feedback coefficient as its
    # physical decay control. Keep it distinct from DX7 feedback so the two
    # synth engines can expose appropriate UI ranges without weakening either.
    "ks_feedback": (0.90, 0.9999),
}


def hard_range(key: str) -> tuple[float, float] | None:
    return CONTROL_LIMITS.get(str(key))


def bounded_control_range(
    key: str,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    low = float(minimum)
    high = float(maximum)
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise ValueError(f"invalid range for {key}: {minimum}..{maximum}")
    hard = hard_range(key)
    if hard is not None:
        low = max(low, hard[0])
        high = min(high, hard[1])
    if low > high:
        raise ValueError(f"empty safe range for {key}: {low}..{high}")
    return low, high


def clamp_control_value(key: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite value for {key}: {value!r}")
    hard = hard_range(key)
    if hard is None:
        return number
    return max(hard[0], min(hard[1], number))
