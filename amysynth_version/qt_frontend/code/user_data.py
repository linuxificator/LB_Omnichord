from __future__ import annotations

import json
import shutil
from pathlib import Path


USER_ROOT = Path.home() / ".omnichord"
OMNI_PRESET_DIR = USER_ROOT / "omni_presets"
MIDI_PRESET_DIR = USER_ROOT / "midi_presets"
USER_CONFIG_DIR = USER_ROOT / "config"

_REVISION_1_TINY_SAMPLE_MAP = {
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

    # Revision 2 changes only the shipped drum-kit default for the dedicated
    # Gamma9001 release. Preserve every explicit kit choice; migrate precisely
    # the former shipped default so an existing installation actually adopts
    # the new bank instead of retaining its seeded revision-1 configuration.
    if current_revision < 2 <= shipped_revision:
        drums = current.get("drums")
        shipped_drums = shipped.get("drums")
        if (
            isinstance(drums, dict)
            and isinstance(shipped_drums, dict)
            and drums.get("kit") == "tiny"
            and shipped_drums.get("kit") == "gamma9001"
        ):
            drums["kit"] = "gamma9001"
        if isinstance(drums, dict) and isinstance(shipped_drums, dict):
            sample_map = drums.get("sample_map")
            shipped_sample_map = shipped_drums.get("sample_map")
            if isinstance(sample_map, dict) and isinstance(shipped_sample_map, dict):
                for name, old_hit in _REVISION_1_TINY_SAMPLE_MAP.items():
                    if sample_map.get(name) == old_hit and name in shipped_sample_map:
                        sample_map[name] = shipped_sample_map[name]

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
