from __future__ import annotations

from pathlib import Path
from collections.abc import Callable, Sequence
from typing import Any

import app_core


PHYSICAL_STRINGS_KEY = "physical_strings"
TB303_KEY = "tb303"


def _control(
    key: str,
    label: str,
    group: str,
    default: float,
    minimum: float,
    maximum: float,
    step: float,
    decimals: int,
    *,
    unit: str = "",
    scale: str = "linear",
) -> app_core.SynthControl:
    return app_core.SynthControl(
        key=key,
        label=label,
        group=group,
        default=default,
        native_default=None,
        minimum=minimum,
        maximum=maximum,
        step=step,
        decimals=decimals,
        unit=unit,
        scale=scale,
    )


def load_synth_catalog(
    original_loader: Callable[[Path], tuple[Sequence[Any], int, int, int]],
    path: Path,
) -> tuple[list[Any], int, int, int]:
    synths, chord_default, strum_default, bass_default = original_loader(path)
    synths = list(synths)
    if not any(synth.key == PHYSICAL_STRINGS_KEY for synth in synths):
        synths.append(
            app_core.SynthDefinition(
                key=PHYSICAL_STRINGS_KEY,
                label="Ph. Strings",
                controls=(
                    app_core.SynthControl(
                        key="ks_feedback",
                        label="DECAY",
                        group="extra",
                        default=0.985,
                        native_default=0.985,
                        minimum=0.90,
                        maximum=0.999,
                        step=0.001,
                        decimals=3,
                        unit="",
                        scale="linear",
                    ),
                ),
            )
        )
    if not any(synth.key == TB303_KEY for synth in synths):
        synths.append(
            app_core.SynthDefinition(
                key=TB303_KEY,
                label="TB-303",
                controls=(
                    _control("waveform", "WAVE", "extra", 0, 0, 1, 1, 0),
                    _control(
                        "filter_hz", "CUTOFF", "common", 400, 20, 10000, 10, 0,
                        unit="Hz", scale="log",
                    ),
                    _control(
                        "resonance", "RES", "common", 1.2, 0.51, 12, 0.1, 1,
                        unit="Q",
                    ),
                    _control(
                        "filter_env_octaves", "ENV MOD", "extra", 2, 0, 5, 0.1, 1,
                        unit="oct",
                    ),
                    _control(
                        "filter_decay_ms", "DECAY", "common", 250, 30, 3000, 10, 0,
                        unit="ms", scale="log",
                    ),
                    _control(
                        "accent_amount", "ACCENT", "extra", 0.35, 0, 1, 0.01, 2,
                    ),
                    _control(
                        "portamento_ms", "SLIDE", "extra", 60, 0, 300, 5, 0,
                        unit="ms",
                    ),
                ),
            )
        )
    return synths, chord_default, strum_default, bass_default
