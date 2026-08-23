import QtQuick

Item {
    id: root

    required property var controller
    required property int rowIndex
    required property bool tuningCoupled

    property color padColor: "#5d9fd0"
    property bool gestureActive: false

    function normalizedY(y) {
        if (root.height <= 0)
            return 0.5
        return Math.max(0.0, Math.min(1.0, y / root.height))
    }

    Rectangle {
        anchors.fill: parent
        radius: 13
        border.color: Qt.lighter(root.padColor, 1.35)
        border.width: 2

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Qt.darker(root.padColor, 1.20)
            }
            GradientStop {
                position: 0.5
                color: Qt.darker(root.padColor, 1.65)
            }
            GradientStop {
                position: 1.0
                color: Qt.darker(root.padColor, 2.15)
            }
        }
    }

    Repeater {
        model: 15

        Rectangle {
            required property int index

            x: 12
            y:
                18
                + index
                * (root.height - 36) / 14
            width: root.width - 24
            height: index % 2 === 0 ? 2 : 1
            radius: 1
            color:
                index % 2 === 0
                ? Qt.lighter(root.padColor, 1.35)
                : Qt.lighter(root.padColor, 1.12)
            opacity: root.gestureActive ? 1.0 : 0.75
        }
    }

    MultiPointTouchArea {
        anchors.fill: parent
        z: 1000
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: true

        onPressed: (points) => {
            if (!points || points.length === 0)
                return
            root.gestureActive = true
            root.controller.midiPreviewStart(
                root.rowIndex,
                root.normalizedY(points[0].y),
                root.tuningCoupled
            )
        }

        onUpdated: (points) => {
            if (
                !root.gestureActive
                || !points
                || points.length === 0
            )
                return
            root.controller.midiPreviewMove(
                root.rowIndex,
                root.normalizedY(points[0].y),
                root.tuningCoupled
            )
        }

        onReleased: {
            if (!root.gestureActive)
                return
            root.gestureActive = false
            root.controller.midiPreviewEnd()
        }

        onCanceled: {
            if (!root.gestureActive)
                return
            root.gestureActive = false
            root.controller.midiPreviewEnd()
        }

        onGestureStarted: (gesture) =>
            gesture.grab()
    }
}
