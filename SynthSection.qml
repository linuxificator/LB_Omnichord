import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var controller
    required property var synthModel

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

    function setSynthIndex(index) {
        if (root.role === "strum") {
            root.controller.setStrumSynthIndex(index)
        } else if (root.role === "bass") {
            root.controller.setBassSynthIndex(index)
        } else {
            root.controller.setChordSynthIndex(index)
        }
    }

    function setControl(key, value) {
        if (root.role === "strum") {
            root.controller.setStrumSynthControl(
                key,
                value
            )
        } else if (root.role === "bass") {
            root.controller.setBassSynthControl(
                key,
                value
            )
        } else {
            root.controller.setChordSynthControl(
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
            !== root.selectedIndex
        ) {
            synthWheel.syncingFromBackend = true
            synthWheel.currentIndex =
                root.selectedIndex

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

            model: root.synthModel
            visibleItemCount: 3
            wrap: true
            flickDeceleration: 1200

            property bool initialized: false
            property bool syncingFromBackend: false

            Component.onCompleted: {
                syncingFromBackend = true
                currentIndex = root.selectedIndex

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
                required property var modelData
                required property int index

                width: synthWheel.width
                height:
                    synthWheel.height
                    / synthWheel.visibleItemCount

                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: modelData
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
                        synthWheel.currentIndex = index
                }
            }

            onCurrentIndexChanged: {
                if (
                    initialized
                    && !syncingFromBackend
                    && currentIndex >= 0
                ) {
                    root.setSynthIndex(
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

    Column {
        x: root.showTransport ? bassTransportButton.x + bassTransportButton.width + 10 : wheelFrame.width + 6
        y: 0
        width: parent.width - x
        height: parent.height
        spacing: 8

        Item {
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

                        onEdited:
                            root.setControl(key, value)
                    }
                }
            }
        }

        Item {
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

                        onEdited:
                            root.setControl(key, value)
                    }
                }
            }
        }
    }
}
