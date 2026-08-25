import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string label: ""
    property real currentValue: 0
    property real fromValue: 0
    property real toValue: 1
    property real stepValue: 0.01
    property int decimals: 2

    property color textColor: "#4c3b08"
    property color trackColor: "#eee2a5"
    property color fillColor: "#c59518"
    property color handleColor: "#fffbea"
    property color borderColor: "#8a6810"
    property var midiControlRouter: null
    property var midiTarget: ({})
    property bool midiBindingGesture: false
    property int midiMoveCount: 0
    property double midiPressStarted: 0

    readonly property bool midiBound: {
        if (root.midiControlRouter === null)
            return false
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.isControlTargetBound(root.midiTarget)
    }

    signal edited(real value)
    signal activated()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        if (!learned)
            root.midiControlRouter.controlTargetTapped(root.midiTarget)
        return learned
    }

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right

        text:
            root.label
            + " "
            + Number(slider.value).toFixed(
                root.decimals
            )

        color: root.textColor
        font.pixelSize: 13
        font.bold: true
        elide: Text.ElideRight
    }

    Slider {
        id: slider

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 30

        from: root.fromValue
        to: root.toValue
        stepSize: root.stepValue
        value: root.currentValue
        live: true
        snapMode: Slider.SnapAlways

        onPressedChanged: {
            if (pressed) {
                root.midiMoveCount = 0
                root.midiPressStarted = Date.now()
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.midiBindingGesture = false
            }
        }

        onMoved: {
            if (root.midiBindingGesture)
                return
            root.midiMoveCount += 1
            if (
                root.midiControlRouter !== null
                && (
                    root.midiMoveCount >= 2
                    || Date.now() - root.midiPressStarted >= 180
                )
            ) {
                root.midiControlRouter.controlTargetMoved(root.midiTarget)
            }
            root.edited(value)
        }

        background: Rectangle {
            x: slider.leftPadding
            y:
                slider.topPadding
                + slider.availableHeight / 2
                - height / 2
            width: slider.availableWidth
            height: 8
            radius: 4
            color: root.trackColor

            Rectangle {
                width:
                    slider.visualPosition
                    * parent.width
                height: parent.height
                radius: 4
                color: root.fillColor
            }
        }

        handle: Rectangle {
            x:
                slider.leftPadding
                + slider.visualPosition
                * (
                    slider.availableWidth
                    - width
                )
            y:
                slider.topPadding
                + slider.availableHeight / 2
                - height / 2
            width: 19
            height: 19
            radius: 10
            color: root.midiBound ? "#35b85a" : root.handleColor
            border.color: root.borderColor
            border.width: 2
        }
    }
}
