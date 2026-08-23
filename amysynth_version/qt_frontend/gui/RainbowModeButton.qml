import QtQuick
import QtQuick.Controls

Button {
    id: root

    // The mode switch intentionally projects one chord-row indent farther to
    // the right than the CHORD ON/OFF button below the chord-type rail.
    // Keeping that 30 px extension inside this shared component gives MIDI and
    // OMNI exactly the same geometry without duplicating the rainbow styling.
    property int extensionWidth: 30

    font.pixelSize: 17
    font.bold: true

    contentItem: Item {
        Text {
            x: 0
            y: 0
            width: root.width + root.extensionWidth
            height: root.height
            text: root.text
            color: "#ffffff"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            style: Text.Outline
            styleColor: "#402a36"
        }
    }

    background: Rectangle {
        width: root.width + root.extensionWidth
        height: root.height
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

    // Extend the hit area together with the visible button. The normal Button
    // keeps ownership of its original area; this covers only the extra indent.
    MouseArea {
        x: root.width
        y: 0
        width: root.extensionWidth
        height: root.height
        onClicked: root.clicked()
    }
}
