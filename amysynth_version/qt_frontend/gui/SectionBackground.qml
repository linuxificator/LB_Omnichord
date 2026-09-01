import QtQuick

Rectangle {
    property int leftExtension: 0
    property int contentWidth: 0
    property int frameHeight: 0

    x: -leftExtension
    width: leftExtension + contentWidth
    height: frameHeight
    radius: 12
    color: "#f4c77f"
    border.color: "#bd7517"
    border.width: 1
}
