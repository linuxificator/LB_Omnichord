#!/usr/bin/env python3
"""Minimal baseline for LB Omnichord's custom LabeledSlider.

Use this after `simple_slider_baseline.py` works.  It keeps the same
Python/PySide6/QML stack, but replaces the plain Qt Quick Slider with the
repository's `gui/LabeledSlider.qml` component.  It still avoids the real
backend, AMY, MIDI routing, `Main.qml`, scaling layout and release packaging.
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
QML_FILE = ROOT / "tools" / "custom_slider_baseline.qml"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal LB LabeledSlider baseline app.",
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
    print_diagnostics("Custom slider baseline environment:")

    QQuickStyle.setStyle("Basic")

    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("LB Omnichord custom slider baseline")

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
