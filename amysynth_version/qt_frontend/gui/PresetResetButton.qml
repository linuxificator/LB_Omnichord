import QtQuick
import QtQuick.Controls

Button {
    id: root

    property color panelColor: "#d7d7d2"
    property color borderColor: "#85857f"
    property color textColor: "#343432"
    property var midiControlRouter: null
    property var midiTarget: ({})

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

    function midiButtonHandled() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        if (learned)
            return true
        return root.midiControlRouter.midiButtonTargetBlocked(root.midiTarget)
    }

    width: 52
    height: 52

    font.pixelSize: 11
    font.bold: true

    contentItem: Text {
        text: root.text
        color: root.enabled ? root.textColor : "#686864"
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: width / 2
        color: root.enabled
            ? (root.pressed ? Qt.darker(root.panelColor, 1.08) : root.panelColor)
            : "#bdbdb8"
        border.color: root.enabled ? root.borderColor : "#85857f"
        border.width: 2
    }

    Rectangle {
        visible: root.midiControlRouter !== null
        anchors.horizontalCenter: parent.horizontalCenter
        y: 4
        width: 8
        height: 8
        radius: 4
        color: {
            if (root.midiVisualState === "preset-displaced")
                return "#f22b2b"
            if (root.midiVisualState === "preset-incoming")
                return "#3186d7"
            return root.midiBound ? "#35b85a" : "#a5a5a0"
        }

        SequentialAnimation on opacity {
            running: root.midiPresetFeedback
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 0.2; duration: 110 }
            NumberAnimation { from: 0.2; to: 1.0; duration: 110 }
        }
    }
}
