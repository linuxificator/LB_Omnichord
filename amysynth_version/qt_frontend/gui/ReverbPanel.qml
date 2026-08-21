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

    component PinkRow: Item {
        id: row
        required property string labelText
        required property real currentValue
        required property var editFunction

        Text {
            x: 6
            width: 42
            anchors.verticalCenter: parent.verticalCenter
            text: row.labelText
            color: "#6b3048"
            font.pixelSize: 10
            font.bold: true
            horizontalAlignment: Text.AlignRight
        }

        Slider {
            id: slider
            x: 54
            width: parent.width - 96
            anchors.verticalCenter: parent.verticalCenter
            height: 22
            from: 0
            to: 1
            stepSize: 0.01
            value: row.currentValue
            live: true
            snapMode: Slider.SnapAlways
            onMoved: row.editFunction(value)

            background: Rectangle {
                x: slider.leftPadding
                y: slider.topPadding + slider.availableHeight / 2 - height / 2
                width: slider.availableWidth
                height: 6
                radius: 3
                color: "#e8b7ca"

                Rectangle {
                    width: slider.visualPosition * parent.width
                    height: parent.height
                    radius: 3
                    color: "#d87fa5"
                }
            }

            handle: Rectangle {
                x: slider.leftPadding
                   + slider.visualPosition * (slider.availableWidth - width)
                y: slider.topPadding + slider.availableHeight / 2 - height / 2
                width: 15
                height: 15
                radius: 8
                color: "#fff7fb"
                border.color: "#a75f7d"
                border.width: 2
            }
        }

        Text {
            anchors.right: parent.right
            width: 36
            anchors.verticalCenter: parent.verticalCenter
            text: Number(row.currentValue).toFixed(2)
            color: "#6b3048"
            font.pixelSize: 9
            horizontalAlignment: Text.AlignLeft
        }
    }

    Column {
        x: 3
        y: 3
        width: parent.width - 72
        height: parent.height - 6
        spacing: 0

        PinkRow {
            width: parent.width
            height: parent.height / 3
            labelText: "LEV"
            currentValue: root.controller.reverbLevel
            editFunction: root.updateLevel
        }

        PinkRow {
            width: parent.width
            height: parent.height / 3
            labelText: "LIVE"
            currentValue: root.controller.reverbLiveness
            editFunction: root.updateLiveness
        }

        PinkRow {
            width: parent.width
            height: parent.height / 3
            labelText: "DAMP"
            currentValue: root.controller.reverbDamping
            editFunction: root.updateDamping
        }
    }

    Button {
        id: drumButton
        width: 56
        height: 56
        x: parent.width - width - 8
        anchors.verticalCenter: parent.verticalCenter
        text: "DRM"
        font.pixelSize: 12
        font.bold: true

        contentItem: Text {
            text: drumButton.text
            color: root.controller.reverbDrumsIncluded ? "#ffffff" : "#6b3048"
            font: drumButton.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: width / 2
            color: root.controller.reverbDrumsIncluded
                   ? "#b64f7a"
                   : (drumButton.pressed ? "#d48aa8" : "#efbfd1")
            border.color: root.controller.reverbDrumsIncluded ? "#7e294d" : "#b96e8d"
            border.width: root.controller.reverbDrumsIncluded ? 3 : 2
        }

        onClicked: root.controller.toggleReverbDrums()
    }
}
