import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: window

    width: 1024
    height: 600
    visible: true
    visibility: Window.FullScreen
    color: "#171a20"
    title: "Qt Multi-touch Test"

    property int currentPointCount: 0
    property int highestPointCount: 0

    Text {
        anchors.top: parent.top
        anchors.topMargin: 24
        anchors.horizontalCenter:
            parent.horizontalCenter

        text:
            "Current touch points: "
            + window.currentPointCount
            + "    Maximum seen: "
            + window.highestPointCount

        color: "white"
        font.pixelSize: 28
        font.bold: true
        z: 10
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        anchors.horizontalCenter:
            parent.horizontalCenter

        text:
            "Put two or more fingers on different parts of the screen. "
            + "Press Escape to exit."

        color: "#c8d1dc"
        font.pixelSize: 18
        z: 10
    }

    Shortcut {
        sequence: "Escape"
        onActivated: Qt.quit()
    }

    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 10
        mouseEnabled: false

        touchPoints: [
            TouchPoint { id: p1 },
            TouchPoint { id: p2 },
            TouchPoint { id: p3 },
            TouchPoint { id: p4 },
            TouchPoint { id: p5 },
            TouchPoint { id: p6 },
            TouchPoint { id: p7 },
            TouchPoint { id: p8 },
            TouchPoint { id: p9 },
            TouchPoint { id: p10 }
        ]

        onTouchUpdated: (points) => {
            window.currentPointCount =
                points.length

            window.highestPointCount =
                Math.max(
                    window.highestPointCount,
                    points.length
                )
        }

        onReleased: (points) => {
            window.currentPointCount =
                touchPoints.filter(
                    point => point.pressed
                ).length
        }

        onCanceled: (points) => {
            window.currentPointCount = 0
        }
    }

    component PointMarker: Rectangle {
        required property var touchPoint
        required property color markerColor

        visible: touchPoint.pressed
        x: touchPoint.x - width / 2
        y: touchPoint.y - height / 2
        width: 72
        height: 72
        radius: 36
        color: markerColor
        opacity: 0.78
        border.color: "white"
        border.width: 3

        Text {
            anchors.centerIn: parent
            text: parent.touchPoint.pointId
            color: "white"
            font.pixelSize: 18
            font.bold: true
        }
    }

    PointMarker {
        touchPoint: p1
        markerColor: "#e74c3c"
    }
    PointMarker {
        touchPoint: p2
        markerColor: "#3498db"
    }
    PointMarker {
        touchPoint: p3
        markerColor: "#2ecc71"
    }
    PointMarker {
        touchPoint: p4
        markerColor: "#9b59b6"
    }
    PointMarker {
        touchPoint: p5
        markerColor: "#f39c12"
    }
    PointMarker {
        touchPoint: p6
        markerColor: "#1abc9c"
    }
    PointMarker {
        touchPoint: p7
        markerColor: "#e84393"
    }
    PointMarker {
        touchPoint: p8
        markerColor: "#00cec9"
    }
    PointMarker {
        touchPoint: p9
        markerColor: "#fdcb6e"
    }
    PointMarker {
        touchPoint: p10
        markerColor: "#6c5ce7"
    }
}
