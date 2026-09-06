from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QObject, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"


def quick_descendants(item: QQuickItem) -> list[QQuickItem]:
    descendants: list[QQuickItem] = []
    for child in item.childItems():
        descendants.append(child)
        descendants.extend(quick_descendants(child))
    return descendants


class MigraineRenderBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    def create_window(self, source: bytes) -> tuple[QQmlEngine, QQmlComponent, QObject]:
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        component.setData(
            source,
            QUrl.fromLocalFile(str(GUI / "MigraineRenderBudgetTest.qml")),
        )
        window = component.create()
        self.assertIsNotNone(
            window,
            "\n".join(error.toString() for error in component.errors()),
        )
        assert window is not None
        QCoreApplication.processEvents()
        self.assertTrue(QTest.qWaitForWindowExposed(window))
        return engine, component, window

    @staticmethod
    def dispose(engine: QQmlEngine, component: QQmlComponent, window: QObject) -> None:
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        QCoreApplication.processEvents()

    def test_effect_has_a_bounded_cached_scene_graph_surface(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Window
import "."

Window {
    width: 160
    height: 160
    visible: true

    Migraine {
        objectName: "migraine"
        width: 96
        height: 96
        active: true
    }
}
""",
        )
        migraine = window.findChild(QObject, "migraine")
        cached_edge = window.findChild(QObject, "migraineCachedEdge")
        self.assertIsInstance(migraine, QQuickItem)
        self.assertIsNotNone(cached_edge)
        assert isinstance(migraine, QQuickItem)

        descendants = quick_descendants(migraine)
        class_names = [item.metaObject().className() for item in descendants]
        self.assertLessEqual(len(descendants), 12)
        self.assertEqual(
            sum("QQuickShape" in name for name in class_names),
            3,
        )
        self.assertFalse(any("Particle" in name for name in class_names))
        self.assertFalse(any("Emitter" in name for name in class_names))
        self.dispose(engine, component, window)

    def test_pointer_bursts_do_not_rebuild_geometry_per_input_event(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Window
import "."

Window {
    id: window
    width: 160
    height: 160
    visible: true
    property int inputUpdates: 0
    property int morphUpdates: 0
    property int synchronousMorphUpdates: -1

    Migraine {
        id: migraine
        objectName: "migraine"
        width: 96
        height: 96
        onMorphPhaseChanged: window.morphUpdates += 1
    }

    Component.onCompleted: {
        migraine.beginAt(48, 48)
        for (let index = 0; index < 120; ++index) {
            migraine.moveTo(
                48 + (index % 12),
                48 + ((index * 7) % 19)
            )
            window.inputUpdates += 1
        }
        window.synchronousMorphUpdates = window.morphUpdates
    }
}
""",
        )
        self.assertEqual(int(window.property("inputUpdates")), 120)
        self.assertEqual(int(window.property("synchronousMorphUpdates")), 0)
        self.assertEqual(int(window.property("morphUpdates")), 0)

        # macOS' offscreen event dispatcher can defer a QML Timer past a
        # single short qWait even though its declared interval is unchanged.
        # Poll for delivery without weakening the actual contract: all 120
        # inputs must still coalesce into exactly one geometry update.
        for _attempt in range(50):
            QTest.qWait(10)
            if int(window.property("morphUpdates")) >= 1:
                break
        self.assertEqual(int(window.property("morphUpdates")), 1)

        migraine = window.findChild(QObject, "migraine")
        self.assertIsNotNone(migraine)
        assert migraine is not None
        self.assertEqual(int(migraine.property("morphInterval")), 34)
        self.assertAlmostEqual(float(migraine.property("targetCenterX")), 59.0)
        self.assertAlmostEqual(float(migraine.property("targetCenterY")), 64.0)
        self.dispose(engine, component, window)

    def test_cached_effect_remains_hollow_and_chromatic(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Window
import "."

Window {
    id: window
    width: 160
    height: 160
    visible: true
    color: "#031a34"

    Migraine {
        id: migraine
        width: 96
        height: 96
        Component.onCompleted: migraine.beginAt(80, 80)
    }
}
""",
        )
        QTest.qWait(140)
        screen = window.screen()
        self.assertIsNotNone(screen)
        image: QImage = screen.grabWindow(window.winId()).toImage()
        self.assertFalse(image.isNull())

        background = QColor("#031a34")
        center = image.pixelColor(80, 80)
        self.assertLessEqual(abs(center.red() - background.red()), 4)
        self.assertLessEqual(abs(center.green() - background.green()), 4)
        self.assertLessEqual(abs(center.blue() - background.blue()), 4)

        chromatic_pixels = 0
        for x in range(30, 131):
            for y in range(30, 131):
                color = image.pixelColor(x, y)
                channels = (color.red(), color.green(), color.blue())
                if max(channels) - min(channels) > 24 and max(channels) > 48:
                    chromatic_pixels += 1
        self.assertGreater(chromatic_pixels, 120)
        self.dispose(engine, component, window)


if __name__ == "__main__":
    unittest.main()
