#!/usr/bin/env python3
"""Populate synths.json slider defaults from AMY's built-in patch table.

The AMY factory patch remains the authority for native timbre controls.  This
script extracts values which map directly onto the Omnichord sliders.  The DX7
ADSR sliders are a separate global output envelope (not part of the original
operator envelopes), so those use conservative instrument-family profiles.
A few Juno amplitude envelopes receive documented musical corrections where a
zero/very-fast attack is unpleasant in this application's retriggering model.

Usage:
    python generate_defaults.py /path/to/amy/src/patches.h [synths.json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

PATCH_LINE = re.compile(
    r'/\*\s*(\d+)\s*:.*?\*/\s*"((?:\\.|[^"\\])*)"\s*,?\s*$'
)
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

# -1 used to mean "leave the factory patch unchanged".  Defaults are now
# explicit for every instrument, so that sentinel must not be part of the UI
# range.  These are the actual lower bounds accepted by the AMY translation
# layer for the exposed controls.
CONTROL_MINIMUMS: dict[str, float] = {
    "filter_hz": 20.0,
    "resonance": 0.51,
    "lfo_hz": 0.01,
    "vibrato_depth": 0.0,
    "filter_lfo_depth": 0.0,
    "pulse_width": 0.05,
    "pwm_depth": 0.0,
    "portamento_ms": 0.0,
    "attack_ms": 0.0,
    "decay_ms": 0.0,
    "sustain": 0.0,
    "release_ms": 0.0,
    "algorithm": 1.0,
    "feedback": 0.0,
}

# Human-facing presentation belongs to the control definition rather than QML
# key-specific conditionals.  Frequency controls display Hz and use a
# logarithmic travel, matching how frequency is perceived.
CONTROL_DISPLAY: dict[str, tuple[str, str, str]] = {
    "filter_hz": ("VCF base", "Hz", "log"),
    "resonance": ("Resonance", "Q", "linear"),
    "lfo_hz": ("LFO rate", "Hz", "log"),
    "vibrato_depth": ("Vibrato", "oct", "linear"),
    "filter_lfo_depth": ("VCF LFO", "oct", "linear"),
    "pulse_width": ("Pulse width", "", "linear"),
    "pwm_depth": ("PWM depth", "", "linear"),
    "portamento_ms": ("Portamento", "ms", "linear"),
    "attack_ms": ("Attack", "ms", "linear"),
    "decay_ms": ("Decay", "ms", "linear"),
    "sustain": ("Sustain", "", "linear"),
    "release_ms": ("Release", "ms", "linear"),
    "algorithm": ("Algorithm", "", "linear"),
    "feedback": ("Feedback", "", "linear"),
}


def c_unescape(text: str) -> str:
    return bytes(text, "utf-8").decode("unicode_escape")


def load_patch_commands(path: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PATCH_LINE.search(line)
        if match:
            result[int(match.group(1))] = c_unescape(match.group(2))
    if len(result) < 256:
        raise RuntimeError(f"only parsed {len(result)} AMY patches from {path}")
    return result


def commands(patch: str) -> list[str]:
    return [part for part in patch.split("Z") if part]


def first_command(parts: Iterable[str], prefix: str) -> str | None:
    return next((part for part in parts if part.startswith(prefix)), None)


def scalar_after(command: str | None, key: str, default: float = 0.0) -> float:
    if not command:
        return default
    match = re.search(re.escape(key) + f"({NUMBER})", command)
    return float(match.group(1)) if match else default


def csv_after(command: str | None, key: str, stop_letters: str) -> list[float | None]:
    if not command:
        return []
    match = re.search(
        re.escape(key) + f"([^" + re.escape(stop_letters) + r"]*)",
        command,
    )
    if not match:
        return []
    values: list[float | None] = []
    for raw in match.group(1).split(","):
        raw = raw.strip()
        if not raw:
            values.append(None)
        else:
            try:
                values.append(float(raw))
            except ValueError:
                break
    return values


def value_at(values: list[float | None], index: int, default: float = 0.0) -> float:
    if index >= len(values) or values[index] is None:
        return default
    return float(values[index])


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def juno_native(patch: str) -> dict[str, float]:
    parts = commands(patch)
    lfo = next(
        (part for part in parts if part.startswith("v1") and "f" in part),
        None,
    )
    pulse = next(
        (
            part
            for part in parts
            if part.startswith("v2") and "f" in part and "d" in part
        ),
        None,
    )
    filt = first_command(parts, "v0F")
    amp = first_command(parts, "v0a")

    lfo_values = csv_after(
        lfo,
        "f",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    pitch_values = csv_after(
        pulse,
        "f",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    duty_values = csv_after(
        pulse,
        "d",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    filter_values = csv_after(filt, "F", "R")
    amp_values = csv_after(amp, "A", "B")

    return {
        "filter_hz": value_at(filter_values, 0, 4000.0),
        "resonance": scalar_after(filt, "R", 0.7),
        "lfo_hz": value_at(lfo_values, 0, 1.0),
        "vibrato_depth": value_at(pitch_values, 5, 0.0),
        "filter_lfo_depth": value_at(filter_values, 5, 0.0),
        "pulse_width": value_at(duty_values, 0, 0.5),
        "pwm_depth": value_at(duty_values, 5, 0.0),
        "portamento_ms": scalar_after(pulse, "m", 0.0),
        "attack_ms": value_at(amp_values, 0, 10.0),
        "decay_ms": value_at(amp_values, 2, 500.0),
        "sustain": value_at(amp_values, 3, 0.8),
        "release_ms": value_at(amp_values, 4, 250.0),
    }


def dx7_native(patch: str) -> dict[str, float]:
    parts = commands(patch)
    lfo = first_command(parts, "v1")
    algo = first_command(parts, "v0")
    lfo_values = csv_after(
        lfo,
        "f",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    )
    pitch_values = csv_after(algo, "f", "b")
    algorithm_match = re.search(r"o(\d+)$", algo or "")
    return {
        "algorithm": float(algorithm_match.group(1)) if algorithm_match else 1.0,
        "feedback": scalar_after(algo, "b", 0.0),
        "lfo_hz": value_at(lfo_values, 0, 1.0),
        "vibrato_depth": value_at(pitch_values, 5, 0.0),
        "portamento_ms": 0.0,
    }


# The DX7 sliders control an additional ALGO-output ADSR.  These profiles are
# intentionally broad and conservative so the original six-operator envelopes
# still provide most of the character.
DX7_ENVELOPES: list[tuple[tuple[str, ...], tuple[float, float, float, float]]] = [
    (("BRASS",), (40.0, 350.0, 0.88, 250.0)),
    (("STRINGS",), (350.0, 1200.0, 0.82, 1200.0)),
    (("E.PIANO", "PIANO"), (10.0, 3500.0, 0.30, 900.0)),
    (("BASS",), (10.0, 700.0, 0.55, 250.0)),
    (("VIBE",), (10.0, 2600.0, 0.10, 1500.0)),
    (("STEEL DRUM",), (10.0, 1800.0, 0.0, 1000.0)),
    (("CELESTE",), (10.0, 3000.0, 0.08, 1800.0)),
    (("E.ORGAN",), (10.0, 0.0, 1.0, 180.0)),
    (("PIPES", "SAX"), (70.0, 300.0, 0.90, 300.0)),
    (("GUITAR",), (10.0, 2200.0, 0.18, 700.0)),
    (("GLOKENSPL", "CHIMES"), (10.0, 5000.0, 0.0, 3000.0)),
    (("XYLOPHONE",), (10.0, 900.0, 0.0, 450.0)),
    (("CHIME-STRG",), (250.0, 2500.0, 0.45, 2500.0)),
    (("SHIMMER",), (450.0, 2500.0, 0.75, 3000.0)),
]


def dx7_envelope(label: str) -> dict[str, float]:
    upper = label.upper()
    for needles, values in DX7_ENVELOPES:
        if any(needle in upper for needle in needles):
            attack, decay, sustain, release = values
            return {
                "attack_ms": attack,
                "decay_ms": decay,
                "sustain": sustain,
                "release_ms": release,
            }
    return {
        "attack_ms": 10.0,
        "decay_ms": 1000.0,
        "sustain": 0.75,
        "release_ms": 600.0,
    }


def apply_juno_musical_corrections(label: str, values: dict[str, float]) -> None:
    # AMY's Juno patches are the primary source.  Corrections below are small
    # VCA-envelope adaptations for this application's hard retrigger behavior.
    if label in {"Harpsichord 1", "Harpsichord 2"}:
        # Keep the plucked decay, but avoid a waveform-phase click at note-on.
        values["attack_ms"] = 20.0
        if label == "Harpsichord 1":
            # Keep the UI default consistent with the P4 stability correction
            # applied immediately after AMY factory patch 68 is loaded.
            values["filter_hz"] = 16000.0
            values["resonance"] = 4.0
    elif label == "Orchestral Pad":
        values.update(
            attack_ms=600.0,
            decay_ms=1800.0,
            sustain=0.78,
            release_ms=1800.0,
        )
    elif label == "Synth Pad":
        values["attack_ms"] = max(values["attack_ms"], 350.0)
        values["sustain"] = max(values["sustain"], 0.70)
        values["release_ms"] = max(values["release_ms"], 1200.0)
    elif "Organ" in label or label == "Owgan":
        # A tiny de-click attack is effectively instantaneous musically.
        values["attack_ms"] = max(values["attack_ms"], 10.0)


def populate(catalog: dict, patches: dict[int, str]) -> None:
    for synth in catalog["synths"]:
        patch_number = int(synth["patch"])
        patch = patches[patch_number]
        engine = str(synth["engine"])
        label = str(synth["label"])

        if engine == "Juno":
            native_defaults = juno_native(patch)
            defaults = dict(native_defaults)
            apply_juno_musical_corrections(label, defaults)
        elif engine == "DX7":
            native_defaults = dx7_native(patch)
            defaults = dict(native_defaults)
            defaults.update(dx7_envelope(label))
        else:
            raise ValueError(f"unsupported engine {engine!r} for {synth['key']}")

        controls = {control["key"]: control for control in synth["controls"]}
        if set(defaults) != set(controls):
            missing = set(controls) - set(defaults)
            extra = set(defaults) - set(controls)
            raise ValueError(
                f"{synth['key']} default/control mismatch: missing={missing}, extra={extra}"
            )

        for key, value in defaults.items():
            control = controls[key]
            control["minimum"] = CONTROL_MINIMUMS[key]
            minimum = float(control["minimum"])
            maximum = float(control["maximum"])
            native_value = native_defaults.get(key)
            control["native_default"] = (
                None
                if native_value is None
                else clamp(native_value, minimum, maximum)
            )
            control["default"] = clamp(value, minimum, maximum)
            label_text, unit, scale = CONTROL_DISPLAY[key]
            control["label"] = label_text
            control["unit"] = unit
            control["scale"] = scale

    catalog["schema_version"] = max(5, int(catalog.get("schema_version", 0)))
    catalog["source"]["slider_defaults"] = (
        "Native AMY factory values are retained separately from application "
        "defaults so unchanged native controls are not retransmitted; musical "
        "VCA corrections are documented in README_defaults.md; frequency "
        "controls display Hz with logarithmic slider travel"
    )


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(
            f"usage: {Path(sys.argv[0]).name} PATCHES_H [SYNTHS_JSON]",
            file=sys.stderr,
        )
        return 2
    patches_path = Path(sys.argv[1])
    catalog_path = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else Path(__file__).with_name("synths.json")
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    populate(catalog, load_patch_commands(patches_path))
    catalog_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
