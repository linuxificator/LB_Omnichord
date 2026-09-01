import QtQuick

Item {
    id: root

    required property var noteModel
    readonly property real markerSize: Math.min(34, width - 4)
    readonly property real verticalMargin: 5

    Repeater {
        id: noteRepeater
        model: root.noteModel

        delegate: Rectangle {
            required property var modelData
            required property int index

            width: root.markerSize
            height: width
            radius: width / 2
            x: (root.width - width) / 2
            y: {
                const availableHeight =
                    root.height - 2 * root.verticalMargin - height
                if (noteRepeater.count <= 1)
                    return (root.height - height) / 2
                return root.verticalMargin
                    + index * availableHeight / (noteRepeater.count - 1)
            }
            color: "#dcecf7"
            border.color: "#8bb9d8"
            border.width: 1

            Text {
                anchors.fill: parent
                text: String(modelData)
                color: "#08243d"
                font.pixelSize: 15
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
