#!/usr/bin/env python3
"""Build the reviewed SCLOrk playback-gain profile from fixed-pitch NRT reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--report",
        action="append",
        default=[],
        metavar="MIDI_NOTE=PATH",
        help="fixed-pitch NRT report (repeat for each audit note)",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-rms", type=float, default=0.05)
    parser.add_argument("--peak-ceiling", type=float, default=0.65)
    parser.add_argument("--max-gain", type=float, default=16.0)
    parser.add_argument("--max-raw-peak", type=float, default=64.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))["programs"]
    reports: dict[int, dict[str, dict[str, object]]] = {}
    for value in args.report:
        note_text, separator, path_text = value.partition("=")
        if not separator:
            raise ValueError(f"invalid --report {value!r}; expected MIDI_NOTE=PATH")
        note = int(note_text)
        entries = json.loads(Path(path_text).read_text(encoding="utf-8"))["programs"]
        reports[note] = {str(item["program_id"]): item for item in entries}
    if len(reports) < 2:
        raise ValueError("at least two fixed-pitch reports are required")

    programs: dict[str, dict[str, float]] = {}
    excluded: dict[str, dict[str, str]] = {}
    for program in catalog:
        if not program["pitch_support"] or program["category"] == "drums":
            continue
        program_id = str(program["program_id"])
        measurements = [report[program_id] for report in reports.values()]
        rms = median(float(item["rms"]) for item in measurements)
        peak = max(float(item["peak"]) for item in measurements)
        if (
            not math.isfinite(rms)
            or rms <= 0
            or not math.isfinite(peak)
            or peak <= 0
            or peak > args.max_raw_peak
        ):
            excluded[program_id] = {
                "reason": "non-finite or unstable raw output in the fixed-pitch audit"
            }
            continue
        gain = min(
            args.target_rms / rms,
            args.peak_ceiling / peak,
            args.max_gain,
        )
        programs[program_id] = {"gain": round(gain, 6)}

    document = {
        "schema_revision": 1,
        "method": {
            "midi_notes": sorted(reports),
            "target_rms": args.target_rms,
            "peak_ceiling": args.peak_ceiling,
            "max_gain": args.max_gain,
            "max_raw_peak": args.max_raw_peak,
        },
        "programs": dict(sorted(programs.items())),
        "excluded": dict(sorted(excluded.items())),
    }
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
