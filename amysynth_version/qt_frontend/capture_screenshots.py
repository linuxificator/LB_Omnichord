#!/usr/bin/env python3
"""Capture deterministic public OMNI and MIDI screenshots from the real UI."""

from __future__ import annotations

import argparse
import os
import pty
import select
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = FRONTEND_DIR / "screenshots"


def drain_serial_output(master_fd: int, stop: threading.Event) -> None:
    """Consume the frontend's pseudo-serial output until capture is done."""

    while not stop.is_set():
        try:
            readable, _, _ = select.select([master_fd], [], [], 0.05)
            if readable and not os.read(master_fd, 65536):
                return
        except (OSError, ValueError):
            return


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination directory (default: frontend screenshots directory).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    serial_port = os.ttyname(slave_fd)
    stop_drain = threading.Event()
    drain_thread = threading.Thread(
        target=drain_serial_output,
        args=(master_fd, stop_drain),
        name="screenshot-serial-drain",
        daemon=True,
    )
    drain_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="lb-omnichord-screenshots-") as home:
            env = os.environ.copy()
            env.update(
                {
                    "HOME": home,
                    "QT_QPA_PLATFORM": "offscreen",
                    "QT_QUICK_BACKEND": "software",
                    "QSG_INFO": "0",
                }
            )
            command = [
                sys.executable,
                str(FRONTEND_DIR / "code" / "main.py"),
                "--serial-port",
                serial_port,
                "--windowed",
                "--capture-screenshots-dir",
                str(output),
            ]
            return subprocess.run(command, env=env, check=False).returncode
    finally:
        stop_drain.set()
        drain_thread.join(timeout=1.0)
        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    raise SystemExit(main())
