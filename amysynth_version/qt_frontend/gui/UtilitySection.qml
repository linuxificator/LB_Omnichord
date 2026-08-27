import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: root

    required property var controller
    required property var tuningModeModel
    required property bool fullScreen
    property int leftExtension: 0
    property bool tuningCoupled: true
    property int tuningRowHeight: height
    property int presetRowY: 0
    property int presetRowHeight: height

    signal toggleFullscreenRequested()
    signal toggleTuningCouplingRequested()

    readonly property int wheelWidth: 150
    readonly property int tuningX: 231
    readonly property int tuningWidth: 52
    readonly property int utilityGap: 8
    readonly property int panicWidth: 76
    readonly property int escapeWidth: 72

    readonly property int panicX:
        tuningX + tuningWidth + utilityGap
    readonly property int escapeX:
        panicX + panicWidth + utilityGap
    property int presetX:
        escapeX + escapeWidth + utilityGap

    function synchronizeTuningWheel() {
        if (!tuningWheel.initialized) {
            return
        }

        if (
            tuningWheel.currentIndex
            !== controller.selectedTuningModeIndex
        ) {
            tuningWheel.syncingFromBackend = true
            tuningWheel.currentIndex =
                controller.selectedTuningModeIndex

            Qt.callLater(
                function() {
                    tuningWheel.syncingFromBackend =
                        false
                }
            )
        }
    }

    // Orange area deliberately ends at the tuning tap-control.
    Rectangle {
        x: -root.leftExtension
        y: 0
        width: root.leftExtension + root.tuningX + root.tuningWidth
        height: root.tuningRowHeight
        radius: 12
        color: "#f4c77f"
        border.color: "#bd7517"
        border.width: 1
    }

    TuningLinkButton {
        x: root.wheelWidth + 7
        y: 8
        width:
            root.tuningX
            - root.wheelWidth
            - 14
        height: root.tuningRowHeight - 16
        coupled: root.tuningCoupled
        onClicked: {
            if (root.tuningCoupled) {
                root.controller.setMidiTuningCoupled(false)
                root.toggleTuningCouplingRequested()
            } else {
                if (root.controller.coupleTuningFromOmni())
                    root.toggleTuningCouplingRequested()
            }
        }
    }

    Frame {
        id: tuningWheelFrame

        x: 0
        y: 0
        width: root.wheelWidth
        height: root.tuningRowHeight
        padding: 0

        background: Rectangle {
            radius: 10
            color: "#e99d43"
            border.color: "#a65c0a"
            border.width: 1
        }

        Tumbler {
            id: tuningWheel

            anchors.fill: parent
            anchors.margins: 3
            model: root.tuningModeModel
            visibleItemCount: 3
            wrap: true

            property bool initialized: false
            property bool syncingFromBackend: false

            Component.onCompleted: {
                syncingFromBackend = true
                currentIndex =
                    root.controller
                        .selectedTuningModeIndex

                Qt.callLater(
                    function() {
                        tuningWheel.syncingFromBackend =
                            false
                        tuningWheel.initialized = true
                    }
                )
            }

            Connections {
                target: root.controller

                function onTuningChanged() {
                    root.synchronizeTuningWheel()
                }
            }

            delegate: Item {
                required property var modelData
                required property int index

                width: tuningWheel.width
                height:
                    tuningWheel.height
                    / tuningWheel.visibleItemCount

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: modelData
                    color: "#482507"
                    horizontalAlignment:
                        Text.AlignHCenter
                    verticalAlignment:
                        Text.AlignVCenter
                    font.pixelSize:
                        Math.abs(
                            Tumbler.displacement
                        ) < 0.5 ? 19 : 15
                    font.bold:
                        Math.abs(
                            Tumbler.displacement
                        ) < 0.5
                    opacity:
                        0.34
                        + Math.max(
                            0,
                            1 - Math.abs(
                                Tumbler.displacement
                            )
                        ) * 0.66
                }

                TapHandler {
                    gesturePolicy:
                        TapHandler.DragThreshold

                    onTapped:
                        tuningWheel.currentIndex =
                            index
                }
            }

            onCurrentIndexChanged: {
                if (
                    initialized
                    && !syncingFromBackend
                    && currentIndex >= 0
                ) {
                    root.controller
                        .setTuningModeIndex(
                            currentIndex
                        )
                }
            }
        }

        Rectangle {
            anchors.horizontalCenter:
                parent.horizontalCenter
            y: parent.height / 2 - 16
            width: parent.width - 12
            height: 32
            radius: 7
            color: "transparent"
            border.color: "#844400"
            border.width: 2
        }
    }

    TapNumber {
        x: root.tuningX
        y: 0
        width: root.tuningWidth
        height: root.tuningRowHeight

        currentValue:
            root.controller.tuningReference
        fromValue: 415
        toValue: 466
        stepValue: 1

        panelColor: "#efb05c"
        panelBorderColor: "#a75d0a"
        fillColor: "#cc6f0c"
        textColor: "#492606"
        midiControlRouter: root.controller.midiPlayer
        midiTarget: ({
            "screen": "omni",
            "kind": "tuning_reference"
        })

        onEdited:
            root.controller
                .setTuningReference(value)
    }

    Button {
        id: panicButton

        x: root.panicX
        y: 8
        width: root.panicWidth
        height: root.tuningRowHeight - 16

        text: "PNC!"
        font.pixelSize: 18
        font.bold: true

        contentItem: Text {
            text: panicButton.text
            color: "#ffffff"
            font: panicButton.font
            horizontalAlignment:
                Text.AlignHCenter
            verticalAlignment:
                Text.AlignVCenter
        }

        background: Rectangle {
            radius: 9
            color:
                panicButton.pressed
                ? "#bd0000"
                : "#f11616"
            border.color: "#850000"
            border.width: 2
        }

        onClicked:
            root.controller.panic()
    }

    Button {
        id: escapeButton

        x: root.escapeX
        y: 8
        width: root.escapeWidth
        height: root.tuningRowHeight - 16

        text:
            root.fullScreen
            ? "ESC"
            : "FSC"
        font.pixelSize: 17
        font.bold: true

        contentItem: Text {
            text: escapeButton.text
            color: "#6b1f1f"
            font: escapeButton.font
            horizontalAlignment:
                Text.AlignHCenter
            verticalAlignment:
                Text.AlignVCenter
        }

        background: Rectangle {
            radius: 9
            color:
                escapeButton.pressed
                ? "#df9292"
                : "#f3c0c0"
            border.color: "#bd7474"
            border.width: 2
        }

        onClicked:
            root.toggleFullscreenRequested()
    }

    Rectangle {
        id: presetPanel

        x: root.presetX
        y: root.presetRowY
        width: parent.width - x
        height: root.presetRowHeight
        radius: 12
        color: "#e8dcf5"
        border.color: "#9270b6"
        border.width: 1

        Button {
            id: storeButton

            x: 8
            anchors.verticalCenter:
                parent.verticalCenter
            width: 48
            height: 48

            text: "STR"
            font.pixelSize: 18
            font.bold: true

            contentItem: Text {
                text: storeButton.text
                color: "#ffffff"
                font: storeButton.font
                horizontalAlignment:
                    Text.AlignHCenter
                verticalAlignment:
                    Text.AlignVCenter
            }

            background: Rectangle {
                radius: width / 2
                color:
                    storeButton.pressed
                    ? "#522476"
                    : "#6f3599"
                border.color: "#3f195e"
                border.width: 2
            }

            onClicked:
                root.controller
                    .storeSelectedPreset()
        }

        Row {
            id: presetButtons

            x: storeButton.x
               + storeButton.width
               + 6
            anchors.verticalCenter:
                parent.verticalCenter
            spacing: 6

            Repeater {
                model:
                    root.controller.presetCount

                delegate: Button {
                    id: presetButton

                    required property int index

                    property int presetNumber:
                        index + 1
                    property bool selected:
                        root.controller
                            .selectedPreset
                        === presetNumber
                    property bool storeFlash:
                        false

                    width: 48
                    height: 48

                    text:
                        "P" + presetNumber
                    font.pixelSize: 12
                    font.bold: true

                    contentItem: Text {
                        text: presetButton.text
                        color:
                            presetButton.selected
                            ? "#ffffff"
                            : "#4c286d"
                        font: presetButton.font
                        horizontalAlignment:
                            Text.AlignHCenter
                        verticalAlignment:
                            Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: width / 2
                        color:
                            presetButton.storeFlash
                            ? "#d78cff"
                            : (
                                presetButton.pressed
                                ? "#70408e"
                                : (
                                    presetButton.selected
                                    ? "#8c50b9"
                                    : "#d1b9e6"
                                )
                            )
                        border.color:
                            presetButton.storeFlash
                            ? "#ffffff"
                            : (
                                presetButton.selected
                                ? "#f0ddff"
                                : "#8e6bab"
                            )
                        border.width:
                            (
                                presetButton.selected
                                || presetButton.storeFlash
                            )
                            ? 3 : 1
                    }

                    Timer {
                        id: storeFlashTimer

                        interval: 520
                        repeat: false

                        onTriggered:
                            presetButton.storeFlash =
                                false
                    }

                    Connections {
                        target: root.controller

                        function onPresetStored(
                            presetNumber
                        ) {
                            if (
                                presetNumber
                                === presetButton
                                    .presetNumber
                            ) {
                                presetButton.storeFlash =
                                    true
                                storeFlashTimer.restart()
                            }
                        }
                    }

                    // Intentionally reloads even when this is already the
                    // selected preset.
                    onClicked:
                        root.controller
                            .selectPreset(
                                presetNumber
                            )
                }
            }
        }
    }
}
