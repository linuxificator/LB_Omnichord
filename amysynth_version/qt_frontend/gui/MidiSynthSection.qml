import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var controller
    required property int rowIndex
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

    signal interacted(int rowIndex)

    readonly property int selectedSynthIndex: {
        root.controller.stateVersion
        return root.controller.synthIndex(root.rowIndex)
    }

    readonly property var commonControls: {
        root.controller.stateVersion
        return root.controller.commonControls(root.rowIndex)
    }

    readonly property var extraControls: {
        root.controller.stateVersion
        return root.controller.extraControls(root.rowIndex)
    }

    function markInteraction() {
        root.interacted(root.rowIndex)
    }

    function synchronizeWheel() {
        if (!synthWheel.initialized) {
            return
        }
        const wanted = root.controller.synthIndex(root.rowIndex)
        if (synthWheel.currentIndex !== wanted) {
            synthWheel.syncing = true
            synthWheel.currentIndex = wanted
            Qt.callLater(function() {
                synthWheel.syncing = false
            })
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: root.panelColor
        border.color: root.borderColor
        border.width: 1
    }

    // A press anywhere in this coloured section makes this row the preview
    // source. Pointer handlers can observe the press without stealing the
    // grab from the actual button/tumbler/slider underneath it.
    TapHandler {
        gesturePolicy: TapHandler.DragThreshold
        onPressedChanged: {
            if (pressed)
                root.markInteraction()
        }
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
        onClicked: {
            root.controller.resetRow(root.rowIndex)
            root.markInteraction()
        }
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

            property bool initialized: false
            property bool syncing: false

            Component.onCompleted: {
                syncing = true
                currentIndex = root.selectedSynthIndex
                Qt.callLater(function() {
                    synthWheel.syncing = false
                    synthWheel.initialized = true
                })
            }

            Connections {
                target: root.controller
                function onStateChanged() {
                    root.synchronizeWheel()
                }
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
                if (
                    initialized
                    && !syncing
                    && currentIndex >= 0
                ) {
                    root.controller.setSynthIndex(
                        root.rowIndex,
                        currentIndex
                    )
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
        text: {
            root.controller.stateVersion
            const channel = root.controller.channel(root.rowIndex)
            return channel === 0 ? "A" : String(channel)
        }
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
            root.controller.cycleChannel(root.rowIndex)
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

        Item {
            width: parent.width
            height: (parent.height - sliderColumn.spacing) / 2

            Row {
                id: extraRow
                anchors.fill: parent
                spacing: 8

                Repeater {
                    id: extraRepeater
                    model: root.extraControls

                    delegate: ParameterSlider {
                        required property var modelData

                        width:
                            (
                                extraRow.width
                                - (extraRepeater.count - 1) * extraRow.spacing
                            ) / extraRepeater.count
                        height: extraRow.height
                        control: modelData
                        textColor: root.textColor
                        trackColor: Qt.lighter(root.panelColor, 1.08)
                        fillColor: root.accentColor
                        handleColor: "#ffffff"
                        borderColor: Qt.darker(root.accentColor, 1.2)
                        midiControlRouter: root.controller
                        midiTarget: ({
                            "screen": "midi",
                            "kind": "synth_control",
                            "row": root.rowIndex,
                            "control": modelData.key
                        })

                        onActivated: root.markInteraction()
                        onEdited: (key, value) => {
                            root.controller.setControl(
                                root.rowIndex,
                                key,
                                value
                            )
                            root.markInteraction()
                        }
                    }
                }
            }
        }

        Item {
            width: parent.width
            height: (parent.height - sliderColumn.spacing) / 2

            Row {
                id: commonRow
                anchors.fill: parent
                spacing: 8

                Repeater {
                    id: commonRepeater
                    model: root.commonControls

                    delegate: ParameterSlider {
                        required property var modelData

                        width:
                            (
                                commonRow.width
                                - (commonRepeater.count - 1) * commonRow.spacing
                            ) / commonRepeater.count
                        height: commonRow.height
                        control: modelData
                        textColor: root.textColor
                        trackColor: Qt.lighter(root.panelColor, 1.08)
                        fillColor: root.accentColor
                        handleColor: "#ffffff"
                        borderColor: Qt.darker(root.accentColor, 1.2)
                        midiControlRouter: root.controller
                        midiTarget: ({
                            "screen": "midi",
                            "kind": "synth_control",
                            "row": root.rowIndex,
                            "control": modelData.key
                        })

                        onActivated: root.markInteraction()
                        onEdited: (key, value) => {
                            root.controller.setControl(
                                root.rowIndex,
                                key,
                                value
                            )
                            root.markInteraction()
                        }
                    }
                }
            }
        }
    }

    VerticalVolume {
        x: root.volumeX
        y: 0
        width: root.volumeWidth
        height: parent.height
        currentValue: {
            root.controller.stateVersion
            return root.controller.volume(root.rowIndex)
        }
        panelColor: Qt.lighter(root.panelColor, 1.03)
        panelBorderColor: root.borderColor
        fillColor: root.accentColor
        textColor: root.textColor
        midiControlRouter: root.controller
        midiTarget: ({
            "screen": "midi",
            "kind": "volume",
            "row": root.rowIndex
        })

        onEdited: (value) => {
            root.controller.setVolume(root.rowIndex, value)
            root.markInteraction()
        }
    }
}
