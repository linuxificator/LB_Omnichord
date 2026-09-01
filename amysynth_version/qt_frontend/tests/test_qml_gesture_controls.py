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

    def test_midi_bound_slider_press_without_movement_stays_bound(self) -> None:
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
        property int manualReleaseCount: 0
        function isControlTargetBound(target) { return true }
        function controlTargetVisualState(target) { return "bound" }
        function activateControlTarget(target) { return false }
        function releaseControlTargetForManualEdit(target) {
            manualReleaseCount += 1
        }
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
        # currentValue 0.5 places the handle at the horizontal midpoint.
        point = QPoint(95, 65)
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QCoreApplication.processEvents()
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QCoreApplication.processEvents()

        router = window.findChild(QObject, "midiRouter")
        self.assertIsNotNone(router)
        assert router is not None
        self.assertEqual(int(router.property("manualReleaseCount")), 0)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_midi_bound_slider_track_click_is_a_manual_value_edit(self) -> None:
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
    property real editedValue: 0.5
    property int editCount: 0

    QtObject {
        id: midiRouter
        objectName: "midiRouter"
        property int bindingVersion: 0
        property bool bound: true
        property int manualReleaseCount: 0
        function isControlTargetBound(target) { return bound }
        function controlTargetVisualState(target) {
            return bound ? "bound" : "idle"
        }
        function activateControlTarget(target) { return false }
        function releaseControlTargetForManualEdit(target) {
            if (!bound)
                return
            bound = false
            bindingVersion += 1
            manualReleaseCount += 1
        }
    }

    LabeledSlider {
        x: 15
        y: 10
        width: 160
        height: 70
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
        # Click well left of the 0.5 handle. Qt changes the slider value, so
        # this is a genuine manual edit even though it is not a drag.
        point = QPoint(45, 65)
        QTest.mouseClick(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        QCoreApplication.processEvents()

        router = window.findChild(QObject, "midiRouter")
        self.assertIsNotNone(router)
        assert router is not None
        self.assertEqual(int(router.property("manualReleaseCount")), 1)
        self.assertGreater(int(window.property("editCount")), 0)
        self.assertFalse(bool(router.property("bound")))
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
    property string eventOrder: ""

    QtObject {
        id: midiRouter
        objectName: "midiRouter"
        property int bindingVersion: 0
        property bool bound: true
        property int manualReleaseCount: 0
        function isControlTargetBound(target) { return bound }
        function controlTargetVisualState(target) {
            return bound ? "bound" : "idle"
        }
        function activateControlTarget(target) { return false }
        function releaseControlTargetForManualEdit(target) {
            if (!bound)
                return
            bound = false
            bindingVersion += 1
            manualReleaseCount += 1
            window.eventOrder += "release;"
        }
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
            window.eventOrder += "edit;"
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
        self.assertEqual(int(router.property("manualReleaseCount")), 1)
        self.assertTrue(
            str(window.property("eventOrder")).startswith("release;edit;"),
            str(window.property("eventOrder")),
        )
        self.assertFalse(bool(router.property("bound")))
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_plain_slider_handle_drag_still_moves(self) -> None:
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

    LabeledSlider {
        x: 15
        y: 10
        width: 160
        height: 70
        fromValue: 0
        toValue: 1
        currentValue: window.editedValue
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
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_labeled_slider_drag_does_not_depend_on_immediate_backend_echo(self) -> None:
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
    property real backendValue: 0.2
    property real lastEditedValue: 0.2
    property int editCount: 0

    LabeledSlider {
        objectName: "slowBackendSlider"
        x: 15
        y: 10
        width: 160
        height: 70
        fromValue: 0
        toValue: 1
        currentValue: window.backendValue
        onEdited: (value) => {
            window.lastEditedValue = value
            window.editCount += 1
            // Deliberately notify an old backend value during the drag.
            // The real Python backend may lag; handle dragging must not
            // fight an older backend echo while Qt owns the drag.
            window.backendValue = 0.19
            window.backendValue = 0.2
        }
    }
}
""",
        )
        root = window.findChild(QObject, "slowBackendSlider")
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
        start = QPoint(52, 65)
        end = QPoint(145, 65)
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            start,
        )
        QCoreApplication.processEvents()
        for x in (75, 100, 125, 145):
            QTest.mouseMove(window, QPoint(x, 65), delay=20)
            QCoreApplication.processEvents()
        self.assertGreater(float(slider.property("value")), 0.5)
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            end,
        )
        QCoreApplication.processEvents()

        self.assertGreater(float(window.property("lastEditedValue")), 0.5)
        self.assertGreater(int(window.property("editCount")), 0)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_parameter_slider_drag_ignores_stale_model_replacement_during_press(self) -> None:
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
    property real lastEditedValue: 100
    property int editCount: 0
    property var activeControl: staleControl

    QtObject {
        id: staleControl
        property string key: "decay"
        property string label: "Decay"
        property real value: 100
        property real minimum: 0
        property real maximum: 1000
        property real step: 1
        property int decimals: 0
        property string unit: "ms"
        property string scale: "linear"
    }

    QtObject {
        id: staleControlCopy
        property string key: "decay"
        property string label: "Decay"
        property real value: 100
        property real minimum: 0
        property real maximum: 1000
        property real step: 1
        property int decimals: 0
        property string unit: "ms"
        property string scale: "linear"
    }

    ParameterSlider {
        objectName: "slowModelParameter"
        x: 15
        y: 10
        width: 160
        height: 70
        control: window.activeControl
        onEdited: (key, value) => {
            window.lastEditedValue = value
            window.editCount += 1
            // Simulate a backend state refresh replacing modelData with an
            // older value while the user is still dragging.
            window.activeControl = window.activeControl === staleControl
                ? staleControlCopy
                : staleControl
        }
    }
}
""",
        )
        root = window.findChild(QObject, "slowModelParameter")
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
        start = QPoint(30, 65)
        end = QPoint(145, 65)
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            start,
        )
        QCoreApplication.processEvents()
        for x in (60, 90, 120, 145):
            QTest.mouseMove(window, QPoint(x, 65), delay=20)
            QCoreApplication.processEvents()
        self.assertGreater(float(slider.property("value")), 500.0)
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            end,
        )
        QCoreApplication.processEvents()

        self.assertGreater(float(window.property("lastEditedValue")), 500.0)
        self.assertGreater(int(window.property("editCount")), 0)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_custom_slider_handle_is_registered_with_qt_slider(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    width: 190
    height: 160
    visible: true

    LabeledSlider {
        objectName: "labeled"
        x: 15
        y: 10
        width: 160
        height: 70
        fromValue: 0
        toValue: 1
        currentValue: 0.2
    }

    QtObject {
        id: control
        property string key: "frequency"
        property string label: "Frequency"
        property real value: 440
        property real minimum: 100
        property real maximum: 1000
        property real step: 1
        property int decimals: 0
        property string unit: "Hz"
        property string scale: "linear"
    }

    ParameterSlider {
        objectName: "parameter"
        x: 15
        y: 80
        width: 160
        height: 70
        control: control
    }
}
""",
        )
        for object_name in ("labeled", "parameter"):
            root = window.findChild(QObject, object_name)
            self.assertIsNotNone(root)
            assert root is not None
            sliders = [
                child
                for child in root.findChildren(QObject)
                if "Slider" in child.metaObject().className()
                and child.metaObject().indexOfProperty("implicitHandleWidth") >= 0
            ]
            self.assertEqual(len(sliders), 1)
            slider = sliders[0]
            self.assertGreater(float(slider.property("implicitHandleWidth")), 0.0)
            self.assertGreater(float(slider.property("implicitHandleHeight")), 0.0)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_shared_slider_fill_and_handle_use_native_visual_position(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    width: 220
    height: 90
    visible: true

    LabeledSlider {
        objectName: "mappedSlider"
        x: 20
        y: 10
        width: 180
        height: 70
        label: "Tempo"
        fromValue: 0
        toValue: 100
        currentValue: 25
    }
}
""",
        )
        root = window.findChild(QObject, "mappedSlider")
        self.assertIsNotNone(root)
        assert root is not None
        slider = root.findChild(QObject, "nativeSlider")
        track = root.findChild(QObject, "sliderTrack")
        fill = root.findChild(QObject, "sliderFill")
        handle = root.findChild(QObject, "sliderHandle")
        self.assertIsNotNone(slider)
        self.assertIsNotNone(track)
        self.assertIsNotNone(fill)
        self.assertIsNotNone(handle)
        assert slider is not None
        assert track is not None
        assert fill is not None
        assert handle is not None

        visual = float(slider.property("visualPosition"))
        self.assertAlmostEqual(visual, 0.25, places=6)
        self.assertAlmostEqual(
            float(fill.property("width")),
            visual * float(track.property("width")),
            places=5,
        )
        expected_handle_x = float(slider.property("leftPadding")) + visual * (
            float(slider.property("availableWidth")) - float(handle.property("width"))
        )
        self.assertAlmostEqual(float(handle.property("x")), expected_handle_x, places=5)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()

    def test_reverb_panel_slider_drag_works_in_real_panel_layout(self) -> None:
        engine, component, window = self.create_window(
            b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "."

Window {
    id: window
    width: 360
    height: 110
    visible: true

    QtObject {
        id: controller
        property real reverbLevel: 0.2
        property real reverbLiveness: 0.2
        property real reverbDamping: 0.2
        property bool reverbDrums: false
        function setReverbLevel(value) { reverbLevel = value }
        function setReverbLiveness(value) { reverbLiveness = value }
        function setReverbDamping(value) { reverbDamping = value }
        function setReverbDrums(value) { reverbDrums = value }
    }

    QtObject {
        id: midiRouter
        property int bindingVersion: 0
        function isControlTargetBound(target) { return false }
        function controlTargetVisualState(target) { return "idle" }
        function activateControlTarget(target) { return false }
        function releaseControlTargetForManualEdit(target) {}
        function midiButtonTargetBlocked(target) { return false }
    }

    ReverbPanel {
        objectName: "reverbPanel"
        anchors.fill: parent
        controller: controller
        midiControlRouter: midiRouter
        controlScreen: "omni"
    }
}
""",
        )
        # First reverb slider starts at x≈4 and has width≈74 in this panel.
        # Press its visible handle at value 0.2 and drag across the same row.
        QTest.mousePress(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 92),
        )
        QCoreApplication.processEvents()
        for x in (35, 50, 65):
            QTest.mouseMove(window, QPoint(x, 92), delay=20)
            QCoreApplication.processEvents()
        QTest.mouseRelease(
            window,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(65, 92),
        )
        QCoreApplication.processEvents()
        # Find the controller object by checking for the reverbLevel property.
        controllers = [
            child
            for child in window.findChildren(QObject)
            if child.metaObject().indexOfProperty("reverbLevel") >= 0
        ]
        self.assertEqual(len(controllers), 1)
        self.assertGreater(float(controllers[0].property("reverbLevel")), 0.8)
        window.deleteLater()
        component.deleteLater()
        engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
