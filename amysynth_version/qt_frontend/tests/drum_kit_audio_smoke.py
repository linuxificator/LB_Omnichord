#!/usr/bin/env python3
"""Render every distinct LB drum realization with a matching AMY build."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND / "code"))

import amy  # type: ignore  # noqa: E402
import c_amy  # type: ignore  # noqa: E402

from drum_patterns import DrumSound, load_drum_pattern_catalog  # noqa: E402


def sounds_for_kit(kit: str) -> list[DrumSound]:
    catalog = load_drum_pattern_catalog(FRONTEND / "music" / "drums")
    sounds: set[DrumSound] = set()
    for rhythm in catalog.rhythms.values():
        for level in rhythm.levels:
            for event in level:
                sounds.add(catalog.resolve(kit, rhythm.rhythm_id, event.role))
        for fill in rhythm.fills:
            for event in fill.events:
                sounds.add(
                    catalog.resolve(
                        kit,
                        rhythm.rhythm_id,
                        event.role,
                        fill=True,
                    )
                )
    return sorted(
        sounds,
        key=lambda sound: (
            sound.synth_patch or -1,
            sound.preset or -1,
            sound.note,
        ),
    )


def render_blocks(count: int) -> int:
    peak = 0
    for _ in range(count):
        block = c_amy.render_to_list()
        if block:
            peak = max(peak, max(abs(int(sample)) for sample in block))
    return peak


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "kit",
        choices=("tiny", "gamma9001", "general_midi"),
    )
    args = parser.parse_args()
    sounds = sounds_for_kit(args.kit)

    c_amy.live(
        default_synths=0,
        max_buses=11,
        max_oscs=336,
        max_sequencer_tags=1280,
        max_sequence_events=64,
        max_sequence_executions=40,
    )
    try:
        amy.send_wire("S12288Z")
        if args.kit == "general_midi":
            amy.send_wire("K258i0iy0Z")
        else:
            amy.send_wire("i0iv4in1Zv0w7i0Z")
        amy.send_wire("i0iV1Zy0V1Z")
        render_blocks(8)

        silent: list[DrumSound] = []
        for sound in sounds:
            prefix = "" if sound.preset is None else f"p{sound.preset}"
            amy.send_wire(f"{prefix}n{sound.note}l1i0Z")
            peak = render_blocks(32)
            amy.send_wire("l0i0Z")
            render_blocks(8)
            if peak == 0:
                silent.append(sound)
        if silent:
            raise AssertionError(
                f"{args.kit} produced silence for {len(silent)} mappings: "
                f"{silent}"
            )
        print(
            f"{args.kit} audio smoke passed: "
            f"{len(sounds)} distinct AMY realizations rendered non-silent"
        )
        return 0
    finally:
        c_amy.stop()


if __name__ == "__main__":
    raise SystemExit(main())
