#!/usr/bin/env python3
"""Frozen AppImage entry point for the two-process Linux application."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CONFIG_PATH = APP_ROOT / "config" / "amy_config.json"


def configure_frontend_asset_paths(core: object) -> None:
    core.FRONTEND_DIR = APP_ROOT
    core.GUI_DIR = APP_ROOT / "gui"
    core.CONFIG_DIR = APP_ROOT / "config"
    core.INSTRUMENT_DIR = APP_ROOT / "instruments"
    core.MUSIC_DIR = APP_ROOT / "music"


def import_frontend() -> object:
    # Configure app_core before importing main: main imports midi_player, whose
    # factory-preset constant is deliberately resolved once at import time.
    import app_core

    configure_frontend_asset_paths(app_core)
    import main

    return main


def run_service(arguments: list[str]) -> int:
    import local_amy_service

    sys.argv = [sys.argv[0], *arguments]
    return int(local_amy_service.main())


def self_test() -> int:
    import amy  # noqa: F401
    import c_amy  # noqa: F401
    import PySide6  # noqa: F401
    import local_amy_service  # noqa: F401
    import_frontend()

    required = (
        APP_ROOT / "licence.txt",
        CONFIG_PATH,
        APP_ROOT / "config" / "defaults.json",
        APP_ROOT / "gui" / "Main.qml",
        APP_ROOT / "instruments" / "synths.json",
        APP_ROOT / "music" / "rhythms.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("missing packaged assets: " + ", ".join(missing))
    print("LB Omnichord AppImage self-test passed")
    return 0


def socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    base = Path(runtime_dir) if runtime_dir else Path(tempfile.gettempdir())
    return base / f"lb-omnichord-{os.getuid()}-{os.getpid()}.sock"


def run_frontend(arguments: list[str]) -> int:
    socket = socket_path()
    service = subprocess.Popen(
        [
            sys.executable,
            "--amy-service",
            "--socket",
            str(socket),
            "--config",
            str(CONFIG_PATH),
        ]
    )

    def stop_service() -> None:
        if service.poll() is None:
            service.terminate()
            try:
                service.wait(timeout=3)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait(timeout=2)

    def forward_signal(signum: int, _frame: object) -> None:
        stop_service()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, forward_signal)
    signal.signal(signal.SIGTERM, forward_signal)

    try:
        deadline = time.monotonic() + 8.0
        while not socket.is_socket():
            return_code = service.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"AMY service stopped during startup with status {return_code}"
                )
            if time.monotonic() >= deadline:
                raise RuntimeError("AMY service did not create its socket in time")
            time.sleep(0.05)

        main = import_frontend()

        sys.argv = [sys.argv[0], "--amy-socket", str(socket), *arguments]
        return int(main._core.main())
    finally:
        stop_service()
        socket.unlink(missing_ok=True)


def main_entry() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "--amy-service":
        return run_service(arguments[1:])
    if arguments in (["--package-self-test"], ["--appimage-self-test"]):
        return self_test()
    return run_frontend(arguments)


if __name__ == "__main__":
    raise SystemExit(main_entry())
