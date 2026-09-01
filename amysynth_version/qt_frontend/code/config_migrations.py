from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


CURRENT_CONFIG_REVISION = 2
JsonObject = dict[str, Any]


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


Migration = Callable[[JsonObject], tuple[str, ...]]


MIGRATIONS: dict[int, Migration] = {
    0: _revision_zero_to_one,
    1: _revision_one_to_two,
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
