#!/usr/bin/env python3
"""Test-only receiver process for portable MIDI and OSC contracts."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any


FRONTEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FRONTEND / "code"))

from midi_input import (  # noqa: E402
    MidiByteStreamParser,
    MidiByteStreamState,
    MidiInputEvent,
    OrderedMidiInputEmitter,
)
from osc_input import OscInputEvent, decode_osc_packet  # noqa: E402


def _event_record(event: MidiInputEvent | OscInputEvent) -> dict[str, Any]:
    if isinstance(event, MidiInputEvent):
        return {
            "sequence": event.sequence,
            "kind": event.kind,
            "technology": event.technology,
            "channel": event.channel,
            "data": event.data,
            "value": event.value,
            "is_on": event.is_on,
        }
    return {
        "sequence": event.sequence,
        "address": event.address,
        "argument": event.argument,
        "value": event.value,
        "value_type": event.value_type,
    }


def receive_midi() -> int:
    events: list[MidiInputEvent] = []
    emitter = OrderedMidiInputEmitter(events.append)
    parser = MidiByteStreamParser(emitter, "external-process-stream")
    state = MidiByteStreamState()
    parser.feed(sys.stdin.buffer.read(), state)
    emitter.close()
    print(
        json.dumps(
            {
                "kind": "portable-midi-parser-receiver",
                "pid": os.getpid(),
                "events": [_event_record(event) for event in events],
            },
            sort_keys=True,
        )
    )
    return 0


def receive_osc(port: int, ready: Path, timeout: float) -> int:
    events: list[OscInputEvent] = []
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("0.0.0.0", int(port)))
    receiver.settimeout(max(0.1, float(timeout)))
    ready.write_text(f"{os.getpid()}\n", encoding="ascii")
    deadline = time.monotonic() + max(0.1, float(timeout))
    observed = False
    sequence = 0
    try:
        while time.monotonic() < deadline:
            packet, _peer = receiver.recvfrom(65535)
            for address, argument, value, value_type in decode_osc_packet(packet):
                sequence += 1
                events.append(
                    OscInputEvent(
                        sequence, address, argument, value, value_type
                    )
                )
            identities = {(item.address, item.value_type) for item in events}
            if (
                ("/package-smoke/rotary", "continuous") in identities
                and ("/package-smoke/button", "button") in identities
            ):
                observed = True
                break
    except TimeoutError:
        pass
    finally:
        receiver.close()
    print(
        json.dumps(
            {
                "kind": "portable-osc-receiver",
                "pid": os.getpid(),
                "complete": observed,
                "events": [_event_record(event) for event in events],
            },
            sort_keys=True,
        )
    )
    return 0 if observed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("midi")
    osc = subparsers.add_parser("osc")
    osc.add_argument("--port", type=int, required=True)
    osc.add_argument("--ready", type=Path, required=True)
    osc.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "midi":
        return receive_midi()
    if args.command == "osc":
        return receive_osc(args.port, args.ready, args.timeout)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
