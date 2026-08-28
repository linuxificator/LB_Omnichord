#!/usr/bin/env python3
"""Capture deterministic public OMNI and MIDI screenshots from the real UI."""

from __future__ import annotations

import argparse
import os
import pty
import subprocess
import sys
import tempfile
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = FRONTEND_DIR / "screenshots"


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
        os.close(master_fd)
        os.close(slave_fd)


if __name__ == "__main__":
    raise SystemExit(main())
