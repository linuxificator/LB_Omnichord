from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import app_core


PHYSICAL_STRINGS_KEY = "physical_strings"


def load_synth_catalog(
    original_loader: Callable[[Path], tuple[list[Any], int, int, int]],
    path: Path,
) -> tuple[list[Any], int, int, int]:
    synths, chord_default, strum_default, bass_default = original_loader(path)
    if not any(synth.key == PHYSICAL_STRINGS_KEY for synth in synths):
        synths = list(synths)
        synths.append(
            app_core.SynthDefinition(
                key=PHYSICAL_STRINGS_KEY,
                label="Ph. Strings",
                controls=(
                    app_core.SynthControl(
                        key="feedback",
                        label="DECAY",
                        group="TONE",
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
    return synths, chord_default, strum_default, bass_default
