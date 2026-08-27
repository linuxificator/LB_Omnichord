import QtQuick
import QtQuick.Controls

Button {
    id: root

    // The mode switch intentionally projects one chord-row indent farther to
    // the right than the CHORD ON/OFF button below the chord-type rail.
    property int extensionWidth: 30
    property var midiControlRouter: null
    property string bindingLocationScreen: ""

    padding: 0
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    font.pixelSize: height * 0.55
    font.bold: true

    contentItem: Item {
        x: 0
        y: 0
        width: root.width + root.extensionWidth
        height: root.height

        Text {
            width: root.width
            height: root.height
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: root.extensionWidth / 2
            text: root.text
            color: "#ffffff"
            font: root.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            style: Text.Outline
            styleColor: "#402a36"
        }

        MidiBindingLocationLed {
            x: 9
            anchors.verticalCenter: parent.verticalCenter
            width: 10
            height: 10
            radius: width / 2
            z: 2
            midiControlRouter: root.midiControlRouter
            targetScreen: root.bindingLocationScreen
            locationEnabled: root.bindingLocationScreen.length > 0
        }
    }

    background: Rectangle {
        x: 0
        y: 0
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

    MouseArea {
        x: root.width
        y: 0
        width: root.extensionWidth
        height: root.height
        onClicked: root.clicked()
    }
}
