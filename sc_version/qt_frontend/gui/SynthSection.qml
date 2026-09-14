pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var controller
    required property var midiControlRouter

    property string role: "chord"
    readonly property bool showTransport: role === "bass"

    property color wheelColor: "#78a57c"
    property color wheelBorderColor: "#476b4b"
    property color wheelTextColor: "#102417"
    property color selectionColor: "#315b39"

    property color commonTextColor: "#102417"
    property color commonTrackColor: "#c5d8c9"
    property color commonFillColor: "#426f4c"
    property color commonHandleColor: "#f4fff5"
    property color commonBorderColor: "#315b39"

    property color extraTextColor: "#16301e"
    property color extraTrackColor: "#d8eadb"
    property color extraFillColor: "#77ad82"
    property color extraHandleColor: "#f4fff5"
    property color extraBorderColor: "#4d8759"

    readonly property int selectedIndex:
        role === "strum"
        ? controller.selectedStrumSynthIndex
        : (
            role === "bass"
            ? controller.selectedBassSynthIndex
            : controller.selectedChordSynthIndex
        )

    readonly property string synthKind: {
        const revision = root.selectedIndex
        return root.controller.synthKind(root.role)
    }
    readonly property var browserModel: {
        const revision = root.selectedIndex
        return root.controller.synthBrowserNames(root.role)
    }
    readonly property int browserIndex: {
        const revision = root.selectedIndex
        return root.controller.synthBrowserIndex(root.role)
    }
    readonly property var sampleColumns: {
        const revision = root.selectedIndex
        return root.controller.sampleChoiceColumns(root.role)
    }

    readonly property var commonControls:
        role === "strum"
        ? controller.strumCommonControls
        : (
            role === "bass"
            ? controller.bassCommonControls
            : controller.chordCommonControls
        )

    readonly property var extraControls:
        role === "strum"
        ? controller.strumExtraControls
        : (
            role === "bass"
            ? controller.bassExtraControls
            : controller.chordExtraControls
        )

    function setBrowserIndex(index) {
        root.controller.setSynthBrowserIndex(root.role, index)
    }

    function setControl(key, value) {
        if (root.role === "strum") {
            root.controller.editStrumSynthControl(
                key,
                value
            )
        } else if (root.role === "bass") {
            root.controller.editBassSynthControl(
                key,
                value
            )
        } else {
            root.controller.editChordSynthControl(
                key,
                value
            )
        }
    }

    function synchronizeWheel() {
        if (!synthWheel.initialized) {
            return
        }

        if (
            synthWheel.currentIndex
            !== root.browserIndex
        ) {
            synthWheel.syncingFromBackend = true
            synthWheel.currentIndex =
                root.browserIndex

            Qt.callLater(function() {
                synthWheel.syncingFromBackend =
                    false
            })
        }
    }

    Frame {
        id: wheelFrame

        x: 0
        y: 0
        width: 150
        height: parent.height
        padding: 0

        background: Rectangle {
            radius: 10
            color: root.wheelColor
            border.color: root.wheelBorderColor
            border.width: 1
        }

        Tumbler {
            id: synthWheel

            anchors.fill: parent
            anchors.margins: 3

            model: root.browserModel
            visibleItemCount: 3
            wrap: true

            property bool initialized: false
            property bool syncingFromBackend: false

            Component.onCompleted: {
                syncingFromBackend = true
                currentIndex = root.browserIndex

                Qt.callLater(function() {
                    synthWheel.syncingFromBackend =
                        false
                    synthWheel.initialized = true
                })
            }

            Connections {
                target: root.controller

                function onChordSynthStateChanged() {
                    if (root.role === "chord") {
                        root.synchronizeWheel()
                    }
                }

                function onStrumSynthStateChanged() {
                    if (root.role === "strum") {
                        root.synchronizeWheel()
                    }
                }

                function onBassSynthStateChanged() {
                    if (root.role === "bass") {
                        root.synchronizeWheel()
                    }
                }

                function onBassRunningChanged() {
                    if (root.role === "bass") {
                        bassTransportSymbol.requestPaint()
                    }
                }
            }

            delegate: Item {
                id: synthItem
                required property var modelData
                required property int index

                width: synthWheel.width
                height:
                    synthWheel.height
                    / synthWheel.visibleItemCount

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: synthItem.modelData
                    color: root.wheelTextColor
                    elide: Text.ElideRight
                    horizontalAlignment:
                        Text.AlignHCenter
                    verticalAlignment:
                        Text.AlignVCenter

                    font.pixelSize:
                        Math.abs(
                            Tumbler.displacement
                        ) < 0.5 ? 18 : 15

                    font.bold:
                        Math.abs(
                            Tumbler.displacement
                        ) < 0.5

                    opacity:
                        0.30
                        + Math.max(
                            0,
                            1 - Math.abs(
                                Tumbler.displacement
                            )
                        ) * 0.70
                }

                TapHandler {
                    gesturePolicy: TapHandler.DragThreshold

                    onTapped:
                        synthWheel.currentIndex = synthItem.index
                }
            }

            onCurrentIndexChanged: {
                if (
                    initialized
                    && !syncingFromBackend
                    && currentIndex >= 0
                ) {
                    root.setBrowserIndex(
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
            border.color: root.selectionColor
            border.width: 2
        }
    }

    Button {
        id: bassTransportButton
        visible: root.showTransport
        x: wheelFrame.width + 7
        y: (parent.height - height) / 2
        width: 62
        height: 62
        contentItem: Canvas {
            id: bassTransportSymbol
            anchors.fill: parent
            onPaint: {
                const c = getContext("2d"); c.reset()
                c.fillStyle = root.controller.bassRunning ? "#f5f5f3" : "#30302e"
                if (root.controller.bassRunning) {
                    const side = 19; c.fillRect((width-side)/2,(height-side)/2,side,side)
                } else {
                    c.beginPath(); c.moveTo(width/2-9,height/2-14); c.lineTo(width/2+15,height/2); c.lineTo(width/2-9,height/2+14); c.closePath(); c.fill()
                }
            }
        }
        background: Rectangle {
            radius: 31
            color: root.controller.bassRunning ? "#666662" : "#c7c7c2"
            border.color: "#555552"
            border.width: 2
        }
        onClicked: root.controller.toggleBassRunning()
    }

    Rectangle {
        visible: root.showTransport
            && root.controller.synthSupportsRiffArticulation(root.role)
        anchors.horizontalCenter: bassTransportButton.horizontalCenter
        y: 5
        width: 8
        height: 8
        radius: 4
        color: "#ef8c22"
        border.color: "#9a4e08"
        border.width: 1
        z: 4
    }

    Column {
        x: root.showTransport ? bassTransportButton.x + bassTransportButton.width + 10 : wheelFrame.width + 6
        y: 0
        width: parent.width - x
        height: parent.height
        spacing: 8

        Item {
            visible: root.synthKind !== "sample"
            width: parent.width
            height: (parent.height - 8) / 2

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
                                - (
                                    Math.max(
                                        1,
                                        extraRepeater.count
                                    ) - 1
                                ) * extraRow.spacing
                            )
                            / Math.max(
                                1,
                                extraRepeater.count
                            )
                        height: extraRow.height

                        control: modelData
                        textColor:
                            root.extraTextColor
                        trackColor:
                            root.extraTrackColor
                        fillColor:
                            root.extraFillColor
                        handleColor:
                            root.extraHandleColor
                        borderColor:
                            root.extraBorderColor
                        midiControlRouter:
                            root.midiControlRouter
                        midiTarget: ({
                            "screen": "omni",
                            "kind": "synth_control",
                            "role": root.role,
                            "control": modelData.key
                        })

                        onEdited: (key, value) =>
                            root.setControl(key, value)
                    }
                }
            }
        }

        Item {
            visible: root.synthKind !== "sample"
            width: parent.width
            height: (parent.height - 8) / 2

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
                                - (
                                    commonRepeater.count - 1
                                ) * commonRow.spacing
                            )
                            / commonRepeater.count
                        height: commonRow.height

                        control: modelData
                        textColor:
                            root.commonTextColor
                        trackColor:
                            root.commonTrackColor
                        fillColor:
                            root.commonFillColor
                        handleColor:
                            root.commonHandleColor
                        borderColor:
                            root.commonBorderColor
                        midiControlRouter:
                            root.midiControlRouter
                        midiTarget: ({
                            "screen": "omni",
                            "kind": "synth_control",
                            "role": root.role,
                            "control": modelData.key
                        })

                        onEdited: (key, value) =>
                            root.setControl(key, value)
                    }
                }
            }
        }
    }

    Row {
        id: sampleChoiceRow
        visible: root.synthKind === "sample"
        x: root.showTransport
            ? bassTransportButton.x + bassTransportButton.width + 10
            : wheelFrame.width + 6
        y: 0
        width: parent.width - x
        height: parent.height
        spacing: 8

        Repeater {
            id: sampleColumnRepeater
            model: root.sampleColumns

            delegate: Column {
                id: sampleColumn
                required property var modelData
                width: (
                    sampleChoiceRow.width
                    - Math.max(0, sampleColumnRepeater.count - 1)
                        * sampleChoiceRow.spacing
                ) / Math.max(1, sampleColumnRepeater.count)
                height: sampleChoiceRow.height
                spacing: 8

                Button {
                    width: parent.width
                    height: 48
                    visible: sampleColumn.modelData.showVariant
                    text: sampleColumn.modelData.label
                    font.pixelSize: 12
                    font.bold: sampleColumn.modelData.selected
                    background: Rectangle {
                        radius: 8
                        color: sampleColumn.modelData.selected ? "#d39a43" : "#e9d7b5"
                        border.color: "#865d20"
                        border.width: sampleColumn.modelData.selected ? 2 : 1
                    }
                    onClicked: {
                        const choices = sampleColumn.modelData.choices
                        if (choices.length > 0)
                            root.controller.selectSampleChoice(
                                root.role, choices[0].synthIndex
                            )
                    }
                }

                Row {
                    width: parent.width
                    height: 48
                    spacing: 4
                    Repeater {
                        id: articulationRepeater
                        model: sampleColumn.modelData.choices.length > 1
                            ? sampleColumn.modelData.choices : []
                        delegate: Button {
                            id: articulationButton
                            required property var modelData
                            width: (
                                sampleColumn.width
                                - Math.max(0, articulationRepeater.count - 1) * 4
                            ) / Math.max(1, articulationRepeater.count)
                            height: 48
                            text: articulationButton.modelData.label
                            font.pixelSize: 11
                            font.bold: articulationButton.modelData.selected
                            background: Rectangle {
                                radius: 8
                                color: articulationButton.modelData.selected
                                    ? "#d39a43" : "#efe3cc"
                                border.color: "#865d20"
                                border.width: articulationButton.modelData.selected ? 2 : 1
                            }
                            onClicked: root.controller.selectSampleChoice(
                                root.role, articulationButton.modelData.synthIndex
                            )
                        }
                    }
                }
            }
        }
    }
}
