#!/usr/bin/env python3
"""Send a deterministic AMY sequencer workload over a serial connection.

The two modes schedule the same note events.  ``root`` uses AMY's historical
root tick scheduler, while ``stored`` groups those events into stored sequence
definitions and starts one execution per definition.  This makes source-level
ESP32-P4 comparisons repeatable without starting the Omnichord UI.
"""

from __future__ import annotations

import argparse
import time

import serial


PERIOD = 384
PATTERN_COUNT = 15


def _event_wires(index: int) -> tuple[tuple[int, str], ...]:
    synth = 1 + index % 4
    note = 36 + (index % 12)
    offset = (index % 4) * 24
    return (
        (offset, f"n{note}l0.45i{synth}Z"),
        (offset + 18, f"n{note}l0i{synth}Z"),
        (offset + 192, f"n{note + 12}l0.38i{synth}Z"),
        (offset + 210, f"n{note + 12}l0i{synth}Z"),
    )


def workload(mode: str, shared_reverb: bool = False) -> list[str]:
    commands = [
        "zY0Z",  # stop transport while replacing the workload
        "S274432Z",  # RESET_SEQUENCER | RESET_ALL_OSCS | RESET_SYNTHS
        "K143i1iv8iy1Z",
        "K28i2iv8iy2Z",
        "K4i3iv8iy3Z",
        "K4i4iv8iy3Z",
        "j120Z",
        "S16384Z",  # align timebase before executions capture start ticks
    ]
    if shared_reverb:
        commands.extend((
            "hR0,0.25,0.5,0.5,3000Z",
            "hR1,0.25,0.5,0.5,3000Z",
            "y1hS0,1Z",
            "y2hS0,1Z",
            "y3hS1,1Z",
        ))
    for index in range(PATTERN_COUNT):
        tag = 100 + index
        if mode == "stored":
            commands.append(f"HR{tag}Z")
        for tick, wire in _event_wires(index):
            if mode == "stored":
                commands.append(f"H{tick},{PERIOD},{tag}{wire}")
            else:
                commands.append(f"H{tick},{PERIOD}{wire}")
        if mode == "stored":
            commands.append(f"HC{tag},1,0Z")
    commands.append("zY1Z")
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("root", "stored"))
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=1_000_000)
    parser.add_argument("--command-gap-ms", type=float, default=1.0)
    parser.add_argument("--shared-reverb", action="store_true")
    parser.add_argument(
        "--load-samples",
        type=int,
        default=0,
        help="request this many deferred P4 load snapshots after setup",
    )
    parser.add_argument("--sample-interval", type=float, default=2.0)
    args = parser.parse_args()

    messages = workload(args.mode, shared_reverb=args.shared_reverb)
    with serial.Serial(args.port, args.baud, timeout=0.1) as connection:
        for message in messages:
            connection.write((message + "\n").encode("ascii"))
            connection.flush()
            if args.command_gap_ms:
                time.sleep(args.command_gap_ms / 1000.0)
        for _ in range(args.load_samples):
            time.sleep(args.sample_interval)
            connection.write(b"?loadZ\n")
            connection.flush()
    reverb = "+shared-reverb" if args.shared_reverb else ""
    print(f"sent {len(messages)} AMY messages ({args.mode}{reverb}) to {args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
