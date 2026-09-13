import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "../../gui"

Window {
    id: window
    width: 960
    height: 420
    visible: true
    title: "LB Omnichord layout slider baseline"

    property real currentValue: 25
    property real delayedValue: 25
    property real lastEditedValue: currentValue
    property int editCount: 0

    Timer {
        id: delayedEcho
        interval: 250
        repeat: false
        onTriggered: window.delayedValue = window.lastEditedValue
    }

    Flickable {
        id: viewport
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        readonly property bool scaleToFit: true
        readonly property real fittedScale:
            scaleToFit
            ? Math.min(width / contentArea.implicitWidth,
                       height / contentArea.implicitHeight)
            : 1.0

        interactive: !scaleToFit
        flickableDirection: Flickable.HorizontalAndVerticalFlick
        contentWidth: Math.max(width, contentArea.implicitWidth * fittedScale)
        contentHeight: Math.max(height, contentArea.implicitHeight * fittedScale)
        boundsBehavior: Flickable.StopAtBounds

        Item {
            id: contentArea
            implicitWidth: 1300
            implicitHeight: 520
            x: Math.max(0, (viewport.width - implicitWidth * viewport.fittedScale) / 2)
            y: Math.max(0, (viewport.height - implicitHeight * viewport.fittedScale) / 2)
            scale: viewport.fittedScale
            transformOrigin: Item.TopLeft

            Rectangle {
                anchors.fill: parent
                color: "#f6f0df"
                border.color: "#c8b989"
            }

            Text {
                x: 32
                y: 24
                text: "Main.qml-like viewport: Flickable + scaled contentArea, no backend/MIDI/AMY"
                font.pixelSize: 24
                color: "#3d3423"
            }

            LabeledSlider {
                id: immediate
                x: 60
                y: 100
                width: 520
                height: 70
                label: "immediate echo"
                fromValue: 0
                toValue: 100
                stepValue: 1
                decimals: 0
                currentValue: window.currentValue

                onEdited: (value) => {
                    window.currentValue = value
                    window.lastEditedValue = value
                    window.editCount += 1
                    console.log("immediate slider edited", value, window.editCount)
                }
            }

            LabeledSlider {
                id: delayed
                x: 60
                y: 200
                width: 520
                height: 70
                label: "delayed backend echo"
                fromValue: 0
                toValue: 100
                stepValue: 1
                decimals: 0
                currentValue: window.delayedValue

                onEdited: (value) => {
                    window.lastEditedValue = value
                    window.editCount += 1
                    delayedEcho.restart()
                    console.log("delayed slider edited", value, window.editCount)
                }
            }

            Text {
                x: 60
                y: 300
                width: 700
                text: "Drag both round handles. Immediate echo mimics normal QML state. Delayed echo mimics backend lag during drag."
                      + " Last edited: " + window.lastEditedValue.toFixed(1)
                      + " / edit events: " + window.editCount
                wrapMode: Text.WordWrap
                font.pixelSize: 22
                color: "#3d3423"
            }
        }
    }
}
