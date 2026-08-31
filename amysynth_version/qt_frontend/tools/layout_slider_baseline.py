#!/usr/bin/env python3
"""Baseline for LB LabeledSlider inside a Main.qml-like viewport.

This keeps AMY, MIDI and the backend out of the process, but adds the two
layout features that the real app wraps around every control:

- an outer `Flickable`;
- a scaled `contentArea` with `transformOrigin: Item.TopLeft`.

If `simple_slider_baseline.py` and `custom_slider_baseline.py` both work but
this one fails, the regression is in pointer handling through the app viewport.
If all three work, the remaining suspect is runtime state feedback from the
full backend.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle


ROOT = Path(__file__).resolve().parents[1]
QML_FILE = ROOT / "tools" / "layout_slider_baseline.qml"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Main-layout-like LB LabeledSlider baseline app.",
    )
    platform = parser.add_mutually_exclusive_group()
    platform.add_argument(
        "--x11",
        action="store_true",
        help="force QT_QPA_PLATFORM=xcb before creating the Qt app",
    )
    platform.add_argument(
        "--wayland",
        action="store_true",
        help="force QT_QPA_PLATFORM=wayland before creating the Qt app",
    )
    parser.add_argument(
        "--software-renderer",
        action="store_true",
        help="force QT_QUICK_BACKEND=software before creating the Qt app",
    )
    return parser.parse_args(argv)


def configure_environment(args: argparse.Namespace) -> None:
    if args.x11:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif args.wayland:
        os.environ["QT_QPA_PLATFORM"] = "wayland"

    if args.software_renderer:
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ.pop("QSG_RHI_BACKEND", None)

    os.environ.setdefault("QSG_INFO", "1")


def print_diagnostics(label: str) -> None:
    print(label, file=sys.stderr, flush=True)
    for key in (
        "XDG_SESSION_TYPE",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "QT_QPA_PLATFORM",
        "QT_QUICK_BACKEND",
        "QSG_RHI_BACKEND",
        "QSG_INFO",
    ):
        print(
            f"  {key}: {os.environ.get(key, '<unset>')}",
            file=sys.stderr,
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    configure_environment(args)
    print_diagnostics("Layout slider baseline environment:")

    QQuickStyle.setStyle("Basic")

    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("LB Omnichord layout slider baseline")

    def quit_from_signal(signum: int, _frame: object) -> None:
        print(
            f"Received signal {signum}; quitting Qt event loop.",
            file=sys.stderr,
            flush=True,
        )
        app.quit()

    signal.signal(signal.SIGINT, quit_from_signal)
    signal.signal(signal.SIGTERM, quit_from_signal)
    signal.signal(signal.SIGQUIT, quit_from_signal)
    signal_timer = QTimer()
    signal_timer.setInterval(200)
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start()

    print(
        f"  Qt QPA platform after app creation: {QGuiApplication.platformName()}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"  Loading QML: {QML_FILE}",
        file=sys.stderr,
        flush=True,
    )

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT / "gui"))
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    roots = engine.rootObjects()
    print(f"  Root objects: {len(roots)}", file=sys.stderr, flush=True)
    if not roots:
        return 1

    window = roots[0]
    window.setProperty("visible", True)
    show = getattr(window, "show", None)
    if callable(show):
        show()
    raise_ = getattr(window, "raise_", None)
    if callable(raise_):
        raise_()
    request_activate = getattr(window, "requestActivate", None)
    if callable(request_activate):
        request_activate()
    print(
        f"  Window visible property: {window.property('visible')}",
        file=sys.stderr,
        flush=True,
    )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
