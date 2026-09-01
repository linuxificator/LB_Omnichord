from __future__ import annotations

from pathlib import Path

from config_migrations import CURRENT_CONFIG_REVISION, migrate_config_document
from json_store import JsonStore
from resolved_config import ConfigIssue, ConfigValidationError, resolve_amy_config_data


USER_ROOT = Path.home() / ".omnichord"
OMNI_PRESET_DIR = USER_ROOT / "omni_presets"
MIDI_PRESET_DIR = USER_ROOT / "midi_presets"
USER_CONFIG_DIR = USER_ROOT / "config"


def _migrate_amy_config(source: Path, target: Path) -> None:
    """Validate an explicit migration before atomically persisting it."""

    shipped = JsonStore(source).read()
    if not isinstance(shipped, dict):
        raise ConfigValidationError(
            [ConfigIssue("$", "shipped config must contain a JSON object")]
        )
    shipped_migration = migrate_config_document(shipped)
    if shipped_migration.source_revision != CURRENT_CONFIG_REVISION:
        raise ConfigValidationError(
            [
                ConfigIssue(
                    "$.config_revision",
                    "shipped config must declare the current revision",
                )
            ]
        )
    shipped_resolved = resolve_amy_config_data(
        shipped,
        source_path=source,
        source_kind="shipped",
    )
    if shipped_resolved.revision != CURRENT_CONFIG_REVISION:
        raise ConfigValidationError(
            [
                ConfigIssue(
                    "$.config_revision",
                    "shipped configuration did not resolve to the current revision",
                )
            ]
        )

    store = JsonStore(target)
    current = store.read()
    if not isinstance(current, dict):
        raise ConfigValidationError(
            [ConfigIssue("$", "must contain a JSON object")]
        )
    migration = migrate_config_document(current)
    resolve_amy_config_data(
        migration.data,
        source_path=target,
        source_kind="user",
    )
    if migration.changed:
        store.write(migration.data)


def migrate_user_layout() -> None:
    """Move pre-layout user files into their dedicated directories once."""
    USER_ROOT.mkdir(parents=True, exist_ok=True)
    OMNI_PRESET_DIR.mkdir(parents=True, exist_ok=True)
    MIDI_PRESET_DIR.mkdir(parents=True, exist_ok=True)

    for path in USER_ROOT.glob("p*.json"):
        if path.stem[1:].isdigit():
            target = OMNI_PRESET_DIR / path.name
            if not target.exists():
                path.replace(target)
    old_last = USER_ROOT / "last_preset.json"
    new_last = OMNI_PRESET_DIR / old_last.name
    if old_last.is_file() and not new_last.exists():
        old_last.replace(new_last)

    old_midi = USER_ROOT / "midi"
    if old_midi.is_dir():
        for path in old_midi.iterdir():
            target = MIDI_PRESET_DIR / path.name
            if path.is_file() and not target.exists():
                path.replace(target)
        try:
            old_midi.rmdir()
        except OSError:
            pass


def ensure_user_configs(shipped_config_dir: Path) -> Path:
    """Seed editable startup configs and return their authoritative directory."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for source in Path(shipped_config_dir).glob("*.json"):
        target = USER_CONFIG_DIR / source.name
        if not target.exists():
            JsonStore(target).write(JsonStore(source).read())
        if source.name == "amy_config.json":
            _migrate_amy_config(source, target)
    return USER_CONFIG_DIR
