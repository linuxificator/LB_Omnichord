from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from frontend_config import FrontendConfig, load_frontend_config
from json_store import JsonStore
from release_identity import release_user_root


USER_ROOT = release_user_root()
OMNI_PRESET_DIR = USER_ROOT / "omni_presets"
MIDI_PRESET_DIR = USER_ROOT / "midi_presets"
USER_CONFIG_DIR = USER_ROOT / "config"


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
            JsonStore(target).write(shipped)
        if source.name == "frontend.json":
            loader(target)
    return destination
