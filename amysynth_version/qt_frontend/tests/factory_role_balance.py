#!/usr/bin/env python3
"""Measure factory-preset bass against its three-note chord companion.

The comparison deliberately uses the shipped per-preset volumes and the
production patch corrections.  K-weighted loudness accounts for reduced
human sensitivity in the low register without introducing a hidden runtime
bass multiplier.  This is an offline audit tool, not application code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))
sys.path.insert(0, str(FRONTEND / "tests"))

import amy  # type: ignore  # noqa: E402
import c_amy  # type: ignore  # noqa: E402

from audio_metrics import audio_metrics  # noqa: E402
from instrument_balance import build_plan  # noqa: E402


SAMPLE_RATE = int(amy.AMY_SAMPLE_RATE)
BASS_NOTE = 40
CHORD_NOTES = (60, 64, 67)


def _render(
    item: dict[str, object],
    *,
    notes: tuple[int, ...],
    volume: float,
    gate_seconds: float,
) -> np.ndarray:
    amy.send_wire("S143360Z")
    for command in item["setup"]:
        if str(command).startswith("i2iV"):
            continue
        amy.send_wire(str(command))
    # build_plan records the configured patch-specific multiplier in each
    # note level.  Divide out its 0.5 audit base before applying preset volume.
    reference_note = dict(item["notes"][1])
    multiplier = float(reference_note["level"]) / 0.5
    amy.send_wire(f"i2iV{volume * multiplier:.9g}Z")
    amy.render(0.08)
    for note in notes:
        amy.send_wire(f"n{note}l1i2Z")
    body = amy.render(gate_seconds)
    amy.send_wire("l0i2Z")
    tail = amy.render(0.35)
    return np.concatenate((body, tail), axis=0)


def build_report(*, gate_seconds: float = 1.0) -> dict[str, object]:
    plan = {str(item["key"]): item for item in build_plan()}
    presets = FRONTEND / "instruments" / "default_presets"
    report: dict[str, object] = {}
    c_amy.live(
        audio=False,
        default_synths=0,
        max_buses=11,
        max_oscs=336,
        max_sequencer_tags=1280,
        max_sequence_events=64,
        max_sequence_executions=40,
        max_reverb_rooms=2,
    )
    try:
        for number in range(1, 19):
            preset = json.loads(
                (presets / f"p{number}.json").read_text(encoding="utf-8")
            )
            bass_key = str(preset["synths"]["bass"]["selected"])
            chord_key = str(preset["synths"]["chord"]["selected"])
            bass = _render(
                plan[bass_key],
                notes=(BASS_NOTE,),
                volume=float(preset["volumes"]["bass"]),
                gate_seconds=gate_seconds,
            )
            chord = _render(
                plan[chord_key],
                notes=CHORD_NOTES,
                volume=float(preset["volumes"]["chord"]),
                gate_seconds=gate_seconds,
            )
            bass_metrics = audio_metrics(bass, SAMPLE_RATE)
            chord_metrics = audio_metrics(chord, SAMPLE_RATE)
            report[f"P{number}"] = {
                "bass": {
                    "instrument": bass_key,
                    "note": BASS_NOTE,
                    "preset_volume": preset["volumes"]["bass"],
                    **bass_metrics,
                },
                "chord": {
                    "instrument": chord_key,
                    "notes": CHORD_NOTES,
                    "preset_volume": preset["volumes"]["chord"],
                    **chord_metrics,
                },
                "bass_minus_chord_lu": round(
                    float(bass_metrics["loudness_lkfs"])
                    - float(chord_metrics["loudness_lkfs"]),
                    3,
                ),
            }
    finally:
        c_amy.stop()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--gate-seconds", type=float, default=1.0)
    args = parser.parse_args()
    args.report.write_text(
        json.dumps(
            build_report(gate_seconds=max(0.05, args.gate_seconds)),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
