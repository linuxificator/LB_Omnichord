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
        color: root.textColor
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: width / 2
        color: root.pressed ? Qt.darker(root.panelColor, 1.08) : root.panelColor
        border.color: root.borderColor
        border.width: 2
    }
}
