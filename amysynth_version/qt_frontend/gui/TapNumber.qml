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
    property bool centerButtonEnabled: false
    property string centerText: String(root.currentValue)
    property color centerPanelColor: root.panelColor
    property color centerPanelTextColor: root.textColor
    property color centerPanelBorderColor: root.panelBorderColor
    property var midiControlRouter: null
    property var midiTarget: ({})
    property var centerMidiTarget: ({})
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
    readonly property string centerMidiVisualState: {
        if (root.midiControlRouter === null)
            return "idle"
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.controlTargetVisualState(
            root.centerMidiTarget
        )
    }
    readonly property bool centerMidiBound: {
        if (root.midiControlRouter === null)
            return false
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.isControlTargetBound(
            root.centerMidiTarget
        )
    }
    readonly property bool centerMidiPresetFeedback:
        root.centerMidiVisualState === "preset-displaced"
        || root.centerMidiVisualState === "preset-incoming"

    signal edited(int value)
    signal activated()
    signal centerClicked()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const wasBound = root.midiBound
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        return learned || wasBound || root.midiPresetFeedback
    }

    function centerMidiButtonHandled() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.centerMidiTarget
        )
        if (learned)
            return true
        return root.midiControlRouter.midiButtonTargetBlocked(
            root.centerMidiTarget
        )
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
        id: centerPanel

        anchors.centerIn: parent
        width: parent.width - 8
        height: 27
        radius: 7
        color: root.centerPanelColor
        opacity: 0.96
        border.color: root.centerPanelBorderColor
        border.width: 1

        Rectangle {
            visible:
                root.centerButtonEnabled
                && (
                    root.centerMidiBound
                    || root.centerMidiPresetFeedback
                )
            anchors.horizontalCenter: parent.horizontalCenter
            y: 2
            width: 7
            height: 7
            radius: 4
            color: {
                if (root.centerMidiVisualState === "preset-displaced")
                    return "#f22b2b"
                if (root.centerMidiVisualState === "preset-incoming")
                    return "#3186d7"
                return root.centerMidiBound ? "#35b85a" : "#a5a5a0"
            }
        }

        Text {
            anchors.centerIn: parent
            text: root.centerText
            color: root.centerPanelTextColor
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

    Button {
        id: incrementButton
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height:
            root.centerButtonEnabled
            ? (parent.height - 27) / 2
            : parent.height / 2
        autoRepeat: true
        background: Item {}
        contentItem: Item {}

        onPressedChanged: {
            if (pressed) {
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.midiBindingGesture = false
            }
        }
        onPressed: {
            if (!root.midiBindingGesture)
                root.step(1)
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
        height:
            root.centerButtonEnabled
            ? (parent.height - 27) / 2
            : parent.height / 2
        autoRepeat: true
        background: Item {}
        contentItem: Item {}

        onPressedChanged: {
            if (pressed) {
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.midiBindingGesture = false
            }
        }
        onPressed: {
            if (!root.midiBindingGesture)
                root.step(-1)
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
        anchors.centerIn: parent
        width: parent.width
        height: 27
        visible: root.centerButtonEnabled
        background: Item {}
        contentItem: Item {}
        onClicked: {
            if (!root.centerMidiButtonHandled())
                root.centerClicked()
        }
    }
}
