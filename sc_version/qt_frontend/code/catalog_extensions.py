from __future__ import annotations

from pathlib import Path
from collections import defaultdict
from dataclasses import replace

import app_core
from vsco_browser import load_vsco_browser
from supercollider_programs import (
    SuperColliderProgram,
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
    native_default=default,
        minimum=minimum,
        maximum=maximum,
        step=step,
        decimals=decimals,
        unit=unit,
        scale=scale,
    )


def _acid_controls() -> tuple[app_core.SynthControl, ...]:
    controls = (
        _control("waveform", "WAVE", "extra", 0, 0, 1, 1, 0),
        _control(
            "filter_hz", "CUTOFF", "extra", 400, 20, 20000, 10, 0,
            unit="Hz", scale="log",
        ),
        _control(
            "resonance", "RES", "extra", 1.2, 0.51, 12, 0.1, 1,
            unit="Q",
        ),
        _control(
            "filter_env_octaves", "ENV MOD", "extra", 2, 0, 5, 0.1, 1,
            unit="oct",
        ),
        _control(
            "filter_decay_ms", "F DEC", "extra", 250, 30, 3000, 10, 0,
            unit="ms", scale="log",
        ),
        _control("accent_amount", "ACCENT", "extra", 0.35, 0, 1, 0.01, 2),
        _control(
            "portamento_ms", "SLIDE", "extra", 60, 0, 300, 5, 0,
            unit="ms",
        ),
        _control("attack_ms", "ATTACK", "common", 6, 0, 3000, 1, 0, unit="ms"),
        _control("decay_ms", "DECAY", "common", 100, 0, 10000, 5, 0, unit="ms"),
        _control("sustain", "SUSTAIN", "common", 1, 0, 1, 0.01, 2),
        _control("release_ms", "RELEASE", "common", 180, 0, 15000, 5, 0, unit="ms"),
    )
    extras = [control for control in controls if control.group == "extra"]
    common = [control for control in controls if control.group == "common"]
    return tuple(extras[:4] + common + [replace(control, group="common") for control in extras[4:]])


_NATIVE_ALIASES: tuple[tuple[str, tuple[str, ...], str, float, float, float, int, str, str], ...] = (
    ("attack_ms", ("att", "attack", "atk"), "ATTACK", 0.0, 3000.0, 1.0, 0, "ms", "linear"),
    ("decay_ms", ("dec", "decay"), "DECAY", 0.0, 10000.0, 5.0, 0, "ms", "linear"),
    ("sustain", ("sus", "sustain"), "SUSTAIN", 0.0, 1.0, 0.01, 2, "", "linear"),
    ("release_ms", ("rel", "release"), "RELEASE", 0.0, 15000.0, 5.0, 0, "ms", "linear"),
    ("filter_hz", ("cutoff",), "CUTOFF", 20.0, 20000.0, 10.0, 0, "Hz", "log"),
    ("filter_rq", ("rq",), "FILTER RQ", 0.001, 1.0, 0.01, 3, "", "log"),
    ("portamento_ms", ("lagTime", "slideTime", "glide", "freqLag", "lagamount"), "GLIDE", 0.0, 1000.0, 5.0, 0, "ms", "linear"),
    ("blend", ("blend",), "BLEND", 0.0, 1.0, 0.01, 2, "", "linear"),
    ("mix", ("mix",), "MIX", 0.0, 1.0, 0.01, 2, "", "linear"),
    ("pulse_width", ("width", "pw"), "WIDTH", 0.05, 0.95, 0.01, 2, "", "linear"),
    ("tone", ("tone",), "TONE", 0.0, 1.0, 0.01, 2, "", "linear"),
)


def _sclork_controls(program: SuperColliderProgram) -> tuple[app_core.SynthControl, ...]:
    """Expose only reviewed, portable controls from immutable source metadata."""

    native = set(program.controls)
    defaults = dict(program.control_defaults)
    common: list[app_core.SynthControl] = []
    extra: list[app_core.SynthControl] = []
    for key, aliases, label, minimum, maximum, step, decimals, unit, scale in _NATIVE_ALIASES:
        source_key = next((candidate for candidate in aliases if candidate in native), None)
        if source_key is None or source_key not in defaults:
            continue
        value = float(defaults[source_key])
        if key.endswith("_ms"):
            value *= 1000.0
        value = max(minimum, min(maximum, value))
        target = common if key in {"attack_ms", "decay_ms", "sustain", "release_ms"} else extra
        target.append(
            _control(key, label, "common" if target is common else "extra", value,
                     minimum, maximum, step, decimals, unit=unit, scale=scale)
        )
    # ADSR always starts the lower row. Surplus sound controls continue to its
    # right; at most four controls occupy the upper row.
    overflow = extra[4:]
    return tuple(extra[:4] + common + [replace(control, group="common") for control in overflow])


def resolve_supercollider_asset_root(frontend_root: Path) -> Path:
    """Resolve source and frozen layouts without depending on the platform."""

    root = Path(frontend_root).resolve()
    candidates = (root / "supercollider", root.parent / "supercollider")
    for candidate in candidates:
        if (candidate / "sclork-playback.json").is_file():
            return candidate
    raise FileNotFoundError(
        "SuperCollider instrument assets are unavailable below or beside "
        f"{root}"
    )


def load_synth_catalog(
    path: Path,
    *,
    supercollider_root: Path | None = None,
) -> tuple[list[app_core.SynthDefinition], int, int, int]:
    """Build the SC edition's browser without loading the AMY patch catalogue.

    Legacy keys are data-migration aliases only. They never become visible
    choices and every emitted selection is a canonical SC/sample program ID.
    Raw drum SynthDefs remain compiled and audited, but are not pitched
    instruments in the shared OMNI/MIDI browser.
    """

    instrument_root = path.parent
    if supercollider_root is None:
        supercollider_root = resolve_supercollider_asset_root(path.parent.parent)
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
        # Drum SynthDefs are available exclusively through the two drum-kit
        # rollers. Their calibration belongs in the shared playback profile,
        # but that must never make them leak into the pitched browser.
        if program.category == "drums" or program.program_id not in playback_gains:
            continue
        synths.append(
            app_core.SynthDefinition(
                key=program.program_id,
                label=display_name(program.native_name),
                controls=_sclork_controls(program),
                aliases=tuple(sorted(aliases_by_program[program.program_id])),
            )
        )
        known_keys.add(program.program_id)
    for program_id, label in ACID_PROGRAMS:
        if program_id not in known_keys:
            synths.append(
                app_core.SynthDefinition(
                    key=program_id,
                    label=label.removeprefix("SC "),
                    controls=_acid_controls(),
                    aliases=tuple(sorted(aliases_by_program[program_id])),
                    supports_riff_articulation=True,
                )
            )
            known_keys.add(program_id)
    for sample_choice in load_vsco_browser(
        supercollider_root / "vsco-manifest.json"
    ):
        if sample_choice.program_id not in known_keys:
            synths.append(
                app_core.SynthDefinition(
                    key=sample_choice.program_id,
                    label=sample_choice.family,
                    controls=(),
                    kind="sample",
                    browser_group=sample_choice.family,
                    variant_label=sample_choice.variant,
                    articulation_label=sample_choice.articulation,
                )
            )
            known_keys.add(sample_choice.program_id)
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
