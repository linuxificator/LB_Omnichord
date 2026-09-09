pragma ComponentBehavior: Bound

import QtQuick
import "PointerNormalization.js" as PointerNormalization

Item {
    id: root

    required property var controller
    property var midiControlRouter: null
    property var midiTarget: ({
        "screen": "omni",
        "kind": "strum_position"
    })
    property bool ladderMode: false
    property Item visualOverlay: null

    property bool gestureActive: false
    property bool bindingGesture: false

    function normalizedY(y) {
        return PointerNormalization.verticalUnit(y, root.height)
    }

    function visualPoint(x, y) {
        if (root.visualOverlay)
            return root.mapToItem(root.visualOverlay, x, y)
        return Qt.point(x, y)
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
            id: guideLine
            required property int index

            x: 12
            y:
                18
                + guideLine.index
                * (
                    root.height - 36
                ) / 14
            width: root.width - 24
            height: guideLine.index % 2 === 0 ? 2 : 1
            radius: 1
            color:
                guideLine.index % 2 === 0
                ? "#4f91c8"
                : "#275e8e"
            opacity: 0.75
        }
    }

    Item {
        anchors.fill: parent
        z: 900

        Migraine {
            id: migraine

            parent: root.visualOverlay ? root.visualOverlay : root
            width: 96
            height: 96
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

            root.bindingGesture = (
                root.midiControlRouter
                && root.midiControlRouter.activateControlTarget(root.midiTarget)
            )
            if (root.bindingGesture)
                return

            root.gestureActive = true
            root.controller.strumStart(
                root.normalizedY(points[0].y)
                + (root.ladderMode ? 2.0 : 0.0)
            )
            const visual = root.visualPoint(points[0].x, points[0].y)
            migraine.beginAt(visual.x, visual.y)
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
                + (root.ladderMode ? 2.0 : 0.0)
            )
            const visual = root.visualPoint(points[0].x, points[0].y)
            migraine.moveTo(visual.x, visual.y)
        }

        onReleased: (points) => {
            if (root.bindingGesture) {
                root.bindingGesture = false
                return
            }
            if (!root.gestureActive)
                return

            root.gestureActive = false
            root.controller.strumEnd()
            migraine.release()
        }

        onCanceled: (points) => {
            if (root.bindingGesture) {
                root.bindingGesture = false
                return
            }
            if (!root.gestureActive)
                return

            root.gestureActive = false
            root.controller.strumEnd()
            migraine.release()
        }

        // If the outer Flickable is interactive in windowed mode, retain
        // the strum once Qt recognises this as a gesture.
        onGestureStarted: (gesture) => {
            gesture.grab()
        }
    }
}
