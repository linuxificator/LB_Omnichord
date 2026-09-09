#!/usr/bin/env python3
"""Emit a real external 120 Hz touch sweep over the production strum."""

from __future__ import annotations

import argparse
import fcntl
import struct
import time
from dataclasses import dataclass
from pathlib import Path


EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0
BTN_TOOL_FINGER = 0x145
BTN_TOUCH = 0x14A
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39
ABS_CNT = 0x40
BUS_VIRTUAL = 0x06


def _ioc(direction: int, kind: int, number: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (kind << 8) | number


def _iow(kind: str, number: int, size: int = 4) -> int:
    return _ioc(1, ord(kind), number, size)


UI_DEV_CREATE = _ioc(0, ord("U"), 1, 0)
UI_DEV_DESTROY = _ioc(0, ord("U"), 2, 0)
UI_SET_EVBIT = _iow("U", 100)
UI_SET_KEYBIT = _iow("U", 101)
UI_SET_ABSBIT = _iow("U", 103)


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


def sweep_points(
    *,
    width: int,
    height: int,
    x_fraction: float,
    y_min_fraction: float,
    y_max_fraction: float,
    rate_hz: float,
    duration_seconds: float,
) -> list[Point]:
    if width <= 0 or height <= 0 or rate_hz <= 0 or duration_seconds <= 0:
        raise ValueError("screen dimensions, rate and duration must be positive")
    if not 0 <= y_min_fraction < y_max_fraction <= 1:
        raise ValueError("vertical fractions must satisfy 0 <= min < max <= 1")
    if not 0 <= x_fraction <= 1:
        raise ValueError("x fraction must be in [0, 1]")
    count = max(2, round(rate_hz * duration_seconds))
    x = round((width - 1) * x_fraction)
    y_min = (height - 1) * y_min_fraction
    y_span = (height - 1) * (y_max_fraction - y_min_fraction)
    result = []
    for index in range(count):
        phase = index / (count - 1)
        triangle = 1.0 - abs(2.0 * phase - 1.0)
        result.append(Point(x, round(y_min + y_span * triangle)))
    return result


def _event(kind: int, code: int, value: int) -> bytes:
    return struct.pack("@llHHi", 0, 0, kind, code, value)


class TouchDevice:
    def __init__(self, path: Path, width: int, height: int) -> None:
        self._file = path.open("wb", buffering=0)
        for event_type in (EV_SYN, EV_KEY, EV_ABS):
            fcntl.ioctl(self._file, UI_SET_EVBIT, event_type)
        for key in (BTN_TOUCH, BTN_TOOL_FINGER):
            fcntl.ioctl(self._file, UI_SET_KEYBIT, key)
        for axis in (
            ABS_X,
            ABS_Y,
            ABS_MT_SLOT,
            ABS_MT_POSITION_X,
            ABS_MT_POSITION_Y,
            ABS_MT_TRACKING_ID,
        ):
            fcntl.ioctl(self._file, UI_SET_ABSBIT, axis)

        maxima = [0] * ABS_CNT
        minima = [0] * ABS_CNT
        maxima[ABS_X] = maxima[ABS_MT_POSITION_X] = width - 1
        maxima[ABS_Y] = maxima[ABS_MT_POSITION_Y] = height - 1
        maxima[ABS_MT_SLOT] = 0
        maxima[ABS_MT_TRACKING_ID] = 65535
        name = b"LB Omnichord external strum benchmark"
        descriptor = struct.pack(
            "=80sHHHHI" + "i" * ABS_CNT * 4,
            name,
            BUS_VIRTUAL,
            0x4C42,
            0x0001,
            1,
            0,
            *maxima,
            *minima,
            *([0] * ABS_CNT),
            *([0] * ABS_CNT),
        )
        self._file.write(descriptor)
        fcntl.ioctl(self._file, UI_DEV_CREATE)
        time.sleep(0.5)

    def emit(self, events: tuple[tuple[int, int, int], ...]) -> None:
        self._file.write(
            b"".join(_event(kind, code, value) for kind, code, value in events)
            + _event(EV_SYN, SYN_REPORT, 0)
        )

    def close(self) -> None:
        if self._file.closed:
            return
        try:
            fcntl.ioctl(self._file, UI_DEV_DESTROY)
        finally:
            self._file.close()

    def __enter__(self) -> TouchDevice:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def run_sweep(device: TouchDevice, points: list[Point], rate_hz: float) -> None:
    period = 1.0 / rate_hz
    first = points[0]
    device.emit(
        (
            (EV_ABS, ABS_MT_SLOT, 0),
            (EV_ABS, ABS_MT_TRACKING_ID, 1),
            (EV_ABS, ABS_MT_POSITION_X, first.x),
            (EV_ABS, ABS_MT_POSITION_Y, first.y),
            (EV_ABS, ABS_X, first.x),
            (EV_ABS, ABS_Y, first.y),
            (EV_KEY, BTN_TOOL_FINGER, 1),
            (EV_KEY, BTN_TOUCH, 1),
        )
    )
    started = time.monotonic()
    try:
        for index, point in enumerate(points[1:], 1):
            due = started + index * period
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            device.emit(
                (
                    (EV_ABS, ABS_MT_POSITION_X, point.x),
                    (EV_ABS, ABS_MT_POSITION_Y, point.y),
                    (EV_ABS, ABS_X, point.x),
                    (EV_ABS, ABS_Y, point.y),
                )
            )
    finally:
        device.emit(
            (
                (EV_ABS, ABS_MT_SLOT, 0),
                (EV_ABS, ABS_MT_TRACKING_ID, -1),
                (EV_KEY, BTN_TOUCH, 0),
                (EV_KEY, BTN_TOOL_FINGER, 0),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=Path, default=Path("/dev/uinput"))
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--rate", type=float, default=120.0)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--x", type=float, default=0.94)
    parser.add_argument("--y-min", type=float, default=0.16)
    parser.add_argument("--y-max", type=float, default=0.84)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    points = sweep_points(
        width=args.width,
        height=args.height,
        x_fraction=args.x,
        y_min_fraction=args.y_min,
        y_max_fraction=args.y_max,
        rate_hz=args.rate,
        duration_seconds=args.duration,
    )
    if args.dry_run:
        print(f"points={len(points)} first={points[0]} middle={points[len(points)//2]} last={points[-1]}")
        return 0
    with TouchDevice(args.device, args.width, args.height) as device:
        run_sweep(device, points, args.rate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
