from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "instruments" / "synths.json"


def synths() -> list[dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    result = data.get("synths", [])
    if not isinstance(result, list):
        raise AssertionError("synths.json does not contain a synth list")
    return result


def synth_index(label: str) -> int:
    wanted = label.casefold()
    entries = synths()
    for index, entry in enumerate(entries):
        if str(entry.get("label", "")).casefold() == wanted:
            return index
    for index, entry in enumerate(entries):
        if wanted in str(entry.get("label", "")).casefold():
            return index
    raise AssertionError(f"instrument label not found: {label!r}")


def entry_for_index(index: int) -> dict[str, Any]:
    entries = synths()
    return entries[int(index)]


def patch_for_index(index: int) -> int:
    return int(entry_for_index(index)["patch"])


def control_default(index: int, key: str) -> float:
    for control in entry_for_index(index).get("controls", []):
        if str(control.get("key")) == key:
            return float(control["default"])
    raise AssertionError(f"control {key!r} absent from synth index {index}")
