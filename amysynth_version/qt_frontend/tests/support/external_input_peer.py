#!/usr/bin/env python3
"""Test-only external OSC/MIDI peer; never staged into application packages."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

from pythonosc.osc_message_builder import OscMessageBuilder


OSC_MESSAGES: tuple[tuple[str, bool | float], ...] = (
    ("/package-smoke/rotary", 0.25),
    ("/package-smoke/rotary", 0.75),
    ("/package-smoke/button", True),
    ("/package-smoke/button", False),
)
MIDI_BYTES = bytes(
    (
        0xB0,
        119,
        24,
        119,
        96,
        0x90,
        118,
        127,
        0x80,
        118,
        0,
        0xE0,
        0,
        64,
    )
)


def _osc_datagram(address: str, value: bool | float) -> bytes:
    builder = OscMessageBuilder(address=address)
    builder.add_arg(value)
    return builder.build().dgram


def _osc_endpoint(config_path: Path) -> tuple[str, int]:
    data: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    raw = data.get("osc_input")
    if not isinstance(raw, dict):
        raise ValueError("configuration has no osc_input object")
    if not bool(raw.get("enabled", False)):
        raise ValueError("configured OSC input is disabled")
    address = str(raw["listen_address"])
    port = int(raw["listen_port"])
    target = "127.0.0.1" if address == "0.0.0.0" else address
    return target, port


def send_osc(config_path: Path, duration: float, interval: float) -> int:
    target = _osc_endpoint(config_path)
    packets = tuple(_osc_datagram(address, value) for address, value in OSC_MESSAGES)
    deadline = time.monotonic() + max(0.1, float(duration))
    sent = 0
    print(
        json.dumps(
            {
                "kind": "osc-external-process-started",
                "pid": os.getpid(),
                "target": f"{target[0]}:{target[1]}",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while time.monotonic() < deadline:
            for packet in packets:
                udp.sendto(packet, target)
                sent += 1
            time.sleep(max(0.005, float(interval)))
    finally:
        udp.close()
    print(
        json.dumps(
            {
                "kind": "osc-external-process",
                "packets_sent": sent,
                "target": f"{target[0]}:{target[1]}",
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def print_osc_port(config_path: Path) -> int:
    print(_osc_endpoint(config_path)[1])
    return 0


def write_midi(output: str) -> int:
    if output == "-":
        sys.stdout.buffer.write(MIDI_BYTES)
        sys.stdout.buffer.flush()
    else:
        with Path(output).open("wb", buffering=0) as stream:
            stream.write(MIDI_BYTES)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    osc = subparsers.add_parser("osc")
    osc.add_argument("--config", type=Path, required=True)
    osc.add_argument("--duration", type=float, default=20.0)
    osc.add_argument("--interval", type=float, default=0.05)

    port = subparsers.add_parser("osc-port")
    port.add_argument("--config", type=Path, required=True)

    midi = subparsers.add_parser("midi")
    midi.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "osc":
        return send_osc(args.config, args.duration, args.interval)
    if args.command == "osc-port":
        return print_osc_port(args.config)
    if args.command == "midi":
        return write_midi(args.output)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
