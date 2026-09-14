import QtQuick

Item {
    id: root
    required property var controller
    required property string role
    required property int stateIndex
    property color panelColor: "#d0d0cc"
    property color borderColor: "#7b7b76"
    property color textColor: "#303030"

    readonly property string mode: {
        const revision = root.stateIndex
        return root.controller.synthKind(root.role)
    }

    width: 46
    height: 96

    PresetResetButton {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: 42
        height: 42
        text: root.mode === "sample" ? "PCM" : "SYN"
        panelColor: root.mode === "sample"
            ? Qt.darker(root.panelColor, 1.16) : root.panelColor
        borderColor: root.borderColor
        textColor: root.textColor
        onClicked: root.controller.toggleSynthKind(root.role)
    }

    PresetResetButton {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: 42
        height: 42
        text: "RST"
        panelColor: root.panelColor
        borderColor: root.borderColor
        textColor: root.textColor
        onClicked: {
            if (root.role === "bass")
                root.controller.resetBassToPreset()
            else if (root.role === "strum")
                root.controller.resetStrumToPreset()
            else
                root.controller.resetChordSynthToPreset()
        }
    }
}
