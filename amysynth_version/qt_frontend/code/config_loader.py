from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CHORD_VOICE_CAPACITY = 7


def load_amy_config(path: Path) -> dict[str, Any]:
    """Load the one authoritative AMY frontend configuration file.

    Configuration used to be duplicated as a large DEFAULT_CONFIG literal in
    amy_serial.py.  That made a missing/partial JSON file silently resurrect an
    old copy of buses, patches and compatibility overrides.  The JSON file is
    now the source of truth: a missing file is an error and no hidden defaults
    are merged into it.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(
            f"AMY configuration file not found: {path}. "
            "The frontend no longer falls back to an embedded configuration."
        )

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")

    required = (
        "serial",
        "synth_ids",
        "voices",
        "default_synths",
        "drums",
        "rhythm",
        "performance",
        "buses",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(
            f"{path} is missing required AMY configuration sections: "
            + ", ".join(missing)
        )

    voices = data["voices"]
    if not isinstance(voices, dict):
        raise ValueError("voices must be a JSON object")
    for role in ("manual_chord", "rhythm_chord"):
        available = int(voices.get(role, 0))
        if available < CHORD_VOICE_CAPACITY:
            raise ValueError(
                f"voices.{role} must be at least {CHORD_VOICE_CAPACITY}; "
                "the chord catalogue and sequenced arpeggios contain up to "
                f"{CHORD_VOICE_CAPACITY} distinct notes"
            )

    # Keep the old transport implementation source-compatible while program
    # resolution moves out of its ROM-only patch map.  This map is derived at
    # load time, never stored as a second configuration source.
    legacy_patch_map: dict[str, int] = {
        **{f"juno_{patch:03d}": patch for patch in range(128)},
        **{f"dx7_{patch:03d}": patch for patch in range(128, 256)},
    }
    configured = data.get("synth_patches")
    if isinstance(configured, dict):
        # Transitional compatibility for old config files.  The shipped file
        # may remove this section once all external configs have migrated.
        legacy_patch_map.update(
            {str(key): int(value) for key, value in configured.items()}
        )
    data["synth_patches"] = legacy_patch_map

    programs = data.get("synth_programs", {})
    if not isinstance(programs, dict):
        raise ValueError("synth_programs must be a JSON object")

    return data
