from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    path: str
    sha256: str
    count_path: tuple[str, ...]
    expected_count: int
    schema: str
    process: str


def _object(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def load_provenance_manifest(path: Path) -> tuple[ProvenanceEntry, ...]:
    raw = _object(json.loads(Path(path).read_text(encoding="utf-8")), str(path))
    if raw.get("schema_version") != 1:
        raise ValueError("unsupported catalogue provenance manifest")
    entries = raw.get("catalogues")
    if not isinstance(entries, list) or not entries:
        raise ValueError("catalogue provenance manifest has no catalogues")
    result: list[ProvenanceEntry] = []
    for index, value in enumerate(entries):
        entry = _object(value, f"catalogues[{index}]")
        count_path = entry.get("count_path")
        if not isinstance(count_path, list) or not count_path:
            raise ValueError(f"catalogues[{index}].count_path must be a list")
        result.append(
            ProvenanceEntry(
                path=str(entry["path"]),
                sha256=str(entry["sha256"]),
                count_path=tuple(str(part) for part in count_path),
                expected_count=int(entry["expected_count"]),
                schema=str(entry["schema"]),
                process=str(entry["process"]),
            )
        )
    return tuple(result)


def verify_catalogue_provenance(
    root: Path,
    entries: Sequence[ProvenanceEntry],
) -> tuple[str, ...]:
    failures: list[str] = []
    for entry in entries:
        path = Path(root) / entry.path
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != entry.sha256:
            failures.append(f"{entry.path}: sha256 {digest} != {entry.sha256}")
        value: Any = json.loads(payload)
        for part in entry.count_path:
            if not isinstance(value, dict) or part not in value:
                failures.append(f"{entry.path}: missing count path {entry.count_path}")
                value = ()
                break
            value = value[part]
        try:
            count = len(value)
        except TypeError:
            failures.append(f"{entry.path}: count path is not sized")
        else:
            if count != entry.expected_count:
                failures.append(
                    f"{entry.path}: count {count} != {entry.expected_count}"
                )
    return tuple(failures)
