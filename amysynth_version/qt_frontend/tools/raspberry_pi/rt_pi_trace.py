#!/usr/bin/env python3
"""Trace and summarize Linux scheduler wake latency for one audio thread."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path


TRACE_ROOT = Path("/sys/kernel/tracing")
LINE = re.compile(
    r"\s(?P<time>\d+\.\d+):\s+sched_(?P<event>wakeup|switch):\s+(?P<body>.*)$"
)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile without samples")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def parse_trace(text: str, tid: int) -> dict[str, object]:
    wakes: list[float] = []
    wake_latency_ms: list[float] = []
    completion_ms: list[float] = []
    running_since: float | None = None
    for line in text.splitlines():
        match = LINE.search(line)
        if match is None:
            continue
        stamp = float(match.group("time"))
        body = match.group("body")
        if match.group("event") == "wakeup":
            pid_match = re.search(r"\bpid=(\d+)\b", body)
            if pid_match and int(pid_match.group(1)) == tid:
                wakes.append(stamp)
            continue
        previous = re.search(r"\bprev_pid=(\d+)\b", body)
        following = re.search(r"\bnext_pid=(\d+)\b", body)
        if following and int(following.group(1)) == tid:
            running_since = stamp
            if wakes:
                wake_latency_ms.append((stamp - wakes.pop(0)) * 1000)
        if previous and int(previous.group(1)) == tid and running_since is not None:
            completion_ms.append((stamp - running_since) * 1000)
            running_since = None

    def summary(values: list[float]) -> dict[str, float | int]:
        return {
            "samples": len(values),
            "median_ms": round(statistics.median(values), 6) if values else 0,
            "p99_ms": round(percentile(values, 0.99), 6) if values else 0,
            "max_ms": round(max(values), 6) if values else 0,
        }

    return {
        "tid": tid,
        "wake_to_run": summary(wake_latency_ms),
        "run_to_switch_out": summary(completion_ms),
        "unmatched_wakes": len(wakes),
    }


def _write(relative: str, value: str) -> None:
    (TRACE_ROOT / relative).write_text(value, encoding="ascii")


def capture(tid: int, seconds: float) -> str:
    _write("tracing_on", "0")
    _write("events/sched/sched_wakeup/enable", "0")
    _write("events/sched/sched_switch/enable", "0")
    _write("trace", "")
    _write("trace_clock", "mono_raw")
    _write("events/sched/sched_wakeup/filter", f"pid == {tid}")
    _write("events/sched/sched_switch/filter", f"prev_pid == {tid} || next_pid == {tid}")
    try:
        _write("events/sched/sched_wakeup/enable", "1")
        _write("events/sched/sched_switch/enable", "1")
        _write("tracing_on", "1")
        time.sleep(seconds)
    finally:
        _write("tracing_on", "0")
        _write("events/sched/sched_wakeup/enable", "0")
        _write("events/sched/sched_switch/enable", "0")
    return (TRACE_ROOT / "trace").read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tid", required=True, type=int)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    trace = capture(args.tid, args.seconds)
    if args.output:
        args.output.write_text(trace, encoding="utf-8")
    print(json.dumps(parse_trace(trace, args.tid), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
