import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string label: ""
    property real currentValue: 0
    property real fromValue: 0
    property real toValue: 1
    property real stepValue: 0.01
    property int decimals: 2

    property color textColor: "#4c3b08"
    property color trackColor: "#eee2a5"
    property color fillColor: "#c59518"
    property color handleColor: "#fffbea"
    property color borderColor: "#8a6810"

    signal edited(real value)

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right

        text:
            root.label
            + " "
            + Number(slider.value).toFixed(
                root.decimals
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
        height: 30

        from: root.fromValue
        to: root.toValue
        stepSize: root.stepValue
        value: root.currentValue
        live: true
        snapMode: Slider.SnapAlways

        onMoved:
            root.edited(value)

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
            width: 19
            height: 19
            radius: 10
            color: root.handleColor
            border.color: root.borderColor
            border.width: 2
        }
    }
}
