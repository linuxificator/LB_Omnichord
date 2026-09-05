#!/usr/bin/env python3
"""Materialize the reviewed Gamma9001 drum-activity refresh into canonical runtime data.

Temporary handoff utility. Run from any working directory on the
feature/gamma9001-drum-pattern-refresh branch. After successful materialization,
validation and commit, remove this file and its .b64 payload.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

EXPECTED_JSON_SHA256 = "e7d3e14374d90a290fc19fa6f202c0776cccc299ce301b68fdc96af40877f0fc"
EXPECTED_RHYTHM_COUNT = 54
MAX_EVENTS = 56
MIN_FOUNDATION_EVENTS = 5
MIN_FOUNDATION_ROLES = 2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAYLOAD_PARTS = tuple(sorted(HERE.glob("drum_activity_timing.refresh.json.gz.b64.part*")))
if not PAYLOAD_PARTS:
    raise SystemExit("staged drum refresh payload parts are missing")
TARGET = ROOT / "qt_frontend" / "music" / "drums" / "drum_activity_timing.json"
MANIFEST = HERE / "canonical_drum_data_manifest.json"
PROVENANCE = ROOT / "qt_frontend" / "music" / "catalogue_provenance.json"


def decoded_bytes() -> bytes:
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in PAYLOAD_PARTS)
    data = gzip.decompress(base64.b64decode(encoded))
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_JSON_SHA256:
        raise SystemExit(
            f"decoded drum JSON SHA-256 {actual} != expected {EXPECTED_JSON_SHA256}"
        )
    return data


def validate(data: bytes) -> dict:
    doc = json.loads(data)
    rhythms = doc.get("rhythms")
    if not isinstance(rhythms, list) or len(rhythms) != EXPECTED_RHYTHM_COUNT:
        raise SystemExit("refresh must contain exactly 54 rhythms")
    if len({str(item["id"]) for item in rhythms}) != EXPECTED_RHYTHM_COUNT:
        raise SystemExit("rhythm IDs must be unique")

    for rhythm in rhythms:
        period = int(rhythm["period_ticks"])
        levels = rhythm["levels"]
        if len(levels) != 5:
            raise SystemExit(f'{rhythm["id"]} does not have five levels')
        previous: set[tuple[int, str]] = set()
        for expected_level, level in enumerate(levels, start=1):
            if int(level["level"]) != expected_level:
                raise SystemExit(f'{rhythm["id"]} levels are not 1..5')
            events = level["events"]
            if int(level["event_count"]) != len(events) or len(events) > MAX_EVENTS:
                raise SystemExit(f'{rhythm["id"]} level {expected_level} violates event capacity')
            current: set[tuple[int, str]] = set()
            for event in events:
                tick = int(event["tick"])
                velocity = int(event["velocity"])
                role = str(event["role"])
                if tick < 0 or tick >= period or tick % 2:
                    raise SystemExit(f'{rhythm["id"]} has invalid tick {tick}')
                if not 1 <= velocity <= 127:
                    raise SystemExit(f'{rhythm["id"]} has invalid velocity {velocity}')
                current.add((tick, role))
            if not previous <= current:
                raise SystemExit(f'{rhythm["id"]} activity levels are not cumulative')
            previous = current

        foundation = levels[0]["events"]
        if len(foundation) < MIN_FOUNDATION_EVENTS:
            raise SystemExit(f'{rhythm["id"]} foundation is too sparse')
        if len({str(event["role"]) for event in foundation}) < MIN_FOUNDATION_ROLES:
            raise SystemExit(f'{rhythm["id"]} foundation lacks orchestral identity')
    return doc


def update_hash_metadata() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["manifest_revision"] = max(2, int(manifest.get("manifest_revision", 1)) + 1)
    found = False
    for entry in manifest["files"]:
        if entry["name"] == "drum_activity_timing.json":
            entry["sha256"] = EXPECTED_JSON_SHA256
            found = True
            break
    if not found:
        raise SystemExit("canonical manifest has no drum_activity_timing.json entry")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    provenance["recorded"] = "2026-09-05"
    found = False
    for entry in provenance["catalogues"]:
        if entry["path"] == "music/drums/drum_activity_timing.json":
            entry["sha256"] = EXPECTED_JSON_SHA256
            entry["process"] = (
                "LB-authored 2026-09-05 genre-convention refresh; "
                "Gamma9001 is the musical reference while timing remains kit-independent"
            )
            found = True
            break
    if not found:
        raise SystemExit("catalogue provenance has no drum activity entry")
    PROVENANCE.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the staged payload without modifying the repository",
    )
    args = parser.parse_args()

    data = decoded_bytes()
    validate(data)
    if args.check:
        print(f"OK: {EXPECTED_RHYTHM_COUNT} rhythms, SHA-256 {EXPECTED_JSON_SHA256}")
        return

    TARGET.write_bytes(data)
    update_hash_metadata()
    print(f"Wrote {TARGET}")
    print(f"Updated {MANIFEST}")
    print(f"Updated {PROVENANCE}")
    print(f"SHA-256 {EXPECTED_JSON_SHA256}")


if __name__ == "__main__":
    main()
