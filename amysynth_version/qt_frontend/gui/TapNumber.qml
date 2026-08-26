import QtQuick
import QtQuick.Controls

Frame {
    id: root

    property int currentValue: 440
    property int fromValue: 415
    property int toValue: 466
    property int stepValue: 1

    property color panelColor: "#efb45e"
    property color panelBorderColor: "#a76512"
    property color fillColor: "#cf7411"
    property color textColor: "#4b2804"
    property var midiControlRouter: null
    property var midiTarget: ({})
    property bool midiBindingGesture: false

    readonly property bool midiBound: {
        if (root.midiControlRouter === null)
            return false
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.isControlTargetBound(root.midiTarget)
    }
    readonly property string midiVisualState: {
        if (root.midiControlRouter === null)
            return "idle"
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.controlTargetVisualState(root.midiTarget)
    }
    readonly property bool midiPresetFeedback:
        root.midiVisualState === "preset-displaced"
        || root.midiVisualState === "preset-incoming"

    property int holdDelayMs: 380
    property int repeatIntervalMs: 75
    property int repeatDirection: 0

    signal edited(int value)
    signal activated()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const wasBound = root.midiBound
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        if (!learned)
            root.midiControlRouter.controlTargetTapped(root.midiTarget)
        return learned || wasBound || root.midiPresetFeedback
    }

    padding: 4

    function clamp(value) {
        return Math.max(
            root.fromValue,
            Math.min(root.toValue, value)
        )
    }

    function step(direction) {
        if (direction === 0) {
            return
        }

        root.edited(
            root.clamp(
                root.currentValue
                + direction * root.stepValue
            )
        )
    }

    function beginPress(yPosition) {
        root.repeatDirection =
            yPosition < root.height / 2
            ? 1
            : -1

        root.step(root.repeatDirection)
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
        color: "#fff1d5"

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height:
                (
                    root.currentValue
                    - root.fromValue
                )
                / (
                    root.toValue
                    - root.fromValue
                )
                * parent.height
            radius: 3
            color: {
                if (root.midiVisualState === "preset-displaced")
                    return "#f22b2b"
                if (root.midiVisualState === "preset-incoming")
                    return "#3186d7"
                return root.midiBound ? "#35b85a" : root.fillColor
            }

            SequentialAnimation on opacity {
                running: root.midiPresetFeedback
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.2; duration: 110 }
                NumberAnimation { from: 0.2; to: 1.0; duration: 110 }
            }
        }
    }

    Rectangle {
        anchors.centerIn: parent
        width: parent.width - 8
        height: 27
        radius: 7
        color: root.panelColor
        opacity: 0.96
        border.color: root.panelBorderColor
        border.width: 1

        Text {
            anchors.centerIn: parent
            text: root.currentValue
            color: root.textColor
            font.pixelSize: 14
            font.bold: true
        }
    }

    Canvas {
        anchors.fill: parent
        opacity: 0.52

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
            root.step(root.repeatDirection)
    }

    MultiPointTouchArea {
        anchors.fill: parent
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: true

        touchPoints: [
            TouchPoint {
                id: numberPoint
            }
        ]

        onPressed: {
            root.midiBindingGesture = root.beginMidiInteraction()
            root.activated()
            if (!root.midiBindingGesture)
                root.beginPress(numberPoint.y)
        }

        onReleased: {
            root.endPress()
            root.midiBindingGesture = false
        }

        onCanceled: {
            root.endPress()
            root.midiBindingGesture = false
        }
    }
}
