from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrumKit:
    kit_id: str
    label: str
    programs: tuple[tuple[str, str], ...]
    gain: float = 1.0

    def program_for(self, role: str) -> str:
        mapping = dict(self.programs)
        return mapping.get(role, mapping["*"])


_KICK = frozenset({"low_primary", "low_secondary", "timekeeper_foot"})
_SNARE = frozenset({"backbeat_primary", "backbeat_soft", "ghost_detail", "electronic_detail"})
_HAT = frozenset({"timekeeper_primary", "timekeeper_open", "texture_shaker", "dry_click"})
_TOM = frozenset({"tonal_low", "tonal_mid", "tonal_high", "timeline_primary"})
_CLAP = frozenset({"hand_low", "hand_high", "hand_accent"})


def _family(
    kit_id: str,
    label: str,
    *,
    kick: str,
    snare: str,
    hat: str,
    tom: str,
    clap: str,
    cymbal: str,
    gain: float,
) -> DrumKit:
    assignments: dict[str, str] = {"*": cymbal}
    for roles, program in (
        (_KICK, kick),
        (_SNARE, snare),
        (_HAT, hat),
        (_TOM, tom),
        (_CLAP, clap),
    ):
        assignments.update((role, program) for role in roles)
    return DrumKit(kit_id, label, tuple(assignments.items()), gain)


DRUM_KITS = (
    DrumKit("pcm-vsco", "VSCO PCM", (("*", "sample.vsco.gm-styleperc"),), 1.0),
    DrumKit("sc-basic", "SC Basic", (("*", "sc.omni.drum"),), 0.82),
    _family(
        "sc-808", "SC 808",
        kick="sc.sclork.kick808", snare="sc.sclork.snare909",
        hat="sc.sclork.sosHats", tom="sc.sclork.squareDrum",
        clap="sc.sclork.clapGray", cymbal="sc.sclork.cymbal808", gain=0.62,
    ),
    _family(
        "sc-electro", "SC Electro",
        kick="sc.sclork.kick_electro", snare="sc.sclork.snareElectro",
        hat="sc.sclork.hihatElectro", tom="sc.sclork.squareDrum",
        clap="sc.sclork.clapElectro", cymbal="sc.sclork.cymbalicMCLD", gain=0.62,
    ),
    _family(
        "sc-oto309", "SC Oto 309",
        kick="sc.sclork.kick_oto309", snare="sc.sclork.snareOto309",
        hat="sc.sclork.hihat1", tom="sc.sclork.squareDrum",
        clap="sc.sclork.clapOto309", cymbal="sc.sclork.cymbal808", gain=0.62,
    ),
    _family(
        "sc-sos", "SC SOS",
        kick="sc.sclork.sosKick", snare="sc.sclork.sosSnare",
        hat="sc.sclork.sosHats", tom="sc.sclork.sosTom",
        clap="sc.sclork.oneclapThor", cymbal="sc.sclork.sosHats", gain=0.58,
    ),
)

DEFAULT_DRUM_KIT_ID = DRUM_KITS[0].kit_id


def kit_by_id(kit_id: str) -> DrumKit:
    requested = str(kit_id)
    return next((kit for kit in DRUM_KITS if kit.kit_id == requested), DRUM_KITS[0])


def midi_role(note: int) -> str:
    value = int(note)
    if value in {35, 36, 44}:
        return "low_primary"
    if value in {38, 40}:
        return "backbeat_primary"
    if value == 39:
        return "hand_accent"
    if value in {41, 43, 45}:
        return "tonal_low"
    if value in {47, 48}:
        return "tonal_mid"
    if value == 50:
        return "tonal_high"
    if value in {42, 46, 54, 69, 70, 71}:
        return "timekeeper_open" if value == 46 else "timekeeper_primary"
    if value in {49, 51, 52, 53, 55, 57, 59}:
        return "section_accent"
    if value in {60, 61, 62, 63, 64}:
        return "hand_high" if value in {60, 62, 63} else "hand_low"
    return "electronic_detail"


def resolve_program(kit_id: str, role: str) -> tuple[str, float]:
    kit = kit_by_id(kit_id)
    return kit.program_for(str(role)), kit.gain
