from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


CURRENT_CONFIG_REVISION = 4
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


Migration = Callable[[JsonObject], tuple[str, ...]]


MIGRATIONS: dict[int, Migration] = {
    0: _revision_zero_to_one,
    1: _revision_one_to_two,
    2: _revision_two_to_three,
    3: _revision_three_to_four,
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
