import QtQuick

Item {
    id: root

    required property var controller

    property bool gestureActive: false

    function normalizedY(y) {
        if (root.height <= 0)
            return 0.5
        return Math.max(0.0, Math.min(1.0, y / root.height))
    }

    Rectangle {
        anchors.fill: parent
        radius: 13
        border.color: "#6eb8ef"
        border.width: 2

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: "#123f70"
            }
            GradientStop {
                position: 0.5
                color: "#082c53"
            }
            GradientStop {
                position: 1.0
                color: "#031a34"
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
                * (
                    root.height - 36
                ) / 14
            width: root.width - 24
            height: index % 2 === 0 ? 2 : 1
            radius: 1
            color:
                index % 2 === 0
                ? "#4f91c8"
                : "#275e8e"
            opacity: 0.75
        }
    }

    /*
     * One unified input path for both real touch and desktop mouse.
     *
     * MultiPointTouchArea is kept (rather than MouseArea) because the
     * Omnichord must allow a chord button to remain held by one finger
     * while another finger strums.  mouseEnabled makes a mouse press act
     * as one pseudo touch point for desktop testing.
     *
     * v3.3 had a MultiPointTouchArea plus TapHandler plus DragHandler on
     * the same item.  On the Raspberry Pi/Wayland Qt 6 stack this could
     * leave the strum pad without a stable grab.  There is now exactly one
     * handler and therefore no competition between pointer handlers.
     */
    MultiPointTouchArea {
        id: inputArea

        anchors.fill: parent
        z: 1000

        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: true

        onPressed: (points) => {
            if (!points || points.length === 0)
                return

            root.gestureActive = true
            root.controller.strumStart(
                root.normalizedY(points[0].y)
            )
        }

        onUpdated: (points) => {
            if (
                !root.gestureActive
                || !points
                || points.length === 0
            )
                return

            root.controller.strumMove(
                root.normalizedY(points[0].y)
            )
        }

        onReleased: (points) => {
            if (!root.gestureActive)
                return

            root.gestureActive = false
            root.controller.strumEnd()
        }

        onCanceled: (points) => {
            if (!root.gestureActive)
                return

            root.gestureActive = false
            root.controller.strumEnd()
        }

        // If the outer Flickable is interactive in windowed mode, retain
        // the strum once Qt recognises this as a gesture.
        onGestureStarted: (gesture) => {
            gesture.grab()
        }
    }
}
