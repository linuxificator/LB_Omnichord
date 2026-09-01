import QtQuick

Item {
    id: root

    required property string titleText
    required property string titleFont
    required property int titleHeight
    required property int titleX
    required property int titleWidth
    required property int strumPanelX
    required property int presetRowHeight
    required property int strumWidth
    required property bool ladderMode
    required property var midiControlRouter

    signal strumModeToggleRequested()

    Text {
        x: root.titleX
        width: root.titleWidth
        height: parent.height
        text: root.titleText
        color: "#493a38"
        font.family: root.titleFont
        font.pixelSize: Math.max(14, root.titleHeight * 0.62)
        font.weight: Font.Medium
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
        maximumLineCount: 1
    }

    Rectangle {
        x: root.strumPanelX
        anchors.bottom: parent.bottom
        width: root.presetRowHeight + root.strumWidth
        height: root.presetRowHeight
        color: "#dcecf7"
        radius: 12
        border.color: "#8bb9d8"

        PresetResetButton {
            anchors.left: parent.left
            anchors.leftMargin: (root.presetRowHeight - width) / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 48
            height: 48
            text: root.ladderMode ? "LDR" : "APG"
            panelColor: "#5d9fd0"
            borderColor: "#2f648c"
            textColor: "#071c2c"
            midiControlRouter: root.midiControlRouter
            midiTarget: ({
                "screen": "omni",
                "kind": "button",
                "action": "strum_ladder"
            })
            onClicked: root.strumModeToggleRequested()
        }
    }
}
