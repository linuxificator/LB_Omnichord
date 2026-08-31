from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QObject, QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"


class QmlGestureControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    def create_window(
        self,
        source: bytes,
    ) -> tuple[QQmlEngine, QQmlComponent, QObject]:
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        component.setData(
            source,
            QUrl.fromLocalFile(str(GUI / "GestureControlTest.qml")),
        )
        window = component.create()
        self.assertIsNotNone(
            window,
            "\n".join(error.toString() for error in component.errors()),
        )
        assert window is not None
        QCoreApplication.processEvents()
        return engine, component, window

    def test_tap_number_uses_qt_button_auto_repeat(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    id: window
    width: 90
    height: 220
    visible: true
    property int editCount: 0

    TapNumber {
        x: 20
        y: 10
        width: 50
        height: 200
        currentValue: 440
        onEdited: (value) => {
            currentValue = value
            window.editCount += 1
        }
    }
}
""",
        )
        point = QPoint(45, 35)
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QCoreApplication.processEvents()
        self.assertEqual(int(window.property("editCount")), 1)

        QTest.qWait(460)
        repeated = int(window.property("editCount"))
        self.assertGreater(repeated, 1)

        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QTest.qWait(160)
        self.assertEqual(int(window.property("editCount")), repeated)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_slider_double_tap_is_classified_by_qt(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    width: 190
    height: 90
    visible: true

    QtObject {
        id: midiRouter
        objectName: "midiRouter"
        property int bindingVersion: 0
        property int doubleTapCount: 0
        function isControlTargetBound(target) { return true }
        function controlTargetVisualState(target) { return "bound" }
        function activateControlTarget(target) { return false }
        function controlTargetDoubleTapped(target) { doubleTapCount += 1 }
        function controlTargetMoved(target) {}
    }

    LabeledSlider {
        x: 15
        y: 10
        width: 160
        height: 70
        currentValue: 0.5
        midiControlRouter: midiRouter
        midiTarget: ({"screen": "omni", "kind": "master_volume"})
    }
}
""",
        )
        point = QPoint(95, 65)
        QTest.mouseDClick(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QCoreApplication.processEvents()

        router = window.findChild(QObject, "midiRouter")
        self.assertIsNotNone(router)
        assert router is not None
        self.assertEqual(int(router.property("doubleTapCount")), 1)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_midi_bound_slider_handle_drag_still_moves(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    id: window
    width: 190
    height: 90
    visible: true
    property real editedValue: 0.2
    property int editCount: 0

    QtObject {
        id: midiRouter
        objectName: "midiRouter"
        property int bindingVersion: 0
        property int moveCount: 0
        function isControlTargetBound(target) { return true }
        function controlTargetVisualState(target) { return "bound" }
        function activateControlTarget(target) { return false }
        function controlTargetDoubleTapped(target) {}
        function controlTargetMoved(target) { moveCount += 1 }
    }

    LabeledSlider {
        x: 15
        y: 10
        width: 160
        height: 70
        fromValue: 0
        toValue: 1
        currentValue: window.editedValue
        midiControlRouter: midiRouter
        midiTarget: ({"screen": "omni", "kind": "master_volume"})
        onEdited: (value) => {
            window.editedValue = value
            window.editCount += 1
        }
    }
}
""",
        )
        start = QPoint(52, 65)
        end = QPoint(145, 65)
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            start,
        )
        QCoreApplication.processEvents()
        QTest.mouseMove(window, end, delay=20)
        QCoreApplication.processEvents()
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            end,
        )
        QCoreApplication.processEvents()

        self.assertGreater(float(window.property("editedValue")), 0.5)
        self.assertGreater(int(window.property("editCount")), 0)
        router = window.findChild(QObject, "midiRouter")
        self.assertIsNotNone(router)
        assert router is not None
        self.assertGreater(int(router.property("moveCount")), 0)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
