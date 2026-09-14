from __future__ import annotations

from pathlib import Path
from collections import defaultdict

import app_core
from sample_programs import load_vsco_programs
from supercollider_programs import (
    display_name,
    load_legacy_program_map,
    load_sclork_playback_profile,
    load_supercollider_programs,
)


DEFAULT_PROGRAMS = (
    "sc.sclork.prophet5pwmStrings",
    "sc.sclork.pluck",
    "sc.sclork.fmBass",
)
ACID_PROGRAMS = (
    ("sc.omni.acid303", "SC Acid 303"),
    ("sc.omni.acidOto", "SC Acid Oto"),
    ("sc.omni.acidMoog", "SC Acid Moog"),
    ("sc.omni.acidWarsaw", "SC Acid Warsaw"),
)


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


def _acid_controls() -> tuple[app_core.SynthControl, ...]:
    return (
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
        _control("accent_amount", "ACCENT", "extra", 0.35, 0, 1, 0.01, 2),
        _control(
            "portamento_ms", "SLIDE", "extra", 60, 0, 300, 5, 0,
            unit="ms",
        ),
    )


def load_synth_catalog(path: Path) -> tuple[list[app_core.SynthDefinition], int, int, int]:
    """Build the SC edition's browser without loading the AMY patch catalogue.

    Legacy keys are data-migration aliases only. They never become visible
    choices and every emitted selection is a canonical SC/sample program ID.
    Raw drum SynthDefs remain compiled and audited, but are not pitched
    instruments in the shared OMNI/MIDI browser.
    """

    instrument_root = path.parent
    supercollider_root = path.parents[1].parent / "supercollider"
    legacy_map = load_legacy_program_map(
        instrument_root / "supercollider-legacy-map.json"
    )
    playback_gains, _excluded = load_sclork_playback_profile(
        supercollider_root / "sclork-playback.json"
    )
    aliases_by_program: dict[str, list[str]] = defaultdict(list)
    for alias, program_id in legacy_map.items():
        aliases_by_program[program_id].append(alias)

    synths: list[app_core.SynthDefinition] = []
    known_keys: set[str] = set()
    for program in load_supercollider_programs(
        supercollider_root / "sclork-programs.json"
    ):
        if program.program_id not in playback_gains:
            continue
        synths.append(
            app_core.SynthDefinition(
                key=program.program_id,
                label=display_name(program.native_name),
                controls=(),
                aliases=tuple(sorted(aliases_by_program[program.program_id])),
            )
        )
        known_keys.add(program.program_id)
    for program_id, label in ACID_PROGRAMS:
        if program_id not in known_keys:
            synths.append(
                app_core.SynthDefinition(
                    key=program_id,
                    label=label,
                    controls=_acid_controls(),
                    aliases=tuple(sorted(aliases_by_program[program_id])),
                )
            )
            known_keys.add(program_id)
    for sample_program in load_vsco_programs(
        supercollider_root / "vsco-manifest.json"
    ):
        if sample_program.program_id not in known_keys:
            if sample_program.program_id == "sample.vsco.gm-styleperc":
                continue
            synths.append(
                app_core.SynthDefinition(
                    key=sample_program.program_id,
                    label="VSCO " + sample_program.display_name,
                    controls=(),
                )
            )
            known_keys.add(sample_program.program_id)
    missing_defaults = [key for key in DEFAULT_PROGRAMS if key not in known_keys]
    if missing_defaults:
        raise ValueError(
            "SC instrument catalogue misses defaults: " + ", ".join(missing_defaults)
        )
    defaults = tuple(
        next(index for index, synth in enumerate(synths) if synth.key == key)
        for key in DEFAULT_PROGRAMS
    )
    return synths, defaults[0], defaults[1], defaults[2]
