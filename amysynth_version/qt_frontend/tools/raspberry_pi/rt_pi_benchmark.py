#!/usr/bin/env python3
"""External-process workload replay and scheduler evidence for Raspberry Pi."""

from __future__ import annotations

import argparse
import json
import re
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


LOG_LINE = re.compile(
    r"^(?P<stamp>\S+)\s+(?P<kind>TX-(?:HIGH|LOW))\s+(?P<wire>\S+)\s*$"
)


@dataclass(frozen=True, slots=True)
class WireEvent:
    offset_seconds: float
    priority: str
    wire: str


@dataclass(frozen=True, slots=True)
class ThreadSample:
    tid: int
    name: str
    cpu_percent: float
    run_delay_ms: float
    timeslices: int


def parse_interrupts(text: str) -> dict[str, tuple[list[int], str]]:
    lines = text.splitlines()
    if not lines:
        return {}
    cpu_count = len(re.findall(r"\bCPU\d+\b", lines[0]))
    result: dict[str, tuple[list[int], str]] = {}
    for line in lines[1:]:
        match = re.match(r"^\s*([^:]+):\s+(.*)$", line)
        if match is None:
            continue
        fields = match.group(2).split()
        try:
            counts = [int(value) for value in fields[:cpu_count]]
        except (ValueError, IndexError):
            continue
        result[match.group(1).strip()] = (counts, " ".join(fields[cpu_count:]))
    return result


def sample_interrupts(seconds: float) -> list[dict[str, object]]:
    before = parse_interrupts(Path("/proc/interrupts").read_text(encoding="utf-8"))
    time.sleep(seconds)
    after = parse_interrupts(Path("/proc/interrupts").read_text(encoding="utf-8"))
    result = []
    for irq, (later, description) in after.items():
        if irq not in before:
            continue
        earlier = before[irq][0]
        delta = [right - left for left, right in zip(earlier, later)]
        if sum(delta):
            result.append({"irq": irq, "delta": delta, "description": description})
    return sorted(result, key=lambda item: -sum(item["delta"]))


def parse_wire_log(path: Path, session: int = -1) -> list[WireEvent]:
    sessions: list[list[tuple[datetime, str, str]]] = []
    current: list[tuple[datetime, str, str]] | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if " SESSION " in line:
            current = []
            sessions.append(current)
            continue
        match = LOG_LINE.match(line)
        if match is None or current is None:
            continue
        current.append(
            (
                datetime.fromisoformat(match.group("stamp")),
                match.group("kind"),
                match.group("wire"),
            )
        )
    if not sessions:
        raise ValueError(f"no SESSION marker found in {path}")
    selected = sessions[session]
    if not selected:
        raise ValueError(f"selected session {session} contains no wire commands")
    origin = selected[0][0]
    return [
        WireEvent((stamp - origin).total_seconds(), kind, wire)
        for stamp, kind, wire in selected
    ]


def connect_wire_socket(path: Path) -> socket.socket:
    errors: list[OSError] = []
    for kind in (socket.SOCK_SEQPACKET, socket.SOCK_STREAM):
        candidate = socket.socket(socket.AF_UNIX, kind)
        try:
            candidate.connect(str(path))
            return candidate
        except OSError as exc:
            errors.append(exc)
            candidate.close()
    raise ConnectionError(f"cannot connect to {path}: {errors}")


def replay(events: list[WireEvent], path: Path, speed: float) -> None:
    if speed <= 0:
        raise ValueError("speed must be positive")
    connection = connect_wire_socket(path)
    started = time.monotonic()
    try:
        for event in events:
            due = started + event.offset_seconds / speed
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            connection.sendall(event.wire.encode("ascii"))
    finally:
        connection.close()


def _schedstat(pid: int) -> dict[int, tuple[int, int, int, str]]:
    result: dict[int, tuple[int, int, int, str]] = {}
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            run_ns, delay_ns, timeslices = map(
                int, (task / "schedstat").read_text(encoding="ascii").split()
            )
            name = (task / "comm").read_text(encoding="utf-8").strip()
        except (FileNotFoundError, ProcessLookupError):
            continue
        result[int(task.name)] = (run_ns, delay_ns, timeslices, name)
    return result


def sample_threads(pid: int, seconds: float) -> list[ThreadSample]:
    before = _schedstat(pid)
    started = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - started
    after = _schedstat(pid)
    result = []
    for tid, (run_ns, delay_ns, timeslices, name) in before.items():
        if tid not in after:
            continue
        later_run, later_delay, later_slices, _ = after[tid]
        result.append(
            ThreadSample(
                tid=tid,
                name=name,
                cpu_percent=round((later_run - run_ns) / 1e9 / elapsed * 100, 3),
                run_delay_ms=round((later_delay - delay_ns) / 1e6, 3),
                timeslices=later_slices - timeslices,
            )
        )
    return sorted(result, key=lambda item: (-item.cpu_percent, item.tid))


def select_audio_thread(samples: list[ThreadSample], process_id: int) -> ThreadSample:
    candidates = [sample for sample in samples if sample.tid != process_id]
    if not candidates:
        raise ValueError("no active non-main audio-thread candidate found")
    selected = max(candidates, key=lambda sample: sample.cpu_percent)
    if selected.cpu_percent <= 0:
        raise ValueError("no active non-main audio-thread candidate found")
    return selected


def synthetic_commands(profile: str, count: int) -> list[str]:
    if count < 0:
        raise ValueError("count cannot be negative")
    base = [
        "hR0,0.7,0.75,0.5Z",
        "hR1,0.7,0.75,0.5Z",
        "y0h0Z",
        "y0hS0,1Z",
        "y4h0Z",
        "y4hS1,1Z",
    ]
    if profile in {"sine", "filtered-saw"}:
        if count > 336:
            raise ValueError("configured release limit is 336 oscillators")
        for index in range(count):
            frequency = 82.4069 * 2 ** ((index % 48) / 12)
            bus = 0 if index % 2 == 0 else 4
            body = "w0" if profile == "sine" else "w2F1800R0.7G4"
            base.append(
                f"v{index}{body}f{frequency:.5f}y{bus}Q0.5l0.00035Z"
            )
        return base
    if profile == "dx7":
        if count > 42:
            raise ValueError("patch 129 needs eight oscs; 42 voices fill 336 slots")
        first = min(count, 32)
        second = max(0, count - first)
        base.extend((f"K129i0iv{first}Z", "i0iV0.003Z", "i0iy0Z"))
        if second:
            base.extend((f"K129i1iv{second}Z", "i1iV0.003Z", "i1iy4Z"))
        for note in range(first):
            base.append(f"n{36 + note % 48}l1i0Z")
        for note in range(second):
            base.append(f"n{36 + note % 48}l1i1Z")
        return base
    raise ValueError(f"unknown synthetic profile: {profile}")


def send_commands(commands: list[str], path: Path) -> None:
    connection = connect_wire_socket(path)
    try:
        for command in commands:
            connection.sendall(command.encode("ascii"))
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--log", type=Path, required=True)
    replay_parser.add_argument("--socket", type=Path, required=True)
    replay_parser.add_argument("--session", type=int, default=-1)
    replay_parser.add_argument("--speed", type=float, default=1.0)
    sample_parser = sub.add_parser("sample-threads")
    sample_parser.add_argument("--pid", type=int, required=True)
    sample_parser.add_argument("--seconds", type=float, default=5.0)
    irq_parser = sub.add_parser("sample-irqs")
    irq_parser.add_argument("--seconds", type=float, default=5.0)
    synth = sub.add_parser("synthetic")
    synth.add_argument("--socket", type=Path, required=True)
    synth.add_argument("--profile", choices=("sine", "filtered-saw", "dx7"), required=True)
    synth.add_argument("--count", type=int, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "replay":
        events = parse_wire_log(args.log, args.session)
        print(json.dumps({"events": len(events), "duration_seconds": events[-1].offset_seconds}))
        replay(events, args.socket, args.speed)
        return 0
    if args.command == "sample-threads":
        samples = sample_threads(args.pid, args.seconds)
        print(json.dumps([asdict(item) for item in samples], indent=2))
        print(json.dumps({"audio_candidate": asdict(select_audio_thread(samples, args.pid))}))
        return 0
    if args.command == "sample-irqs":
        print(json.dumps(sample_interrupts(args.seconds), indent=2))
        return 0
    if args.command == "synthetic":
        commands = synthetic_commands(args.profile, args.count)
        send_commands(commands, args.socket)
        print(json.dumps({"commands": len(commands), "profile": args.profile, "count": args.count}))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
