import QtQuick
import QtQuick.Controls

Button {
    id: root

    property int channel: 1
    property color panelColor: "#ffffff"
    property color pressedPanelColor: "#dddddd"
    property color borderColor: "#000000"
    property real borderWidth: 2
    property color textColor: "#000000"
    property bool showMidiLed: false
    property var midiControlRouter: null
    property var midiTarget: ({})

    width: 62
    height: 62
    padding: 0
    text: root.channel === 0 ? "A" : String(root.channel)
    font.pixelSize: 20
    font.bold: true

    contentItem: Text {
        text: root.text
        color: root.textColor
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        objectName: "midiChannelButtonFace"
        radius: width / 2
        color: root.pressed ? root.pressedPanelColor : root.panelColor
        border.color: root.borderColor
        border.width: root.borderWidth
    }

    Item {
        visible: root.showMidiLed
        anchors.horizontalCenter: parent.horizontalCenter
        y: 7
        width: 8
        height: 8
        z: 2

        MidiButtonLed {
            anchors.fill: parent
            midiControlRouter: root.midiControlRouter
            midiTarget: root.midiTarget
        }
    }
}
