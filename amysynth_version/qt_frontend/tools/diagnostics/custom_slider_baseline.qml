import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../../gui"

Window {
    id: window
    width: 640
    height: 220
    visible: true
    title: "LB Omnichord custom slider baseline"

    property real currentValue: 25
    property real lastEditedValue: currentValue
    property int editCount: 0

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 24

        Label {
            Layout.fillWidth: true
            text: "LB LabeledSlider only. Hold the round handle with the mouse and drag left/right."
            wrapMode: Text.WordWrap
            font.pixelSize: 16
        }

        LabeledSlider {
            id: labeled
            Layout.fillWidth: true
            height: 70
            label: "custom"
            fromValue: 0
            toValue: 100
            stepValue: 1
            decimals: 0
            currentValue: window.currentValue

            onEdited: (value) => {
                window.currentValue = value
                window.lastEditedValue = value
                window.editCount += 1
                console.log(
                    "custom slider edited",
                    value,
                    "editCount",
                    window.editCount
                )
            }
        }

        Label {
            Layout.fillWidth: true
            text: "current " + window.currentValue.toFixed(1)
                  + " / edited " + window.lastEditedValue.toFixed(1)
                  + " / edit events " + window.editCount
            font.pixelSize: 16
        }

        Label {
            Layout.fillWidth: true
            text: "Expected: behavior matches the plain Qt Slider baseline. If this fails while the plain baseline works, the custom LabeledSlider component is the problem."
            wrapMode: Text.WordWrap
        }
    }
}
