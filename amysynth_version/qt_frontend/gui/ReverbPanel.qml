import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var controller

    Rectangle {
        anchors.fill: parent
        radius: 11
        color: "#f7dce6"
        border.color: "#c98da5"
        border.width: 1
    }

    function updateLevel(value) {
        root.controller.setReverbLevel(value)
    }

    function updateLiveness(value) {
        root.controller.setReverbLiveness(value)
    }

    function updateDamping(value) {
        root.controller.setReverbDamping(value)
    }

    // Reuse the large touch target and press/hold behavior of the section
    // volume controls.  The three reverb controls are deliberately arranged
    // side by side rather than as thin stacked horizontal sliders.
    component PinkControl: Item {
        id: control

        required property string labelText
        required property real currentValue
        required property var editFunction

        Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 14

            text: control.labelText
            color: "#6b3048"
            font.pixelSize: 10
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        VerticalVolume {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: 14

            currentValue: control.currentValue
            panelColor: "#f3c9d9"
            panelBorderColor: "#bd7694"
            fillColor: "#d36f99"
            textColor: "#6b3048"

            onEdited: function(value) {
                control.editFunction(value)
            }
        }
    }

    Row {
        id: controlsRow

        x: 4
        y: 3
        width: parent.width - 8
        height: parent.height - 6
        spacing: 4

        PinkControl {
            width: 94
            height: parent.height
            labelText: "LEV"
            currentValue: root.controller.reverbLevel
            editFunction: root.updateLevel
        }

        PinkControl {
            width: 94
            height: parent.height
            labelText: "LIVE"
            currentValue: root.controller.reverbLiveness
            editFunction: root.updateLiveness
        }

        PinkControl {
            width: 94
            height: parent.height
            labelText: "DAMP"
            currentValue: root.controller.reverbDamping
            editFunction: root.updateDamping
        }

        Item {
            width: 56
            height: parent.height

            Button {
                id: drumButton

                width: 56
                height: 56
                anchors.centerIn: parent

                text: "DRM"
                font.pixelSize: 12
                font.bold: true

                contentItem: Text {
                    text: drumButton.text
                    color:
                        root.controller.reverbDrumsIncluded
                        ? "#ffffff"
                        : "#6b3048"
                    font: drumButton.font
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: width / 2
                    color:
                        root.controller.reverbDrumsIncluded
                        ? "#b64f7a"
                        : (
                            drumButton.pressed
                            ? "#d48aa8"
                            : "#efbfd1"
                        )
                    border.color:
                        root.controller.reverbDrumsIncluded
                        ? "#7e294d"
                        : "#b96e8d"
                    border.width:
                        root.controller.reverbDrumsIncluded
                        ? 3
                        : 2
                }

                onClicked:
                    root.controller.toggleReverbDrums()
            }
        }
    }
}
