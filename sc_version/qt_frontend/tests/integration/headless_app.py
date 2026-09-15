from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle


ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "code"
TEST_SUPPORT_DIR = ROOT / "tests" / "support"
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(TEST_SUPPORT_DIR))

import main as omnichord  # noqa: E402
import app_core  # noqa: E402
from application_composition import (  # noqa: E402
    compose_application_graph,
    load_application_resources,
)
from backend_control_surface import BackendControlSurface  # noqa: E402
from control_server import TestControlServer  # noqa: E402
from performance_qml_adapter import PerformanceQmlAdapter  # noqa: E402


class GuiControlSurface(BackendControlSurface):
    """Test-only visual probe around the production QML root window."""

    def __init__(self, backend: Any, window: QQuickWindow) -> None:
        super().__init__(backend)
        self._window = window

    def setGuiScreen(self, midi_screen: bool) -> None:
        self._window.setProperty("midiScreen", bool(midi_screen))

    def captureGui(self, raw_path: str) -> dict[str, int | str]:
        path = Path(raw_path).resolve()
        image = self._window.grabWindow()
        if image.isNull() or image.width() < 640 or image.height() < 360:
            raise RuntimeError("QML root did not produce a non-trivial frame")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(path), "PNG"):
            raise RuntimeError(f"could not save QML frame to {path}")
        colours = {
            image.pixel(x, y)
            for x in range(0, image.width(), max(1, image.width() // 16))
            for y in range(0, image.height(), max(1, image.height() // 9))
        }
        if len(colours) < 8:
            raise RuntimeError("QML frame is blank or visually degenerate")
        return {
            "path": str(path),
            "width": image.width(),
            "height": image.height(),
            "sampled_colours": len(colours),
        }


def load_qml(
    resources: Any,
    backend: Any,
    gui_path: Path,
) -> tuple[QQmlApplicationEngine, QQuickWindow]:
    """Load the production QML scene with the production context contract."""

    engine = QQmlApplicationEngine()
    context = engine.rootContext()
    context.setContextProperty("backend", backend)
    context.setContextProperty("midiBackend", backend.midiPlayer)
    context.setContextProperty("performanceBackend", PerformanceQmlAdapter(backend))
    context.setContextProperty("sliderTrace", False)
    context.setContextProperty("startupWarningMessages", [])
    context.setContextProperty("chordNames", [item.label for item in resources.chords])
    context.setContextProperty("noteDefinitions", list(app_core.NOTE_DEFINITIONS))
    context.setContextProperty("octaveNames", list(app_core.OCTAVE_NAMES))
    context.setContextProperty("synthNames", [item.label for item in resources.synths])
    context.setContextProperty("rhythmNames", [item.label for item in resources.rhythms])
    context.setContextProperty("tuningModeNames", list(app_core.TUNING_MODE_NAMES))
    context.setContextProperty("headerTitleText", resources.title["text"])
    context.setContextProperty("headerTitleHeight", resources.title["height"])
    context.setContextProperty("headerTitleFont", resources.title["font"])
    context.setContextProperty("startFullscreen", False)
    context.setContextProperty("scaleToFit", True)
    engine.load(QUrl.fromLocalFile(str(gui_path / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("production QML scene failed to load")
    window = engine.rootObjects()[0]
    if not isinstance(window, QQuickWindow):
        raise RuntimeError("production QML root is not a QQuickWindow")
    return engine, window


def main() -> int:
    args = omnichord.parse_arguments()
    dependencies = omnichord.production_dependencies()
    resources = load_application_resources(
        dependencies,
        user_config_dir=omnichord.CONFIG_DIR,
    )

    with_qml = os.environ.get("OMNICHORD_TEST_LOAD_QML") == "1"
    if with_qml:
        QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv) if with_qml else QCoreApplication(sys.argv)
    app.setApplicationName("LB Omnichord headless integration test")
    signal.signal(signal.SIGINT, lambda _signum, _frame: app.quit())
    signal.signal(signal.SIGTERM, lambda _signum, _frame: app.quit())
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda _signum, _frame: app.quit())
    graph = compose_application_graph(
        args,
        dependencies,
        resources,
        user_config_dir=omnichord.CONFIG_DIR,
    )
    client = graph.client
    backend = graph.backend

    port = int(os.environ.get("OMNICHORD_TEST_API_PORT", "18765"))
    engine: QQmlApplicationEngine | None = None
    if with_qml:
        engine, window = load_qml(resources, backend, dependencies.paths.gui)
        surface: BackendControlSurface = GuiControlSurface(backend, window)
        print("TEST_QML_READY=1", file=sys.stderr, flush=True)
    else:
        surface = BackendControlSurface(backend)
    test_server = TestControlServer(surface, port)
    print(f"TEST_API_PORT={test_server.port}", file=sys.stderr, flush=True)

    backend.send_initial_state()
    try:
        return app.exec()
    finally:
        test_server.close()
        if engine is not None:
            del engine
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
