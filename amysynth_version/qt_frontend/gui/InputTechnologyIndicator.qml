import QtQuick

Item {
    id: root

    required property var technology

    objectName: String(technology.key) + "InputTechnologyIndicator"
    width: techText.implicitWidth + 20
    height: 22

    Rectangle {
        id: techLed
        objectName: String(root.technology.key) + "InputTechnologyLed"
        visible:
            root.technology.state !== "listening"
            || Boolean(root.technology.idleLedVisible)
        x: 0
        anchors.verticalCenter: parent.verticalCenter
        width: 11
        height: 11
        radius: 5.5
        color:
            root.technology.state === "unavailable"
            ? "#c73434"
            : "#35b85a"
        border.width: 1
        border.color:
            root.technology.state === "unavailable"
            ? "#7e1c1c"
            : "#1d7738"

        SequentialAnimation on opacity {
            running: root.technology.state === "activity"
            loops: Animation.Infinite
            NumberAnimation {
                from: 1.0
                to: 0.25
                duration: 90
            }
            NumberAnimation {
                from: 0.25
                to: 1.0
                duration: 90
            }
        }
    }

    Text {
        id: techText
        objectName: String(root.technology.key) + "InputTechnologyLabel"
        x: 17
        anchors.verticalCenter: parent.verticalCenter
        text: root.technology.label
        color: "#363632"
        font.pixelSize: 13
        font.weight: Font.Medium
    }
}
