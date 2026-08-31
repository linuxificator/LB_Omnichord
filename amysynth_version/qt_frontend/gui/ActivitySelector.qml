import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string label: "activity"
    property int currentLevel: 1
    property var levels: [1, 2, 3, 4]
    property var levelLabels: []

    property color textColor: "#4c3b08"
    property color groupColor: "#f7ebae"
    property color idleColor: "#f3e5a5"
    property color selectedColor: "#c79214"
    property color borderColor: "#96720f"
    property color selectedTextColor: "#fff9dd"
    property var midiControlRouter: null
    property var midiTargetForLevel: null

    signal selected(int level)

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: root.groupColor
        border.color: root.borderColor
        border.width: 1
        opacity: 0.92
    }

    Text {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 4

        text: root.label
        color: root.textColor
        font.pixelSize: 11
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }

    Row {
        id: buttonRow

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 5

        height: 29
        spacing: 4

        Repeater {
            id: levelRepeater
            model: root.levels

            Button {
                id: levelButton

                required property var modelData
                required property int index

                width:
                    (
                        buttonRow.width
                        - (
                            levelRepeater.count - 1
                        ) * buttonRow.spacing
                    )
                    / Math.max(
                        1,
                        levelRepeater.count
                    )

                height: buttonRow.height
                text:
                    root.levelLabels.length > index
                    ? String(root.levelLabels[index])
                    : String(modelData)

                property bool selectedState:
                    root.currentLevel
                    === Number(modelData)
                property var midiTarget:
                    root.midiTargetForLevel === null
                    ? ({})
                    : root.midiTargetForLevel(Number(modelData))

                font.pixelSize: 13
                font.bold: true

                contentItem: Text {
                    text: parent.text
                    color:
                        parent.selectedState
                        ? root.selectedTextColor
                        : root.textColor
                    font: parent.font
                    horizontalAlignment:
                        Text.AlignHCenter
                    verticalAlignment:
                        Text.AlignVCenter
                }

                background: Rectangle {
                    radius: 6
                    color:
                        parent.selectedState
                        ? root.selectedColor
                        : (
                            parent.pressed
                            ? "#e1ca6a"
                            : root.idleColor
                        )
                    border.color: root.borderColor
                    border.width:
                        parent.selectedState ? 2 : 1
                }

                MidiButtonLed {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 3
                    z: 2
                    midiControlRouter: root.midiControlRouter
                    midiTarget: levelButton.midiTarget
                }

                onClicked:
                    root.selected(
                        Number(modelData)
                    )
            }
        }
    }
}
