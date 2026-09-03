pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    property int currentLevel: 1
    property bool arpeggioEnabled: false
    property int arpeggioRate: 1
    property bool arpeggioDescending: false
    property string directionLabel:
        arpeggioDescending ? "D" : "U"

    property color textColor: "#4c3b08"
    property color groupColor: "#f8e9a1"
    property color idleColor: "#faefbd"
    property color selectedColor: "#cb981d"
    property color borderColor: "#96720f"
    property color selectedTextColor: "#fff9dd"
    property var midiControlRouter: null
    property var activityMidiTargetForLevel: null
    property var arpeggioMidiTarget: ({})
    property var rateMidiTargetForRate: null
    property var directionMidiTarget: ({})

    signal activitySelected(int level)
    signal arpeggioToggled()
    signal rateSelected(int rate)
    signal directionToggled()

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

        text: "chord activity"
        color: root.textColor
        font.pixelSize: 11
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }

    Column {
        id: buttonRows

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: title.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        anchors.topMargin: 4
        anchors.bottomMargin: 5
        spacing: 4

        Row {
            id: topRow

            width: parent.width
            height: (buttonRows.height - buttonRows.spacing) / 2
            spacing: 4

            Repeater {
                id: topRepeater
                model: 5

                Button {
                    id: topButton

                    required property int index

                    width:
                        (
                            topRow.width
                            - (topRepeater.count - 1) * topRow.spacing
                        ) / topRepeater.count
                    height: topRow.height
                    text: index < 4 ? String(index + 1) : "A"

                    property bool selectedState:
                        index < 4
                        ? root.currentLevel === index + 1
                        : root.arpeggioEnabled
                    property var midiTarget:
                        index < 4
                        ? (
                            root.activityMidiTargetForLevel === null
                            ? ({})
                            : root.activityMidiTargetForLevel(index + 1)
                        )
                        : root.arpeggioMidiTarget

                    font.pixelSize: 13
                    font.bold: true

                    contentItem: Text {
                        text: topButton.text
                        color:
                            topButton.selectedState
                            ? root.selectedTextColor
                            : root.textColor
                        font: topButton.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: 6
                        color:
                            topButton.selectedState
                            ? root.selectedColor
                            : (
                                topButton.pressed
                                ? "#e1ca6a"
                                : root.idleColor
                            )
                        border.color: root.borderColor
                        border.width: topButton.selectedState ? 2 : 1
                    }

                    MidiButtonLed {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 3
                        z: 2
                        midiControlRouter: root.midiControlRouter
                        midiTarget: topButton.midiTarget
                    }

                    onClicked: {
                        if (index < 4) {
                            root.activitySelected(index + 1)
                        } else {
                            root.arpeggioToggled()
                        }
                    }
                }
            }
        }

        Row {
            id: bottomRow

            width: parent.width
            height: (buttonRows.height - buttonRows.spacing) / 2
            spacing: 4

            Repeater {
                id: bottomRepeater
                model: 5

                Button {
                    id: bottomButton

                    required property int index

                    width:
                        (
                            bottomRow.width
                            - (bottomRepeater.count - 1) * bottomRow.spacing
                        ) / bottomRepeater.count
                    height: bottomRow.height
                    text:
                        index < 4
                        ? "/" + String(index + 1)
                        : root.directionLabel

                    property bool selectedState:
                        index < 4
                        ? root.arpeggioRate === index + 1
                        : root.arpeggioDescending
                    property var midiTarget:
                        index < 4
                        ? (
                            root.rateMidiTargetForRate === null
                            ? ({})
                            : root.rateMidiTargetForRate(index + 1)
                        )
                        : root.directionMidiTarget

                    font.pixelSize: 13
                    font.bold: true

                    contentItem: Text {
                        text: bottomButton.text
                        color:
                            bottomButton.selectedState
                            ? root.selectedTextColor
                            : root.textColor
                        font: bottomButton.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: 6
                        color:
                            bottomButton.selectedState
                            ? root.selectedColor
                            : (
                                bottomButton.pressed
                                ? "#e1ca6a"
                                : root.idleColor
                            )
                        border.color: root.borderColor
                        border.width: bottomButton.selectedState ? 2 : 1
                    }

                    MidiButtonLed {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 3
                        z: 2
                        midiControlRouter: root.midiControlRouter
                        midiTarget: bottomButton.midiTarget
                    }

                    onClicked: {
                        if (index < 4) {
                            root.rateSelected(index + 1)
                        } else {
                            root.directionToggled()
                        }
                    }
                }
            }
        }
    }
}
