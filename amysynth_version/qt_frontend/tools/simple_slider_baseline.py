#!/usr/bin/env python3
"""Minimal PySide6/QML slider baseline.

This diagnostic intentionally avoids all LB Omnichord backend, AMY, MIDI,
custom controls, scaling helpers and application layout.  It answers one
question: does the current Python/PySide6/Qt/QML stack on this machine support
mouse press-and-hold dragging of a plain Qt Quick Slider?
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


QML = b"""
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: window
    width: 640
    height: 220
    visible: true
    title: "LB Omnichord simple slider baseline"

    property real lastMovedValue: slider.value
    property int moveCount: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Label {
            Layout.fillWidth: true
            text: "Plain Qt Quick Slider. Hold the round handle with the mouse and drag left/right."
            wrapMode: Text.WordWrap
            font.pixelSize: 16
        }

        Slider {
            id: slider
            Layout.fillWidth: true
            from: 0
            to: 100
            value: 25
            live: true

            onMoved: {
                window.lastMovedValue = value
                window.moveCount += 1
                console.log("slider moved", value, "moveCount", window.moveCount)
            }
        }

        Label {
            Layout.fillWidth: true
            text: "value " + slider.value.toFixed(1)
                  + " / moved " + window.lastMovedValue.toFixed(1)
                  + " / move events " + window.moveCount
            font.pixelSize: 16
        }

        Label {
            Layout.fillWidth: true
            text: "Expected: while the mouse button remains down, the handle follows continuous horizontal motion."
            wrapMode: Text.WordWrap
        }
    }
}
"""


def main() -> int:
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    engine.loadData(QML, QUrl("in-memory:simple_slider_baseline.qml"))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
