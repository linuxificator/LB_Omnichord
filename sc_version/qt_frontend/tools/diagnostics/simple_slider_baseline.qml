import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: window
    width: 640
    height: 220
    visible: true
    title: "LB Omnichord simple slider baseline"

    property real lastMovedValue: slider.value
    property int moveCount: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Label {
            Layout.fillWidth: true
            text: "Plain Qt Quick Slider. Hold the round handle with the mouse and drag left/right."
            wrapMode: Text.WordWrap
            font.pixelSize: 16
        }

        Slider {
            id: slider
            Layout.fillWidth: true
            from: 0
            to: 100
            value: 25
            live: true

            onMoved: {
                window.lastMovedValue = value
                window.moveCount += 1
                console.log(
                    "slider moved",
                    value,
                    "moveCount",
                    window.moveCount
                )
            }
        }

        Label {
            Layout.fillWidth: true
            text: "value " + slider.value.toFixed(1)
                  + " / moved " + window.lastMovedValue.toFixed(1)
                  + " / move events " + window.moveCount
            font.pixelSize: 16
        }

        Label {
            Layout.fillWidth: true
            text: "Expected: while the mouse button remains down, the handle follows continuous horizontal motion."
            wrapMode: Text.WordWrap
        }
    }
}
