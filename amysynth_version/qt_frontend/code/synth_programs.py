from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SynthProgram:
    """Engine program behind a frontend synth choice.

    A program is deliberately not synonymous with a ROM patch number.  ROM
    Juno/DX7 patches are one program type; runtime/user patches and synthesis
    engines such as Karplus-Strong can use the same frontend state path.
    """

    key: str
    kind: str
    patch: int | None = None
    oscs_per_voice: int = 1
    wave: int | None = None
    feedback: float | None = None

    @property
    def is_rom_patch(self) -> bool:
        return self.kind == "rom_patch" and self.patch is not None


def resolve_program(key: str, config: dict[str, Any]) -> SynthProgram | None:
    key = str(key)

    raw_programs = config.get("synth_programs", {})
    if isinstance(raw_programs, dict) and key in raw_programs:
        raw = raw_programs[key]
        if not isinstance(raw, dict):
            raise ValueError(f"synth program {key!r} must be an object")
        kind = str(raw.get("type", "")).strip().lower()
        if kind == "karplus_strong":
            return SynthProgram(
                key=key,
                kind=kind,
                oscs_per_voice=max(1, int(raw.get("oscs_per_voice", 1))),
                wave=int(raw.get("wave", 6)),
                feedback=max(0.0, min(1.0, float(raw.get("feedback", 0.985)))),
            )
        if kind == "user_patch":
            patch = int(raw["patch"])
            if patch < 1024:
                raise ValueError(
                    f"user patch program {key!r} must use patch >= 1024"
                )
            return SynthProgram(
                key=key,
                kind=kind,
                patch=patch,
                oscs_per_voice=max(1, int(raw.get("oscs_per_voice", 1))),
            )
        if kind == "rom_patch":
            patch = int(raw["patch"])
            return SynthProgram(
                key=key,
                kind=kind,
                patch=patch,
                oscs_per_voice=max(
                    1,
                    int(raw.get("oscs_per_voice", 6 if patch < 128 else 8)),
                ),
            )
        raise ValueError(f"unsupported synth program type {kind!r} for {key!r}")

    # Existing catalogue keys remain zero-maintenance: their ROM patch number
    # is encoded in the stable key.  The old JSON patch-number table is no
    # longer needed to describe their engine type.
    if key.startswith("juno_") and key[5:].isdigit():
        patch = int(key[5:])
        if 0 <= patch <= 127:
            return SynthProgram(
                key=key,
                kind="rom_patch",
                patch=patch,
                oscs_per_voice=6,
            )
    if key.startswith("dx7_") and key[4:].isdigit():
        patch = int(key[4:])
        if 128 <= patch <= 255:
            return SynthProgram(
                key=key,
                kind="rom_patch",
                patch=patch,
                oscs_per_voice=8,
            )
    return None


def maximum_program_oscs_per_voice(config: dict[str, Any]) -> int:
    maximum = 8  # Existing DX7 programs.
    raw_programs = config.get("synth_programs", {})
    if isinstance(raw_programs, dict):
        for key in raw_programs:
            program = resolve_program(str(key), config)
            if program is not None:
                maximum = max(maximum, program.oscs_per_voice)
    return maximum
