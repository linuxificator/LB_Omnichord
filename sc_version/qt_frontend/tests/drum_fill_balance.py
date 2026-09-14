#!/usr/bin/env python3
"""Render every Gamma9001 fill against its production rhythm context.

This is an offline audit tool, not an application test hook.  It uses the
canonical timing/instrument catalogues and the same hit-level formula as the
production AMY transport, then compares each fill with the equally long
phrase-ending section it replaces at percussion-activity level 3.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))
sys.path.insert(0, str(FRONTEND / "tests"))

import amy  # type: ignore  # noqa: E402
import c_amy  # type: ignore  # noqa: E402

from audio_metrics import audio_metrics  # noqa: E402
from drum_patterns import DrumEvent, DrumPatternCatalog, load_drum_pattern_catalog  # noqa: E402


SAMPLE_RATE = int(amy.AMY_SAMPLE_RATE)
BLOCK_SIZE = int(amy.AMY_BLOCK_SIZE)
# The original measured-output limits plus the maximum intentional integration
# correction.  The integration contract below tests the direction explicitly;
# these remain broad transient/clipping guardrails rather than loudness targets.
MAX_ABSOLUTE_LOUDNESS_DELTA_LU = 8.25
MAX_PEAK_DELTA_DB = 7.5


def _rhythm_tempos() -> dict[str, float]:
    data = json.loads((FRONTEND / "music" / "rhythms.json").read_text())
    return {
        str(item["id"]): float(item["tempo"]["default"])
        for item in data["rhythms"]
    }


def _render_events(
    catalog: DrumPatternCatalog,
    *,
    rhythm_id: str,
    events: Iterable[DrumEvent],
    duration_ticks: int,
    tempo: float,
    fill: bool,
    fill_id: str | None,
    start_tick: int = 0,
    output_gain: float = 1.0,
) -> np.ndarray:
    config = json.loads((FRONTEND / "config" / "amy_config.json").read_text())
    drum_config = config["drums"]
    gain = float(drum_config["velocity_gain"])
    volume = float(json.loads((FRONTEND / "config" / "defaults.json").read_text())["volumes"]["percussion"])

    amy.send_wire("S143360Z")  # sequencer, oscillators and live-note state
    amy.send_wire("i0iv8in1if2Zv0w7i0Zi0iy0Z")
    amy.send_wire(f"i0iV{volume:.9g}Z")
    for _ in range(6):
        c_amy.render_to_list()

    seconds_per_tick = 60.0 / tempo / 96.0
    scheduled: dict[int, list[str]] = {}
    for event in events:
        relative_tick = int(event.tick) - start_tick
        if not 0 <= relative_tick < duration_ticks:
            continue
        sound = catalog.resolve(
            str(drum_config["kit"]),
            rhythm_id,
            event.role,
            fill=fill,
            fill_id=fill_id,
        )
        level = max(0.0, min(1.0, event.velocity / 127.0)) * gain
        if fill:
            level *= max(0.0, float(output_gain))
        preset = "" if sound.preset is None else f"p{sound.preset}"
        command = f"{preset}n{sound.note}l{level:.9g}i0Z"
        block = round(relative_tick * seconds_per_tick * SAMPLE_RATE / BLOCK_SIZE)
        scheduled.setdefault(block, []).append(command)

    active_blocks = max(
        1,
        math.ceil(duration_ticks * seconds_per_tick * SAMPLE_RATE / BLOCK_SIZE),
    )
    tail_blocks = math.ceil(0.25 * SAMPLE_RATE / BLOCK_SIZE)
    output: list[np.ndarray] = []
    for block in range(active_blocks + tail_blocks):
        for command in scheduled.get(block, ()):
            amy.send_wire(command)
        output.append(np.asarray(c_amy.render_to_list(), dtype=np.float64))
    return np.concatenate(output).reshape((-1, 2)) / 32768.0


def build_report() -> dict[str, object]:
    catalog = load_drum_pattern_catalog(FRONTEND / "music" / "drums")
    tempos = _rhythm_tempos()
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
        for rhythm in catalog.rhythms.values():
            tempo = tempos[rhythm.rhythm_id]
            activity = rhythm.levels[2]
            fills: dict[str, object] = {}
            for fill in rhythm.fills:
                start = max(0, rhythm.period_ticks - fill.duration_ticks)
                base = _render_events(
                    catalog,
                    rhythm_id=rhythm.rhythm_id,
                    events=activity,
                    duration_ticks=fill.duration_ticks,
                    tempo=tempo,
                    fill=False,
                    fill_id=None,
                    start_tick=start,
                )
                rendered_fill = _render_events(
                    catalog,
                    rhythm_id=rhythm.rhythm_id,
                    events=fill.events,
                    duration_ticks=fill.duration_ticks,
                    tempo=tempo,
                    fill=True,
                    fill_id=fill.fill_id,
                    output_gain=fill.output_gain,
                )
                base_metrics = audio_metrics(base, SAMPLE_RATE)
                fill_metrics = audio_metrics(rendered_fill, SAMPLE_RATE)
                integrated_hit_weight = sum(
                    event.velocity / 127.0 for event in fill.events
                )
                fills[fill.fill_id] = {
                    "duration_ticks": fill.duration_ticks,
                    "event_count": len(fill.events),
                    "output_gain": fill.output_gain,
                    "integrated_hit_weight": round(integrated_hit_weight, 9),
                    "levelled_hit_weight": round(
                        integrated_hit_weight * fill.output_gain,
                        9,
                    ),
                    "base": base_metrics,
                    "fill": fill_metrics,
                    "loudness_delta_lu": round(
                        float(fill_metrics["loudness_lkfs"])
                        - float(base_metrics["loudness_lkfs"]),
                        3,
                    ),
                    "peak_delta_db": round(
                        float(fill_metrics["peak_dbfs"])
                        - float(base_metrics["peak_dbfs"]),
                        3,
                    ),
                }
            report[rhythm.rhythm_id] = fills
    finally:
        c_amy.stop()
    return report


def validate_report(report: dict[str, object]) -> list[str]:
    """Return balance-contract violations without hiding musical variation."""

    issues: list[str] = []
    flattened: dict[str, dict[str, object]] = {}
    for rhythm_id, raw_fills in report.items():
        if not isinstance(raw_fills, dict):
            issues.append(f"{rhythm_id}: expected an object of fills")
            continue
        for fill_id, raw_metrics in raw_fills.items():
            if not isinstance(raw_metrics, dict):
                issues.append(f"{fill_id}: expected a metrics object")
                continue
            metrics = raw_metrics
            flattened[str(fill_id)] = metrics
            loudness_delta = float(metrics["loudness_delta_lu"])
            peak_delta = float(metrics["peak_delta_db"])
            clipped = int(dict(metrics["fill"])["clipped_samples"])
            if abs(loudness_delta) > MAX_ABSOLUTE_LOUDNESS_DELTA_LU:
                issues.append(
                    f"{fill_id}: loudness delta {loudness_delta:+.3f} LU exceeds "
                    f"+/-{MAX_ABSOLUTE_LOUDNESS_DELTA_LU:.2f} LU"
                )
            if peak_delta > MAX_PEAK_DELTA_DB:
                issues.append(
                    f"{fill_id}: peak delta {peak_delta:+.3f} dB exceeds "
                    f"+{MAX_PEAK_DELTA_DB:.2f} dB"
                )
            if clipped:
                issues.append(f"{fill_id}: rendered {clipped} clipped samples")

    # These reported regressions are useful sentinels in addition to the broad
    # catalogue limits. Funk F3 was conspicuously hot. Breakbeat and Garage
    # 2-step proved that equal mean loudness does not make short and dense fills
    # equally salient; their gains must now move in opposite directions.
    funk_f3 = flattened.get("drum_fill_0093_funk")
    if funk_f3 and (
        abs(float(funk_f3["loudness_delta_lu"])) > 3.0
        or float(funk_f3["peak_delta_db"]) > 2.0
    ):
        issues.append("Funk F3 no longer matches its measured balance contract")
    breakbeat_f1 = flattened.get("drum_fill_0146_breakbeat")
    breakbeat_f5 = flattened.get("drum_fill_0150_breakbeat")
    if breakbeat_f1 and breakbeat_f5:
        if not (
            float(breakbeat_f1["output_gain"]) > 0.72
            and float(breakbeat_f5["output_gain"]) < 0.72
        ):
            issues.append("Breakbeat F1/F5 integration correction is reversed")
    garage_f1 = flattened.get("drum_fill_0141_garage_2step")
    garage_f4 = flattened.get("drum_fill_0144_garage_2step")
    garage_f5 = flattened.get("drum_fill_0145_garage_2step")
    if garage_f1 and garage_f4 and garage_f5:
        if not (
            float(garage_f1["output_gain"])
            > float(garage_f4["output_gain"])
            > float(garage_f5["output_gain"])
        ):
            issues.append("Garage 2-step F1/F4/F5 integration order regressed")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the measured fill-balance contract is violated",
    )
    args = parser.parse_args()
    report = build_report()
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.check:
        issues = validate_report(report)
        if issues:
            print("\n".join(issues), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
