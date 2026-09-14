#!/usr/bin/env python3
"""Capture deterministic public OMNI and MIDI screenshots from the real UI."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = FRONTEND_DIR / "screenshots"
FAKE_SC = FRONTEND_DIR / "tests" / "support" / "fake_supercollider_service.py"
SC_CONFIG = FRONTEND_DIR / "config" / "supercollider.json"


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


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

    with tempfile.TemporaryDirectory(prefix="lb-omnichord-screenshots-") as home:
        temporary = Path(home)
        port = free_udp_port()
        runtime = json.loads(SC_CONFIG.read_text(encoding="utf-8"))
        runtime["language"]["port"] = port
        runtime_path = temporary / "supercollider.json"
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        engine_ready = temporary / "engine.ready"
        engine = subprocess.Popen(
            [
                sys.executable,
                str(FAKE_SC),
                "--port",
                str(port),
                "--log",
                str(temporary / "engine.jsonl"),
                "--ready-file",
                str(engine_ready),
            ]
        )
        try:
            deadline = time.monotonic() + 3.0
            while not engine_ready.exists() and time.monotonic() < deadline:
                if engine.poll() is not None:
                    return engine.returncode or 1
                time.sleep(0.01)
            if not engine_ready.exists():
                return 1
            env = os.environ.copy()
            env.update(
                {
                    "HOME": home,
                    "OMNICHORD_SC_CONFIG": str(runtime_path),
                    "QT_QPA_PLATFORM": "offscreen",
                    "QT_QUICK_BACKEND": "software",
                    "QSG_INFO": "0",
                }
            )
            command = [
                sys.executable,
                str(FRONTEND_DIR / "code" / "main.py"),
                "--windowed",
                "--capture-screenshots-dir",
                str(output),
            ]
            return subprocess.run(command, env=env, check=False).returncode
        finally:
            if engine.poll() is None:
                engine.terminate()
            try:
                engine.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
