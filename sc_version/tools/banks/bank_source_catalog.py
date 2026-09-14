#!/usr/bin/env python3
"""Validate pinned sample-bank sources and inventory local installations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


AUDIO_SUFFIXES = {".wav", ".aif", ".aiff", ".flac"}
_SHA = re.compile(r"[0-9a-f]{40}")


def load_source_catalog(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_revision") != 1:
        raise ValueError(f"{path} is not a supported bank source catalog")
    git_banks = raw.get("git_banks")
    web_banks = raw.get("web_banks")
    if not isinstance(git_banks, list) or not isinstance(web_banks, list):
        raise ValueError(f"{path} must contain git_banks and web_banks lists")
    ids: set[str] = set()
    for bank in (*git_banks, *web_banks):
        if not isinstance(bank, dict) or not str(bank.get("id", "")):
            raise ValueError(f"{path} contains an invalid bank record")
        bank_id = str(bank["id"])
        if bank_id in ids:
            raise ValueError(f"{path} contains duplicate bank {bank_id}")
        ids.add(bank_id)
    for bank in git_banks:
        commit = str(bank.get("commit", ""))
        repository = str(bank.get("repository", ""))
        if _SHA.fullmatch(commit) is None:
            raise ValueError(f"bank {bank['id']} needs a full lowercase commit")
        if not repository.startswith("https://github.com/"):
            raise ValueError(f"bank {bank['id']} needs an HTTPS GitHub repository")
        bank["source_archive_url"] = f"{repository}/archive/{commit}.zip"
    return raw


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_lfs_pointer(path: Path) -> bool:
    if path.stat().st_size > 1024:
        return False
    prefix = path.read_bytes()[:128]
    return prefix.startswith(b"version https://git-lfs.github.com/spec/v1")


def inventory_bank(bank: dict[str, Any], root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    if not resolved.is_dir():
        raise ValueError(f"bank root is missing: {resolved}")
    files = sorted(
        path
        for path in resolved.rglob("*")
        if path.is_file() and path.suffix.casefold() in AUDIO_SUFFIXES
    )
    records = []
    for path in files:
        if _is_lfs_pointer(path):
            raise ValueError(f"Git LFS pointer is not sample audio: {path}")
        records.append(
            {
                "relative_path": path.relative_to(resolved).as_posix(),
                "source_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema_revision": 1,
        "bank_id": str(bank["id"]),
        "repository": str(bank["repository"]),
        "commit": str(bank["commit"]),
        "license": str(bank["license"]),
        "audio_file_count": len(records),
        "source_bytes": sum(int(item["source_bytes"]) for item in records),
        "files": records,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--bank-id")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    catalog = load_source_catalog(arguments.catalog)
    if arguments.bank_id is None:
        print(json.dumps(catalog, indent=2, sort_keys=True))
        return 0
    if arguments.root is None or arguments.output is None:
        parser.error("--bank-id requires --root and --output")
    bank = next(
        (
            item
            for item in catalog["git_banks"]
            if item["id"] == arguments.bank_id
        ),
        None,
    )
    if bank is None:
        raise ValueError(f"unknown Git bank {arguments.bank_id}")
    write_json(arguments.output, inventory_bank(bank, arguments.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
