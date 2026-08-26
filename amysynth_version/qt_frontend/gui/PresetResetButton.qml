import QtQuick
import QtQuick.Controls

Button {
    id: root

    property color panelColor: "#d7d7d2"
    property color borderColor: "#85857f"
    property color textColor: "#343432"

    width: 52
    height: 52

    font.pixelSize: 11
    font.bold: true

    contentItem: Text {
        text: root.text
        color: root.enabled ? root.textColor : "#686864"
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: width / 2
        color: root.enabled
            ? (root.pressed ? Qt.darker(root.panelColor, 1.08) : root.panelColor)
            : "#bdbdb8"
        border.color: root.enabled ? root.borderColor : "#85857f"
        border.width: 2
    }
}
