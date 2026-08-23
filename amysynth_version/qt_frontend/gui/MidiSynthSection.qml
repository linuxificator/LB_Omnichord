import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var synthModel

    property int leftRailWidth: 64
    property int contentX: 64
    property int volumeX: 0
    property int volumeWidth: 52
    property int wheelWidth: 150

    property color panelColor: "#dcecf7"
    property color borderColor: "#8bb9d8"
    property color accentColor: "#2f7fb4"
    property color textColor: "#17212a"

    property int selectedSynthIndex: 0
    // UI convention is MIDI channels 1..16; index 16 is omni/all (A).
    property int channelIndex: 0
    property real volumeValue: 0.5

    property real brightnessValue: 0.5
    property real modulationValue: 0.0
    property real detuneValue: 0.0
    property real attackValue: 0.05
    property real sustainValue: 0.75
    property real releaseValue: 0.25

    signal interacted(color barColor)

    function markInteraction() {
        root.interacted(root.panelColor)
    }

    function resetUi() {
        root.selectedSynthIndex = 0
        synthWheel.currentIndex = 0
        root.brightnessValue = 0.5
        root.modulationValue = 0.0
        root.detuneValue = 0.0
        root.attackValue = 0.05
        root.sustainValue = 0.75
        root.releaseValue = 0.25
        root.volumeValue = 0.5
        root.markInteraction()
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: root.panelColor
        border.color: root.borderColor
        border.width: 1
    }

    PresetResetButton {
        x: (root.leftRailWidth - width) / 2
        y: (root.height - height) / 2
        width: 50
        height: 50
        text: "RST"
        panelColor: Qt.lighter(root.panelColor, 1.05)
        borderColor: root.borderColor
        textColor: root.textColor
        onClicked: root.resetUi()
    }

    Frame {
        id: wheelFrame

        x: root.contentX
        y: 0
        width: root.wheelWidth
        height: parent.height
        padding: 0

        background: Rectangle {
            radius: 10
            color: Qt.lighter(root.accentColor, 1.45)
            border.color: root.borderColor
            border.width: 1
        }

        Tumbler {
            id: synthWheel

            anchors.fill: parent
            anchors.margins: 3
            model: root.synthModel
            visibleItemCount: 3
            wrap: true
            flickDeceleration: 1200

            property bool initialized: false

            Component.onCompleted: {
                currentIndex = root.selectedSynthIndex
                Qt.callLater(function() {
                    synthWheel.initialized = true
                })
            }

            delegate: Item {
                required property var modelData
                required property int index

                width: synthWheel.width
                height: synthWheel.height / synthWheel.visibleItemCount

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: modelData
                    color: root.textColor
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize:
                        Math.abs(Tumbler.displacement) < 0.5 ? 18 : 15
                    font.bold:
                        Math.abs(Tumbler.displacement) < 0.5
                    opacity:
                        0.30
                        + Math.max(
                            0,
                            1 - Math.abs(Tumbler.displacement)
                        ) * 0.70
                }

                TapHandler {
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: synthWheel.currentIndex = index
                }
            }

            onCurrentIndexChanged: {
                if (initialized && currentIndex >= 0) {
                    root.selectedSynthIndex = currentIndex
                    root.markInteraction()
                }
            }
        }

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height / 2 - 16
            width: parent.width - 12
            height: 32
            radius: 7
            color: "transparent"
            border.color: Qt.darker(root.accentColor, 1.25)
            border.width: 2
        }
    }

    Button {
        id: channelButton

        x: root.contentX + root.wheelWidth + 7
        y: (parent.height - height) / 2
        width: 62
        height: 62
        text:
            root.channelIndex < 16
            ? String(root.channelIndex + 1)
            : "A"
        font.pixelSize: 20
        font.bold: true

        contentItem: Text {
            text: channelButton.text
            color: root.textColor
            font: channelButton.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: width / 2
            color:
                channelButton.pressed
                ? Qt.darker(root.panelColor, 1.12)
                : Qt.lighter(root.panelColor, 1.05)
            border.color: root.accentColor
            border.width: 2
        }

        onClicked: {
            root.channelIndex = (root.channelIndex + 1) % 17
            root.markInteraction()
        }
    }

    Column {
        id: sliderColumn

        x: channelButton.x + channelButton.width + 10
        y: 0
        width: root.volumeX - x - 8
        height: parent.height
        spacing: 8

        Row {
            width: parent.width
            height: (parent.height - sliderColumn.spacing) / 2
            spacing: 8

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "BRI"
                currentValue: root.brightnessValue
                fromValue: 0
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.brightnessValue = value
                    root.markInteraction()
                }
            }

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "MOD"
                currentValue: root.modulationValue
                fromValue: 0
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.modulationValue = value
                    root.markInteraction()
                }
            }

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "DET"
                currentValue: root.detuneValue
                fromValue: -1
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.detuneValue = value
                    root.markInteraction()
                }
            }
        }

        Row {
            width: parent.width
            height: (parent.height - sliderColumn.spacing) / 2
            spacing: 8

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "ATK"
                currentValue: root.attackValue
                fromValue: 0
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.attackValue = value
                    root.markInteraction()
                }
            }

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "SUS"
                currentValue: root.sustainValue
                fromValue: 0
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.sustainValue = value
                    root.markInteraction()
                }
            }

            LabeledSlider {
                width: (parent.width - 16) / 3
                height: parent.height
                label: "REL"
                currentValue: root.releaseValue
                fromValue: 0
                toValue: 1
                stepValue: 0.01
                decimals: 2
                textColor: root.textColor
                trackColor: Qt.lighter(root.panelColor, 1.08)
                fillColor: root.accentColor
                handleColor: "#ffffff"
                borderColor: Qt.darker(root.accentColor, 1.2)
                onEdited: (value) => {
                    root.releaseValue = value
                    root.markInteraction()
                }
            }
        }
    }

    VerticalVolume {
        x: root.volumeX
        y: 0
        width: root.volumeWidth
        height: parent.height
        currentValue: root.volumeValue
        panelColor: Qt.lighter(root.panelColor, 1.03)
        panelBorderColor: root.borderColor
        fillColor: root.accentColor
        textColor: root.textColor

        onEdited: (value) => {
            root.volumeValue = value
            root.markInteraction()
        }
    }
}
