from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path

from frontend_config import FrontendConfig, load_frontend_config
from json_store import JsonStore


USER_ROOT = Path.home() / ".omnichord"
OMNI_PRESET_DIR = USER_ROOT / "omni_presets"
MIDI_PRESET_DIR = USER_ROOT / "midi_presets"
USER_CONFIG_DIR = USER_ROOT / "config"


def _legacy_frontend_config(
    shipped: dict[str, object],
    *,
    user_config_dir: Path,
) -> dict[str, object]:
    """Import engine-neutral settings from the preceding edition's config."""

    legacy_path = user_config_dir / "amy_config.json"
    legacy = JsonStore(legacy_path).read() if legacy_path.is_file() else None
    result = copy.deepcopy(shipped)
    if not isinstance(legacy, dict):
        return result
    for name in ("midi_input", "osc_input"):
        if isinstance(legacy.get(name), dict):
            result[name] = copy.deepcopy(legacy[name])
    # Program identifiers belong to their engine. Program selections migrate
    # through the explicit preset alias map, never through frontend config.
    midi = legacy.get("midi_player")
    if isinstance(midi, dict) and isinstance(midi.get("voices_per_synth"), int):
        result["midi"] = {"voices_per_row": midi["voices_per_synth"]}
    rhythm = legacy.get("rhythm")
    if isinstance(rhythm, dict):
        destination = copy.deepcopy(result["rhythm"])
        if isinstance(destination, dict):
            for old_name, new_name in (
                ("chord_gate_beats", "chord_gate_beats"),
                ("bass_gate_beats", "bass_gate_beats"),
                ("max_rhythm_chord_notes", "max_chord_notes"),
            ):
                if old_name in rhythm:
                    destination[new_name] = rhythm[old_name]
            result["rhythm"] = destination
    performance = legacy.get("performance")
    if isinstance(performance, dict) and "strum_tail_ms" in performance:
        result["performance"] = {"strum_tail_ms": performance["strum_tail_ms"]}
    buses = legacy.get("buses")
    if isinstance(buses, dict):
        result["logical_buses"] = copy.deepcopy(buses)
    return result


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


def ensure_user_configs(
    shipped_config_dir: Path,
    *,
    user_config_dir: Path | None = None,
    frontend_config_loader: Callable[[Path], FrontendConfig] | None = None,
) -> Path:
    """Seed editable startup configs and return their authoritative directory."""
    destination = USER_CONFIG_DIR if user_config_dir is None else Path(user_config_dir)
    loader = frontend_config_loader or load_frontend_config
    destination.mkdir(parents=True, exist_ok=True)
    for source in Path(shipped_config_dir).glob("*.json"):
        target = destination / source.name
        if not target.exists():
            shipped = JsonStore(source).read()
            if source.name == "frontend.json" and isinstance(shipped, dict):
                shipped = _legacy_frontend_config(
                    shipped,
                    user_config_dir=destination,
                )
            JsonStore(target).write(shipped)
        if source.name == "frontend.json":
            loader(target)
    return destination
