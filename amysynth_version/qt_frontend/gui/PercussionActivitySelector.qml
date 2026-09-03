pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    property int currentLevel: 1
    property var fillEnabled: [false, false, false, false, false]
    property color textColor: "#4c3b08"
    property color groupColor: "#f5df78"
    property color idleColor: "#f7e9a8"
    property color selectedColor: "#bc8410"
    property color borderColor: "#96720f"
    property color selectedTextColor: "#fff9dd"
    property var midiControlRouter: null
    property var activityMidiTargetForLevel: null
    property var fillMidiTargetForIndex: null

    signal activitySelected(int level)
    signal fillToggled(int fillIndex)

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: root.groupColor
        border.color: root.borderColor
        border.width: 1
        opacity: 0.92
    }

    Text {
        id: title
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 4
        text: "percussion activity / fills"
        color: root.textColor
        font.pixelSize: 11
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }

    Column {
        id: rows
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        anchors.margins: 5
        anchors.topMargin: 4
        spacing: 4

        Row {
            id: activityRow
            width: parent.width
            height: (rows.height - rows.spacing) / 2
            spacing: 4

            Repeater {
                id: activityRepeater
                model: 5

                Button {
                    id: activityButton
                    required property int index
                    width:
                        (activityRow.width
                         - (activityRepeater.count - 1) * activityRow.spacing)
                        / activityRepeater.count
                    height: activityRow.height
                    text: String(index + 1)
                    property bool selectedState:
                        root.currentLevel === index + 1
                    property var midiTarget:
                        root.activityMidiTargetForLevel === null
                        ? ({})
                        : root.activityMidiTargetForLevel(index + 1)
                    font.pixelSize: 13
                    font.bold: true
                    contentItem: Text {
                        text: activityButton.text
                        color: activityButton.selectedState
                            ? root.selectedTextColor : root.textColor
                        font: activityButton.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 6
                        color: activityButton.selectedState
                            ? root.selectedColor
                            : (activityButton.pressed ? "#e1ca6a" : root.idleColor)
                        border.color: root.borderColor
                        border.width: activityButton.selectedState ? 2 : 1
                    }
                    MidiButtonLed {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 3
                        z: 2
                        midiControlRouter: root.midiControlRouter
                        midiTarget: activityButton.midiTarget
                    }
                    onClicked: root.activitySelected(index + 1)
                }
            }
        }

        Row {
            id: fillRow
            width: parent.width
            height: (rows.height - rows.spacing) / 2
            spacing: 4

            Repeater {
                id: fillRepeater
                model: 5

                Button {
                    id: fillButton
                    required property int index
                    width:
                        (fillRow.width
                         - (fillRepeater.count - 1) * fillRow.spacing)
                        / fillRepeater.count
                    height: fillRow.height
                    text: "F" + String(index + 1)
                    property bool selectedState:
                        root.fillEnabled.length > index
                        && Boolean(root.fillEnabled[index])
                    property var midiTarget:
                        root.fillMidiTargetForIndex === null
                        ? ({})
                        : root.fillMidiTargetForIndex(index)
                    font.pixelSize: 12
                    font.bold: true
                    contentItem: Text {
                        text: fillButton.text
                        color: fillButton.selectedState
                            ? root.selectedTextColor : root.textColor
                        font: fillButton.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 6
                        color: fillButton.selectedState
                            ? root.selectedColor
                            : (fillButton.pressed ? "#e1ca6a" : root.idleColor)
                        border.color: root.borderColor
                        border.width: fillButton.selectedState ? 2 : 1
                    }
                    MidiButtonLed {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 3
                        z: 2
                        midiControlRouter: root.midiControlRouter
                        midiTarget: fillButton.midiTarget
                    }
                    onClicked: root.fillToggled(index)
                }
            }
        }
    }
}
