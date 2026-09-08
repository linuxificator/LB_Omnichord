#!/usr/bin/env python3
"""Measure real factory-preset bass patterns against three-note chord patterns.

The comparison uses each rhythm's default tempo, activity events and gates,
the shipped per-preset volumes, and production patch corrections. K-weighted
loudness accounts for reduced human sensitivity in the low register without a
hidden runtime bass multiplier. This is an offline audit tool, not app code.
"""

from __future__ import annotations

import argparse
import json
import math
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
BLOCK_SIZE = int(amy.AMY_BLOCK_SIZE)
BASS_NOTES = (36, 40, 43)
CHORD_NOTES = (60, 64, 67)
REPRESENTATIVE_RHYTHMS = (
    "pop_8",
    "funk",
    "jazz_swing",
    "waltz",
    "breakbeat",
    "drum_and_bass",
    "bossa",
    "seven_eight",
)


def _configure(item: dict[str, object], volume: float) -> None:
    amy.send_wire("S143360Z")
    for command in item["setup"]:
        if str(command).startswith("i2iV"):
            continue
        amy.send_wire(str(command))
    # build_plan records the patch-specific multiplier in each note level.
    # Divide out its 0.5 audit base before applying the factory-preset volume.
    reference_note = dict(item["notes"][1])
    multiplier = float(reference_note["level"]) / 0.5
    amy.send_wire(f"i2iV{volume * multiplier:.9g}Z")
    for _ in range(6):
        c_amy.render_to_list()


def _render_pattern(
    item: dict[str, object],
    *,
    role: str,
    events: list[dict[str, object]],
    tempo: float,
    length_beats: float,
    gate_beats: float,
    volume: float,
) -> np.ndarray:
    _configure(item, volume)
    seconds_per_beat = 60.0 / tempo
    scheduled: dict[int, list[str]] = {}
    for event in events:
        tick_seconds = float(event["time"]) * seconds_per_beat
        off_seconds = tick_seconds + gate_beats * seconds_per_beat
        on_block = round(tick_seconds * SAMPLE_RATE / BLOCK_SIZE)
        off_block = round(off_seconds * SAMPLE_RATE / BLOCK_SIZE)
        level = max(0.0, min(1.0, float(event.get("amp", 1.0))))
        if role == "bass":
            notes = (BASS_NOTES[int(event.get("degree", 0)) % len(BASS_NOTES)],)
        else:
            notes = CHORD_NOTES
        for note in notes:
            scheduled.setdefault(on_block, []).append(f"n{note}l{level:.9g}i2Z")
            scheduled.setdefault(off_block, []).append(f"n{note}l0i2Z")

    active_blocks = max(
        1,
        math.ceil(length_beats * seconds_per_beat * SAMPLE_RATE / BLOCK_SIZE),
    )
    tail_blocks = math.ceil(0.35 * SAMPLE_RATE / BLOCK_SIZE)
    output: list[np.ndarray] = []
    for block in range(active_blocks + tail_blocks):
        for command in scheduled.get(block, ()):
            amy.send_wire(command)
        output.append(np.asarray(c_amy.render_to_list(), dtype=np.float64))
    return np.concatenate(output).reshape((-1, 2)) / 32768.0


def build_report(
    rhythm_ids: tuple[str, ...] = REPRESENTATIVE_RHYTHMS,
) -> dict[str, object]:
    plan = {str(item["key"]): item for item in build_plan()}
    presets = FRONTEND / "instruments" / "default_presets"
    all_rhythms = json.loads(
        (FRONTEND / "music" / "rhythms.json").read_text(encoding="utf-8")
    )["rhythms"]
    by_id = {str(rhythm["id"]): rhythm for rhythm in all_rhythms}
    unknown = set(rhythm_ids) - set(by_id)
    if unknown:
        raise ValueError("unknown rhythm ids: " + ", ".join(sorted(unknown)))
    rhythm_data = [by_id[rhythm_id] for rhythm_id in rhythm_ids]
    config = json.loads(
        (FRONTEND / "config" / "amy_config.json").read_text(encoding="utf-8")
    )
    rhythm_config = config["rhythm"]
    preset_reports: dict[str, object] = {}
    report: dict[str, object] = {
        "measurement": {
            "bass_notes": BASS_NOTES,
            "chord_notes": CHORD_NOTES,
            "metric": "ITU-R BS.1770 K-weighted short-pattern loudness",
            "scope": (
                f"all 18 factory presets x {len(rhythm_ids)} representative "
                "default rhythm patterns"
            ),
            "rhythms": rhythm_ids,
        },
        "presets": preset_reports,
    }
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
            deltas: list[float] = []
            rhythms: dict[str, object] = {}
            for rhythm in rhythm_data:
                bass_level = int(rhythm["default_bass_activity"]) - 1
                chord_level = int(rhythm["default_chord_activity"]) - 1
                common = {
                    "tempo": float(rhythm["tempo"]["default"]),
                    "length_beats": float(rhythm["length_beats"]),
                }
                bass = _render_pattern(
                    plan[bass_key],
                    role="bass",
                    events=list(rhythm["bass_levels"][bass_level]),
                    gate_beats=float(rhythm_config["bass_gate_beats"]),
                    volume=float(preset["volumes"]["bass"]),
                    **common,
                )
                chord = _render_pattern(
                    plan[chord_key],
                    role="chord",
                    events=list(rhythm["chord_levels"][chord_level]),
                    gate_beats=float(rhythm_config["chord_gate_beats"]),
                    volume=float(preset["volumes"]["chord"]),
                    **common,
                )
                bass_metrics = audio_metrics(bass, SAMPLE_RATE)
                chord_metrics = audio_metrics(chord, SAMPLE_RATE)
                delta = round(
                    float(bass_metrics["loudness_lkfs"])
                    - float(chord_metrics["loudness_lkfs"]),
                    3,
                )
                deltas.append(delta)
                rhythms[str(rhythm["id"])] = {
                    "bass_loudness_lkfs": bass_metrics["loudness_lkfs"],
                    "chord_loudness_lkfs": chord_metrics["loudness_lkfs"],
                    "bass_minus_chord_lu": delta,
                }
            preset_reports[f"P{number}"] = {
                "bass_instrument": bass_key,
                "chord_instrument": chord_key,
                "bass_volume": preset["volumes"]["bass"],
                "chord_volume": preset["volumes"]["chord"],
                "median_bass_minus_chord_lu": round(float(np.median(deltas)), 3),
                "p10_bass_minus_chord_lu": round(float(np.percentile(deltas, 10)), 3),
                "p90_bass_minus_chord_lu": round(float(np.percentile(deltas, 90)), 3),
                "rhythms": rhythms,
            }
    finally:
        c_amy.stop()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--rhythms",
        nargs="*",
        default=list(REPRESENTATIVE_RHYTHMS),
        help="rhythm ids to audit (defaults to the cross-style representative set)",
    )
    args = parser.parse_args()
    args.report.write_text(
        json.dumps(build_report(tuple(args.rhythms)), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
