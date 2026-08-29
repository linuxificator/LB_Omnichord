import QtQuick
import QtQuick.Controls

Frame {
    id: root

    property real currentValue: 0.5

    property color panelColor: "#c7b978"
    property color panelBorderColor: "#8e8150"
    property color fillColor: "#2474b8"
    property color textColor: "#302b18"
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

    // A tap changes volume by five percentage points. Qt's standard button
    // auto-repeat supplies the held increments and their cadence.
    property real tapStep: 0.05
    property real repeatStep: 0.025

    signal edited(real value)
    signal activated()

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

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const wasBound = root.midiBound
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        return learned || wasBound || root.midiPresetFeedback
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
        color: {
            if (root.midiVisualState === "preset-displaced")
                return "#f22b2b"
            if (root.midiVisualState === "preset-incoming")
                return "#3186d7"
            return root.midiBound ? "#35b85a" : "#ffffff"
        }
        border.color: root.fillColor
        border.width: 2


        SequentialAnimation on opacity {
            running: root.midiPresetFeedback
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.2; duration: 110 }
            NumberAnimation { from: 0.2; to: 1.0; duration: 110 }
        }
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

    Button {
        id: incrementButton
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: parent.height / 2
        autoRepeat: true
        property bool repeatingPress: false
        background: Item {}
        contentItem: Item {}

        onPressedChanged: {
            if (pressed) {
                repeatingPress = false
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.midiBindingGesture = false
            }
        }
        onPressed: {
            if (!root.midiBindingGesture) {
                root.step(
                    1,
                    repeatingPress ? root.repeatStep : root.tapStep
                )
            }
            repeatingPress = true
        }
        onDoubleClicked: {
            if (root.midiControlRouter !== null) {
                root.midiControlRouter.controlTargetDoubleTapped(
                    root.midiTarget
                )
            }
        }
    }

    Button {
        id: decrementButton
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height / 2
        autoRepeat: true
        property bool repeatingPress: false
        background: Item {}
        contentItem: Item {}

        onPressedChanged: {
            if (pressed) {
                repeatingPress = false
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.midiBindingGesture = false
            }
        }
        onPressed: {
            if (!root.midiBindingGesture) {
                root.step(
                    -1,
                    repeatingPress ? root.repeatStep : root.tapStep
                )
            }
            repeatingPress = true
        }
        onDoubleClicked: {
            if (root.midiControlRouter !== null) {
                root.midiControlRouter.controlTargetDoubleTapped(
                    root.midiTarget
                )
            }
        }
    }
}
