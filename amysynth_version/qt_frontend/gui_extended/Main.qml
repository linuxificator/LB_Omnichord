import QtQuick
import QtQuick.Controls
import "../gui" as Base

Base.Main {
    id: rootWindow

    // Reproduce the base layout transform so this small architectural overlay
    // remains aligned in fullscreen, scaled-to-fit and normal window modes.
    readonly property real gateScale:
        scaleToFit
        ? Math.min(
            Math.max(1, width - 16) / (strumX + strumWidth),
            Math.max(1, height - 16) / totalControlHeight
        )
        : 1.0
    readonly property real gateViewportWidth: Math.max(1, width - 16)
    readonly property real gateViewportHeight: Math.max(1, height - 16)
    readonly property real gateContentX:
        8 + Math.max(
            0,
            (gateViewportWidth - (strumX + strumWidth) * gateScale) / 2
        )
    readonly property real gateContentY:
        8 + Math.max(
            0,
            (gateViewportHeight - totalControlHeight * gateScale) / 2
        )

    Item {
        id: titleOverlay
        x: rootWindow.gateContentX + 520 * rootWindow.gateScale
        y: rootWindow.gateContentY
        width:
            (rootWindow.strumX + rootWindow.strumWidth - 520)
            * rootWindow.gateScale
        height: rootWindow.titleHeight * rootWindow.gateScale
        z: 5000
        visible: rootWindow.titleHeight > 0

        Item {
            width: rootWindow.strumX + rootWindow.strumWidth - 520
            height: rootWindow.titleHeight
            scale: rootWindow.gateScale
            transformOrigin: Item.TopLeft

            readonly property int gatePanelX:
                Math.max(250, rootWindow.strumX - 360 - 520)

            // Cover the original title only. Reverb remains untouched at x<520.
            Rectangle {
                anchors.fill: parent
                color: rootWindow.color
            }

            Text {
                x: 12
                y: 0
                width: Math.max(0, parent.gatePanelX - 24)
                height: parent.height
                text: headerTitleText
                color: "#493a38"
                font.family: headerTitleFont
                font.pixelSize: Math.max(14, parent.height * 0.62)
                font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Rectangle {
                id: gatePanel
                x: parent.gatePanelX
                y: 0
                width: parent.width - x
                height: parent.height
                color: "#dcecf8"
                border.color: "#2474b8"
                border.width: 1
                radius: 10

                // The panel extends all the way over the title cell above the
                // strum strip, so its blue field visually joins that section.

                Button {
                    id: gatedButton
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    width: 56
                    height: 56
                    text: "GTD"
                    font.pixelSize: 14
                    font.bold: true
                    checkable: true
                    checked: backend.strumGateEnabled

                    background: Rectangle {
                        radius: width / 2
                        color:
                            backend.strumGateEnabled
                            ? "#2474b8"
                            : "#a9c9e2"
                        border.color: "#15598f"
                        border.width: 2
                    }
                    contentItem: Text {
                        text: gatedButton.text
                        color:
                            backend.strumGateEnabled
                            ? "#ffffff"
                            : "#173b58"
                        font: gatedButton.font
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: backend.toggleStrumGate()
                }

                QtObject {
                    id: attackControl
                    property string key: "strum_gate_attack"
                    property string label: "ATT"
                    property real value: backend.strumGateAttack
                    property real minimum: 0.0
                    property real maximum: 1.0
                    property real step: 0.01
                    property int decimals: 2
                    property string unit: ""
                    property string scale: "linear"
                }

                QtObject {
                    id: sustainControl
                    property string key: "strum_gate_sustain"
                    property string label: "SUS"
                    property real value: backend.strumGateSustain
                    property real minimum: 0.0
                    property real maximum: 1.0
                    property real step: 0.01
                    property int decimals: 2
                    property string unit: ""
                    property string scale: "linear"
                }

                Base.ParameterSlider {
                    x: 78
                    y: 10
                    width: 145
                    height: Math.max(44, parent.height - 20)
                    control: attackControl
                    enabled: backend.strumGateEnabled
                    opacity: enabled ? 1.0 : 0.38
                    textColor: "#173b58"
                    trackColor: "#b8d5ea"
                    fillColor: "#2474b8"
                    handleColor: "#eef8ff"
                    borderColor: "#15598f"
                    onEdited: (key, value) => backend.setStrumGateAttack(value)
                }

                Base.ParameterSlider {
                    x: 233
                    y: 10
                    width: 145
                    height: Math.max(44, parent.height - 20)
                    control: sustainControl
                    enabled: backend.strumGateEnabled
                    opacity: enabled ? 1.0 : 0.38
                    textColor: "#173b58"
                    trackColor: "#b8d5ea"
                    fillColor: "#2474b8"
                    handleColor: "#eef8ff"
                    borderColor: "#15598f"
                    onEdited: (key, value) => backend.setStrumGateSustain(value)
                }
            }
        }
    }
}
