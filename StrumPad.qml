import QtQuick

Item {
    id: root

    required property var controller

    property real touchStartY: 0
    property bool touchMoved: false
    property real touchDragThreshold: 8

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
     * Real touchscreen path.
     *
     * This area handles exactly one touch point inside the strum strip.
     * Other touch points remain available to buttons, sliders and wheels
     * elsewhere in the window.
     *
     * mouseEnabled is false so a touchscreen that is incorrectly exposed
     * merely as a mouse cannot silently masquerade as multi-touch here.
     */
    MultiPointTouchArea {
        id: touchArea

        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: false

        touchPoints: [
            TouchPoint {
                id: strumFinger
            }
        ]

        onPressed: (points) => {
            root.touchStartY = strumFinger.y
            root.touchMoved = false

            root.controller.strumStart(
                strumFinger.y / root.height
            )
        }

        onUpdated: (points) => {
            if (
                Math.abs(
                    strumFinger.y
                    - root.touchStartY
                ) >= root.touchDragThreshold
            ) {
                root.touchMoved = true
            }

            root.controller.strumMove(
                strumFinger.y / root.height
            )
        }

        onReleased: (points) => {
            if (!root.touchMoved) {
                const releasedPoint = points[0]
                root.controller.strumTap(
                    releasedPoint.y / root.height
                )
            }

            root.controller.strumEnd()
        }

        onCanceled: (points) => {
            root.controller.strumEnd()
        }

        /*
         * The outer Flickable is normally non-interactive in scale-to-fit
         * mode. Explicitly grab the strum gesture after the drag threshold
         * in case scrolling is enabled in windowed mode.
         */
        onGestureStarted: (gesture) => {
            gesture.grab()
        }
    }

    /*
     * Mouse-only fallback for desktop testing.
     * It is deliberately excluded from touchscreen events.
     */
    TapHandler {
        id: mouseTapHandler

        acceptedDevices: PointerDevice.Mouse

        onTapped:
            root.controller.strumTap(
                point.position.y
                / root.height
            )
    }

    DragHandler {
        id: mouseDragHandler

        acceptedDevices: PointerDevice.Mouse
        target: null
        xAxis.enabled: false

        onActiveChanged: {
            if (active) {
                root.controller.strumStart(
                    centroid.position.y
                    / root.height
                )
            } else {
                root.controller.strumEnd()
            }
        }

        onTranslationChanged: {
            if (active) {
                root.controller.strumMove(
                    centroid.position.y
                    / root.height
                )
            }
        }
    }
}
