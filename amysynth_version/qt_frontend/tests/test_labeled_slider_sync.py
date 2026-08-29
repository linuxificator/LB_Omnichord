from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QCoreApplication, QObject, QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"


class LabeledSliderSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    def test_backend_change_restores_visual_value_after_local_write(self) -> None:
        engine = QQmlEngine()
        component = QQmlComponent(engine)
        component.setData(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    width: 180
    height: 90
    visible: true

    QtObject {
        id: midiRouter
        objectName: "midiRouter"
        property int bindingVersion: 0
        property bool targetBound: false
        property string targetVisualState: "idle"
        function isControlTargetBound(target) { return targetBound }
        function controlTargetVisualState(target) { return targetVisualState }
        function activateControlTarget(target) { return true }
        function controlTargetDoubleTapped(target) {}
        function controlTargetMoved(target) {}
    }

    LabeledSlider {
        objectName: "reverbSlider"
        width: 145
        height: 70
        fromValue: 0
        toValue: 3
        currentValue: 0.25
        midiControlRouter: midiRouter
        midiTarget: ({"screen": "omni", "kind": "rhythm_tempo"})
    }
}
""",
            QUrl.fromLocalFile(str(GUI / "LabeledSliderSyncTest.qml")),
        )
        window = component.create()
        self.assertIsNotNone(
            window,
            "\n".join(error.toString() for error in component.errors()),
        )
        assert window is not None
        root = window.findChild(QObject, "reverbSlider")
        self.assertIsNotNone(root)
        assert root is not None
        sliders = [
            child
            for child in root.findChildren(QObject)
            if "Slider" in child.metaObject().className()
            and child.metaObject().indexOfProperty("value") >= 0
        ]
        self.assertEqual(len(sliders), 1)
        slider = sliders[0]

        # Reproduce the binding gesture through the actual Qt Quick event path.
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(125, 55),
        )
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(125, 55),
        )
        QCoreApplication.processEvents()
        self.assertAlmostEqual(float(slider.property("value")), 0.25)

        # The next backend notify must remain authoritative after that touch.
        root.setProperty("currentValue", 0.5)
        QCoreApplication.processEvents()

        self.assertAlmostEqual(float(slider.property("value")), 0.5)

        router = window.findChild(QObject, "midiRouter")
        self.assertIsNotNone(router)
        assert router is not None
        handles = [
            child
            for child in root.findChildren(QObject)
            if child.property("width") == 19
            and child.property("height") == 19
            and child.metaObject().indexOfProperty("color") >= 0
        ]
        self.assertEqual(len(handles), 1)
        handle = handles[0]

        for state, expected in (
            ("preset-displaced", "#f22b2b"),
            ("preset-incoming", "#3186d7"),
        ):
            router.setProperty("targetVisualState", state)
            router.setProperty(
                "bindingVersion",
                int(router.property("bindingVersion")) + 1,
            )
            QCoreApplication.processEvents()
            self.assertEqual(QColor(handle.property("color")).name(), expected)

        router.setProperty("targetVisualState", "bound")
        router.setProperty("targetBound", True)
        router.setProperty(
            "bindingVersion",
            int(router.property("bindingVersion")) + 1,
        )
        QCoreApplication.processEvents()
        self.assertEqual(QColor(handle.property("color")).name(), "#35b85a")
        window.deleteLater()
        engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
