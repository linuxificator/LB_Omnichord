import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var control

    property color textColor: "#102417"
    property color trackColor: "#c5d8c9"
    property color fillColor: "#426f4c"
    property color handleColor: "#f4fff5"
    property color borderColor: "#315b39"

    signal edited(string key, real value)

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right

        text:
            root.control.label
            + " "
            + Number(slider.value).toFixed(
                root.control.decimals
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
        height: 28

        from: root.control.minimum
        to: root.control.maximum
        stepSize: root.control.step
        value: root.control.value
        live: true

        onMoved:
            root.edited(
                root.control.key,
                value
            )

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
            width: 18
            height: 18
            radius: 9
            color: root.handleColor
            border.color: root.borderColor
            border.width: 2
        }
    }
}
