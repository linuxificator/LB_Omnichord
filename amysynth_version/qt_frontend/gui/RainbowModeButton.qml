import QtQuick
import QtQuick.Controls

Button {
    id: root

    font.pixelSize: 17
    font.bold: true

    contentItem: Text {
        text: root.text
        color: "#ffffff"
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        style: Text.Outline
        styleColor: "#402a36"
    }

    background: Rectangle {
        radius: 9
        border.color: "#6a5264"
        border.width: root.pressed ? 3 : 2
        opacity: root.pressed ? 0.78 : 1.0

        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.00; color: "#d84e5f" }
            GradientStop { position: 0.20; color: "#e8903c" }
            GradientStop { position: 0.40; color: "#dec947" }
            GradientStop { position: 0.60; color: "#55a968" }
            GradientStop { position: 0.80; color: "#428ac4" }
            GradientStop { position: 1.00; color: "#8454aa" }
        }
    }
}
