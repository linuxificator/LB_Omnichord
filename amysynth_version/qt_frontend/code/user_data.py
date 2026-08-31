from __future__ import annotations

import json
import shutil
from pathlib import Path


USER_ROOT = Path.home() / ".omnichord"
OMNI_PRESET_DIR = USER_ROOT / "omni_presets"
MIDI_PRESET_DIR = USER_ROOT / "midi_presets"
USER_CONFIG_DIR = USER_ROOT / "config"


def _migrate_amy_config(source: Path, target: Path) -> None:
    """Apply narrowly-scoped migrations while preserving user overrides."""
    try:
        shipped = json.loads(source.read_text(encoding="utf-8"))
        current = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # The authoritative loader will report an unreadable/invalid config.
        # Never replace such a file behind the user's back.
        return
    if not isinstance(shipped, dict) or not isinstance(current, dict):
        return

    shipped_revision = int(shipped.get("config_revision", 0))
    current_revision = int(current.get("config_revision", 0))
    if current_revision >= shipped_revision:
        return

    # Revision 1 raised the automatic chord pool for seven-note arpeggios.
    # Migrate only the former shipped default. Any other explicit value is a
    # user choice and is left for config_loader's capacity validation.
    if current_revision < 1 <= shipped_revision:
        voices = current.get("voices")
        shipped_voices = shipped.get("voices")
        if (
            isinstance(voices, dict)
            and isinstance(shipped_voices, dict)
            and voices.get("rhythm_chord") == 4
            and shipped_voices.get("rhythm_chord") == 7
        ):
            voices["rhythm_chord"] = 7

    current["config_revision"] = shipped_revision
    target.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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
            # Shipped JSON is application content, not a file-metadata backup.
            # Some valid private filesystems reject copied xattrs/timestamps.
            shutil.copyfile(source, target)
        if source.name == "amy_config.json":
            _migrate_amy_config(source, target)
    return USER_CONFIG_DIR
