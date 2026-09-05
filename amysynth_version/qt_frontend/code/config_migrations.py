from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


CURRENT_CONFIG_REVISION = 10
JsonObject = dict[str, Any]


# These values are the historical capacity contract introduced with revision
# 4. They belong in the explicit migration, not as runtime consumer fallbacks.
REVISION_FOUR_PATTERN_CAPACITIES = {
    "amy_max_patterns": 1024,
    "amy_max_pattern_tags": 64,
    "amy_max_pattern_instances": 32,
}
REVISION_FOUR_OSS_MIDI_GLOBS = (
    "/dev/midi",
    "/dev/midi[0-9]*",
    "/dev/amidi[0-9]*",
)

# Revision 4 was published with this Tiny profile even though the hosted
# product line had already selected Gamma9001.  Keep both maps here as an
# immutable migration contract: runtime code must continue to consume the
# resolved configuration rather than duplicate either mapping.
REVISION_FOUR_SHIPPED_TINY_MAP = {
    "bd_haus": {"preset": 1, "note": 39},
    "drum_bass_hard": {"preset": 1, "note": 39},
    "drum_bass_soft": {"preset": 1, "note": 39},
    "drum_snare_hard": {"preset": 2, "note": 45},
    "drum_snare_soft": {"preset": 5, "note": 41},
    "drum_cymbal_closed": {"preset": 6, "note": 53},
    "drum_cymbal_pedal": {"preset": 7, "note": 61},
    "drum_cymbal_open": {"preset": 7, "note": 56},
    "drum_tom_hi_soft": {"preset": 8, "note": 73},
    "drum_tom_mid_soft": {"preset": 8, "note": 63},
    "drum_tom_lo_soft": {"preset": 8, "note": 61},
    "elec_tick": {"preset": 4, "note": 51},
    "perc_bell": {"preset": 10, "note": 69},
    "perc_snap": {"preset": 9, "note": 94},
}
REVISION_FIVE_GAMMA9001_MAP = {
    "bd_haus": {"preset": 0, "note": 60},
    "drum_bass_hard": {"preset": 2, "note": 60},
    "drum_bass_soft": {"preset": 0, "note": 60},
    "drum_snare_hard": {"preset": 12, "note": 45},
    "drum_snare_soft": {"preset": 14, "note": 41},
    "drum_cymbal_closed": {"preset": 9, "note": 60},
    "drum_cymbal_pedal": {"preset": 9, "note": 57},
    "drum_cymbal_open": {"preset": 10, "note": 60},
    "drum_tom_hi_soft": {"preset": 17, "note": 70},
    "drum_tom_mid_soft": {"preset": 17, "note": 67},
    "drum_tom_lo_soft": {"preset": 16, "note": 61},
    "elec_tick": {"preset": 15, "note": 90},
    "perc_bell": {"preset": 18, "note": 66},
    "perc_snap": {"preset": 3, "note": 60},
}
REVISION_SIX_OSC_INPUT = {
    "enabled": True,
    "listen_address": "0.0.0.0",
    "listen_port": 8000,
}

# One bass note needs to balance the energy of a typical three-note chord and
# the ear is less sensitive in the bass register. Native AMY measurements over
# representative Juno and DX7 patches put the median A-weighted difference at
# about 10.9 dB. Use a conservative +10.1 dB role correction while leaving
# patch-specific envelope/timbre differences to instrument_levels.
REVISION_NINE_ROLE_LEVELS = {
    "drums": 1.0,
    "bass": 3.2,
    "strum": 1.0,
    "chord": 1.0,
}
REVISION_TEN_OSC_DISCOVERY = {
    "advertise": True,
    "service_name": "LB Omnichord",
}


def _sample_pair(sample_map: object, name: str) -> tuple[int, int] | None:
    if not isinstance(sample_map, dict):
        return None
    sample = sample_map.get(name)
    if not isinstance(sample, dict):
        return None
    preset = sample.get("preset")
    note = sample.get("note")
    if not isinstance(preset, int) or not isinstance(note, int):
        return None
    return preset, note


def _infer_legacy_drum_kit(drums: JsonObject) -> str:
    sample_map = drums.get("sample_map")
    signatures = {
        "tiny": (("bd_haus", (1, 39)), ("drum_snare_hard", (2, 45))),
        "gamma9001": (
            ("bd_haus", (0, 60)),
            ("drum_snare_hard", (12, 45)),
        ),
    }
    matches = [
        kit
        for kit, expected in signatures.items()
        if all(_sample_pair(sample_map, name) == pair for name, pair in expected)
    ]
    if isinstance(sample_map, dict) and sample_map and all(
        isinstance(sample, dict) and sample.get("preset") == 258
        for sample in sample_map.values()
    ):
        matches.append("general_midi")
    if len(matches) != 1:
        raise ConfigMigrationError(
            "$.drums.kit",
            "cannot infer the legacy drum kit from sample_map",
        )
    return matches[0]


@dataclass(frozen=True, slots=True)
class ConfigMigrationResult:
    data: JsonObject
    source_revision: int
    target_revision: int
    changed_paths: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.source_revision != self.target_revision or bool(
            self.changed_paths
        )


class ConfigMigrationError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.detail = message
        super().__init__(f"{path}: {message}")


def _revision(data: JsonObject) -> int:
    value = data.get("config_revision", 0)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ConfigMigrationError(
            "$.config_revision",
            "must be a non-negative integer",
        )
    return value


def _revision_zero_to_one(data: JsonObject) -> tuple[str, ...]:
    changed: list[str] = []
    voices = data.get("voices")
    if isinstance(voices, dict) and voices.get("rhythm_chord") == 4:
        voices["rhythm_chord"] = 7
        changed.append("$.voices.rhythm_chord")
    data["config_revision"] = 1
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_one_to_two(data: JsonObject) -> tuple[str, ...]:
    changed: list[str] = []
    midi_input = data.get("midi_input")
    if isinstance(midi_input, dict) and midi_input.get("tech_profile") == "linux":
        # Revision 1 shipped Linux as a product default. Revision 2 makes the
        # common package portable; a deliberate diagnostic override can be
        # reapplied explicitly after migration.
        midi_input["tech_profile"] = "auto"
        changed.append("$.midi_input.tech_profile")
    data["config_revision"] = 2
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_two_to_three(data: JsonObject) -> tuple[str, ...]:
    rhythm = data.get("rhythm")
    if not isinstance(rhythm, dict):
        raise ConfigMigrationError(
            "$.rhythm",
            "must be an object before revision 2 can migrate",
        )
    rhythm["pattern_ranges"] = {
        "fills": {"start": 0, "count": 936},
        "chords": {"start": 936, "count": 64},
        "drum_bases": {"start": 1000, "count": 24},
    }
    data["config_revision"] = 3
    return ("$.rhythm.pattern_ranges", "$.config_revision")


def _revision_three_to_four(data: JsonObject) -> tuple[str, ...]:
    changed: list[str] = []
    for key, value in REVISION_FOUR_PATTERN_CAPACITIES.items():
        if key not in data:
            data[key] = value
            changed.append(f"$.{key}")
    midi_input = data.get("midi_input")
    if not isinstance(midi_input, dict):
        raise ConfigMigrationError(
            "$.midi_input",
            "must be an object before revision 3 can migrate",
        )
    if "tech_profile" not in midi_input:
        midi_input["tech_profile"] = "auto"
        changed.append("$.midi_input.tech_profile")
    if "alsa_raw_globs" not in midi_input:
        device_glob = midi_input.get("device_glob")
        if not isinstance(device_glob, str) or not device_glob:
            raise ConfigMigrationError(
                "$.midi_input.device_glob",
                "must be a non-empty string before revision 3 can migrate",
            )
        midi_input["alsa_raw_globs"] = [device_glob]
        changed.append("$.midi_input.alsa_raw_globs")
    if "oss_midi_globs" not in midi_input:
        midi_input["oss_midi_globs"] = list(REVISION_FOUR_OSS_MIDI_GLOBS)
        changed.append("$.midi_input.oss_midi_globs")
    drums = data.get("drums")
    if not isinstance(drums, dict):
        raise ConfigMigrationError(
            "$.drums",
            "must be an object before revision 3 can migrate",
        )
    if "kit" not in drums:
        drums["kit"] = _infer_legacy_drum_kit(drums)
        changed.append("$.drums.kit")
    data["config_revision"] = 4
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_four_to_five(data: JsonObject) -> tuple[str, ...]:
    drums = data.get("drums")
    if not isinstance(drums, dict):
        raise ConfigMigrationError(
            "$.drums",
            "must be an object before revision 4 can migrate",
        )
    changed: list[str] = []
    kit = drums.get("kit")
    if kit == "tiny":
        if drums.get("sample_map") != REVISION_FOUR_SHIPPED_TINY_MAP:
            raise ConfigMigrationError(
                "$.drums.sample_map",
                "custom Tiny mapping cannot be migrated automatically to the "
                "Gamma9001 release profile",
            )
        drums["kit"] = "gamma9001"
        drums["sample_map"] = copy.deepcopy(REVISION_FIVE_GAMMA9001_MAP)
        changed.extend(("$.drums.kit", "$.drums.sample_map"))
    data["config_revision"] = 5
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_five_to_six(data: JsonObject) -> tuple[str, ...]:
    changed: list[str] = []
    if "osc_input" not in data:
        data["osc_input"] = copy.deepcopy(REVISION_SIX_OSC_INPUT)
        changed.append("$.osc_input")
    data["config_revision"] = 6
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_six_to_seven(data: JsonObject) -> tuple[str, ...]:
    """Create the historical revision-7 sequencer-group intermediate form."""

    rhythm = data.get("rhythm")
    if not isinstance(rhythm, dict):
        raise ConfigMigrationError(
            "$.rhythm",
            "must be an object before revision 6 can migrate",
        )
    pattern_ranges = rhythm.pop("pattern_ranges", None)
    if not isinstance(pattern_ranges, dict):
        raise ConfigMigrationError(
            "$.rhythm.pattern_ranges",
            "must be an object before revision 6 can migrate",
        )
    group_ranges: JsonObject = {}
    for name in ("fills", "chords", "drum_bases"):
        item = pattern_ranges.get(name)
        if not isinstance(item, dict):
            raise ConfigMigrationError(
                f"$.rhythm.pattern_ranges.{name}",
                "must be an object before revision 6 can migrate",
            )
        group_ranges[name] = {
            "start": int(item["start"]) + 1,
            "count": int(item["count"]),
        }
    rhythm["group_ranges"] = group_ranges

    renamed = (
        ("amy_max_patterns", "amy_max_sequence_groups"),
        ("amy_max_pattern_tags", "amy_max_sequence_group_tags"),
        ("amy_max_pattern_instances", "amy_max_sequence_group_executions"),
    )
    changed = ["$.rhythm.pattern_ranges", "$.rhythm.group_ranges"]
    for old_name, new_name in renamed:
        if old_name not in data:
            raise ConfigMigrationError(
                f"$.{old_name}",
                "must be present before revision 6 can migrate",
            )
        value = data.pop(old_name)
        if new_name == "amy_max_sequence_group_executions":
            value = max(40, int(value))
        data[new_name] = value
        changed.extend((f"$.{old_name}", f"$.{new_name}"))
    data["config_revision"] = 7
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_seven_to_eight(data: JsonObject) -> tuple[str, ...]:
    """Move stored sequences into AMY's shared sequencer-tag namespace."""

    rhythm = data.get("rhythm")
    if not isinstance(rhythm, dict):
        raise ConfigMigrationError(
            "$.rhythm",
            "must be an object before revision 7 can migrate",
        )
    if (
        isinstance(rhythm.get("sequence_ranges"), dict)
        and all(
            name in data
            for name in (
                "amy_max_sequencer_tags",
                "amy_max_sequence_events",
                "amy_max_sequence_executions",
            )
        )
    ):
        # A current-format file whose revision marker was removed has already
        # passed through the older additive migrations. Discard only the
        # intermediate legacy fields those migrations may have reconstructed.
        changed: list[str] = []
        for name in ("group_ranges", "max_sequencer_tags"):
            if name in rhythm:
                rhythm.pop(name)
                changed.append(f"$.rhythm.{name}")
        for name in (
            "amy_max_sequence_groups",
            "amy_max_sequence_group_tags",
            "amy_max_sequence_group_executions",
        ):
            if name in data:
                data.pop(name)
                changed.append(f"$.{name}")
        data["config_revision"] = 8
        changed.append("$.config_revision")
        return tuple(changed)
    group_ranges = rhythm.pop("group_ranges", None)
    if not isinstance(group_ranges, dict):
        raise ConfigMigrationError(
            "$.rhythm.group_ranges",
            "must be an object before revision 7 can migrate",
        )
    root_tag_capacity = rhythm.pop("max_sequencer_tags", None)
    if not isinstance(root_tag_capacity, int) or root_tag_capacity < 1:
        raise ConfigMigrationError(
            "$.rhythm.max_sequencer_tags",
            "must be a positive integer before revision 7 can migrate",
        )

    sequence_ranges: JsonObject = {}
    for name in ("fills", "chords", "drum_bases"):
        item = group_ranges.get(name)
        if not isinstance(item, dict):
            raise ConfigMigrationError(
                f"$.rhythm.group_ranges.{name}",
                "must be an object before revision 7 can migrate",
            )
        sequence_ranges[name] = {
            "start": root_tag_capacity + int(item["start"]) - 1,
            "count": int(item["count"]),
        }
    rhythm["sequence_ranges"] = sequence_ranges

    required = (
        "amy_max_sequence_groups",
        "amy_max_sequence_group_tags",
        "amy_max_sequence_group_executions",
    )
    for name in required:
        if name not in data:
            raise ConfigMigrationError(
                f"$.{name}",
                "must be present before revision 7 can migrate",
            )
    group_capacity = int(data.pop("amy_max_sequence_groups"))
    data["amy_max_sequencer_tags"] = root_tag_capacity + group_capacity
    data["amy_max_sequence_events"] = int(
        data.pop("amy_max_sequence_group_tags")
    )
    data["amy_max_sequence_executions"] = int(
        data.pop("amy_max_sequence_group_executions")
    )
    data["config_revision"] = 8
    return (
        "$.rhythm.max_sequencer_tags",
        "$.rhythm.group_ranges",
        "$.rhythm.sequence_ranges",
        "$.amy_max_sequence_groups",
        "$.amy_max_sequence_group_tags",
        "$.amy_max_sequence_group_executions",
        "$.amy_max_sequencer_tags",
        "$.amy_max_sequence_events",
        "$.amy_max_sequence_executions",
        "$.config_revision",
    )


def _revision_eight_to_nine(data: JsonObject) -> tuple[str, ...]:
    """Add explicit role-level normalization without patch-specific policy."""

    changed: list[str] = []
    if "role_levels" not in data:
        data["role_levels"] = copy.deepcopy(REVISION_NINE_ROLE_LEVELS)
        changed.append("$.role_levels")
    data["config_revision"] = 9
    changed.append("$.config_revision")
    return tuple(changed)


def _revision_nine_to_ten(data: JsonObject) -> tuple[str, ...]:
    """Add opt-out DNS-SD discovery to an existing configured OSC endpoint."""

    changed: list[str] = []
    osc_input = data.get("osc_input")
    if isinstance(osc_input, dict):
        for key, value in REVISION_TEN_OSC_DISCOVERY.items():
            if key not in osc_input:
                osc_input[key] = copy.deepcopy(value)
                changed.append(f"$.osc_input.{key}")
    data["config_revision"] = 10
    changed.append("$.config_revision")
    return tuple(changed)


Migration = Callable[[JsonObject], tuple[str, ...]]


MIGRATIONS: dict[int, Migration] = {
    0: _revision_zero_to_one,
    1: _revision_one_to_two,
    2: _revision_two_to_three,
    3: _revision_three_to_four,
    4: _revision_four_to_five,
    5: _revision_five_to_six,
    6: _revision_six_to_seven,
    7: _revision_seven_to_eight,
    8: _revision_eight_to_nine,
    9: _revision_nine_to_ten,
}


def migrate_config_document(
    value: JsonObject,
    *,
    target_revision: int = CURRENT_CONFIG_REVISION,
) -> ConfigMigrationResult:
    """Apply every explicit revision transform to an isolated document."""

    data = copy.deepcopy(value)
    original_revision = _revision(data)
    if original_revision > target_revision:
        raise ConfigMigrationError(
            "$.config_revision",
            f"revision {original_revision} is newer than supported {target_revision}",
        )
    changed: list[str] = []
    revision = original_revision
    while revision < target_revision:
        migration = MIGRATIONS.get(revision)
        if migration is None:
            raise ConfigMigrationError(
                "$.config_revision",
                f"no migration from revision {revision} to {revision + 1}",
            )
        changed.extend(migration(data))
        next_revision = _revision(data)
        if next_revision != revision + 1:
            raise RuntimeError(
                "configuration migration did not advance exactly one revision"
            )
        revision = next_revision
    return ConfigMigrationResult(
        data=data,
        source_revision=original_revision,
        target_revision=revision,
        changed_paths=tuple(dict.fromkeys(changed)),
    )
