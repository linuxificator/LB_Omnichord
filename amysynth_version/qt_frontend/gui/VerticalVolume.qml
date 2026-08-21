import QtQuick
import QtQuick.Controls

Frame {
    id: root

    property real currentValue: 0.5

    property color panelColor: "#c7b978"
    property color panelBorderColor: "#8e8150"
    property color fillColor: "#2474b8"
    property color textColor: "#302b18"

    // A tap changes volume by five percentage points. After a short hold,
    // it auto-repeats in smaller, fast increments.
    property real tapStep: 0.05
    property real repeatStep: 0.025
    property int holdDelayMs: 380
    property int repeatIntervalMs: 75

    property int repeatDirection: 0

    signal edited(real value)

    padding: 4

    function clamp(value) {
        return Math.max(
            0.0,
            Math.min(1.0, value)
        )
    }

    function step(direction, amount) {
        if (direction === 0) {
            return
        }

        root.edited(
            root.clamp(
                root.currentValue
                + direction * amount
            )
        )
    }

    function beginPress(yPosition) {
        root.repeatDirection =
            yPosition < root.height / 2
            ? 1
            : -1

        // Immediate response for an ordinary tap.
        root.step(
            root.repeatDirection,
            root.tapStep
        )

        holdDelay.restart()
    }

    function endPress() {
        holdDelay.stop()
        fastRepeat.stop()
        root.repeatDirection = 0
    }

    background: Rectangle {
        radius: 9
        color: root.panelColor
        border.color: root.panelBorderColor
        border.width: 1
    }

    // Keep the familiar vertical-slider visual, but it is now an indicator
    // rather than a draggable control.
    Rectangle {
        id: track

        anchors.horizontalCenter:
            parent.horizontalCenter
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: 10
        anchors.bottomMargin: 10

        width: 7
        radius: 3
        color: "#f7f2da"

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height:
                root.currentValue
                * parent.height
            radius: 3
            color: root.fillColor
        }
    }

    Rectangle {
        id: handle

        anchors.horizontalCenter:
            track.horizontalCenter

        y:
            track.y
            + (
                1 - root.currentValue
            )
            * (
                track.height - height
            )

        width: 23
        height: 14
        radius: 6
        color: "#ffffff"
        border.color: root.fillColor
        border.width: 2
    }

    Rectangle {
        anchors.centerIn: parent
        width: parent.width - 8
        height: 25
        radius: 7
        color: root.panelColor
        opacity: 0.94
        border.color: root.panelBorderColor
        border.width: 1

        Text {
            anchors.centerIn: parent

            text:
                Math.round(
                    root.currentValue * 100
                ) + "%"

            color: root.textColor
            font.pixelSize: 11
            font.bold: true
        }
    }

    // Subtle non-text indication of the two tap regions.
    Canvas {
        anchors.fill: parent
        opacity: 0.45

        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.fillStyle = root.fillColor

            const cx = width / 2

            c.beginPath()
            c.moveTo(cx, 6)
            c.lineTo(cx - 5, 13)
            c.lineTo(cx + 5, 13)
            c.closePath()
            c.fill()

            c.beginPath()
            c.moveTo(cx, height - 6)
            c.lineTo(cx - 5, height - 13)
            c.lineTo(cx + 5, height - 13)
            c.closePath()
            c.fill()
        }
    }

    Timer {
        id: holdDelay

        interval: root.holdDelayMs
        repeat: false

        onTriggered: {
            if (root.repeatDirection !== 0) {
                fastRepeat.start()
            }
        }
    }

    Timer {
        id: fastRepeat

        interval: root.repeatIntervalMs
        repeat: true

        onTriggered:
            root.step(
                root.repeatDirection,
                root.repeatStep
            )
    }

    // One independent touch point per volume control. This retains the
    // application's multi-touch behavior.
    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: true

        touchPoints: [
            TouchPoint {
                id: volumePoint
            }
        ]

        onPressed:
            root.beginPress(volumePoint.y)

        onReleased:
            root.endPress()

        onCanceled:
            root.endPress()
    }
}
