import QtQuick
import QtQuick.Controls

Item {
    id: root
    required property var controller
    required property var rhythmModel
    property color wheelColor: "#d9b743"
    property color wheelBorderColor: "#8e7012"
    property color wheelTextColor: "#3e3006"
    property color selectionColor: "#80620b"

    function synchronizeWheel() {
        if (!rhythmWheel.initialized) return
        if (rhythmWheel.currentIndex !== controller.selectedRhythmIndex) {
            rhythmWheel.syncingFromBackend = true
            rhythmWheel.currentIndex = controller.selectedRhythmIndex
            Qt.callLater(function() { rhythmWheel.syncingFromBackend = false })
        }
    }

    Frame {
        id: wheelFrame
        x: 0; y: 0; width: 150; height: parent.height; padding: 0
        background: Rectangle { radius: 10; color: root.wheelColor; border.color: root.wheelBorderColor; border.width: 1 }
        Tumbler {
            id: rhythmWheel
            anchors.fill: parent; anchors.margins: 3
            model: root.rhythmModel; visibleItemCount: 3; wrap: true
            property bool initialized: false
            property bool syncingFromBackend: false
            Component.onCompleted: {
                syncingFromBackend = true
                currentIndex = root.controller.selectedRhythmIndex
                Qt.callLater(function() { rhythmWheel.syncingFromBackend = false; rhythmWheel.initialized = true })
            }
            Connections {
                target: root.controller
                function onRhythmStateChanged() { root.synchronizeWheel() }
            }
            delegate: Item {
                required property var modelData
                required property int index
                width: rhythmWheel.width
                height: rhythmWheel.height / rhythmWheel.visibleItemCount
                Text {
                    anchors.centerIn: parent; width: parent.width - 10
                    text: modelData; color: root.wheelTextColor; elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    font.pixelSize: Math.abs(Tumbler.displacement) < 0.5 ? 18 : 15
                    font.bold: Math.abs(Tumbler.displacement) < 0.5
                    opacity: 0.32 + Math.max(0, 1 - Math.abs(Tumbler.displacement)) * 0.68
                }

                TapHandler {
                    gesturePolicy: TapHandler.DragThreshold

                    onTapped:
                        rhythmWheel.currentIndex = index
                }
            }
            onCurrentIndexChanged: {
                if (initialized && !syncingFromBackend && currentIndex >= 0)
                    root.controller.setRhythmIndex(currentIndex)
            }
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height / 2 - 16; width: parent.width - 12; height: 32
            radius: 7; color: "transparent"; border.color: root.selectionColor; border.width: 2
        }
    }

    Button {
        id: runButton
        x: wheelFrame.width + 7; y: (parent.height - height) / 2; width: 62; height: 62
        contentItem: Canvas {
            id: rhythmTransportSymbol
            anchors.fill: parent

            onPaint: {
                const c = getContext("2d")
                c.reset()
                c.fillStyle = root.controller.rhythmRunning
                    ? "#fff8d5" : "#3e3006"
                if (root.controller.rhythmRunning) {
                    const side = 19
                    c.fillRect(
                        (width - side) / 2,
                        (height - side) / 2,
                        side,
                        side
                    )
                } else {
                    // Match the geometrically centered bass transport arrow.
                    c.beginPath()
                    c.moveTo(width / 2 - 9, height / 2 - 14)
                    c.lineTo(width / 2 + 15, height / 2)
                    c.lineTo(width / 2 - 9, height / 2 + 14)
                    c.closePath()
                    c.fill()
                }
            }

            Connections {
                target: root.controller
                function onRhythmStateChanged() {
                    rhythmTransportSymbol.requestPaint()
                }
            }
        }
        background: Rectangle {
            radius: 31
            color: root.controller.rhythmRunning ? "#a56b19" : "#f0d66b"
            border.color: "#8e7012"; border.width: 2
        }
        onClicked: root.controller.toggleRhythm()
    }

    Item {
        id: controlsArea
        x: runButton.x + runButton.width + 12; y: 0; width: parent.width - x; height: parent.height

        // Preserve the original four-button activity width. The bass group
        // adds one button with exactly that button width; only tempo yields
        // the extra horizontal space.
        readonly property real formerActivityWidth:
            width * 0.57 - 14
        readonly property real standardActivityWidth:
            formerActivityWidth * 0.32
        readonly property real activityGap:
            formerActivityWidth * 0.02
        readonly property real activityButtonWidth:
            (standardActivityWidth - 10 - 3 * 4) / 4
        readonly property real bassActivityWidth:
            10 + 5 * activityButtonWidth + 4 * 4
        readonly property real expandedActivityWidth:
            2 * standardActivityWidth
            + bassActivityWidth
            + 2 * activityGap

        LabeledSlider {
            id: tempoSlider

            x: 0
            y: 0
            width:
                parent.width
                - 14
                - controlsArea.expandedActivityWidth
            height: parent.height

            label: "tempo"
            currentValue:
                root.controller.rhythmTempo
            fromValue: 40
            toValue: 200
            stepValue: 1
            decimals: 0
            midiControlRouter: root.controller.midiPlayer
            midiTarget: ({
                "screen": "omni",
                "kind": "rhythm_tempo"
            })

            onEdited: (value) =>
                root.controller.setRhythmTempo(value)
        }

        Item {
            id: activityArea

            x: tempoSlider.width + 14
            y: 0
            width: parent.width - x
            height: parent.height

            ActivitySelector {
                x: 0
                y: 0
                width: controlsArea.standardActivityWidth
                height: 58

                label: "percussion activity"
                currentLevel:
                    root.controller.rhythmBusyness

                groupColor: "#f5df78"
                idleColor: "#f7e9a8"
                selectedColor: "#bc8410"

                onSelected: (level) =>
                    root.controller.setRhythmBusyness(
                        level
                    )
            }

            ActivitySelector {
                x:
                    controlsArea.standardActivityWidth
                    + controlsArea.activityGap
                y: 0
                width: controlsArea.standardActivityWidth
                height: 58

                label: "chord activity"
                currentLevel:
                    root.controller
                        .rhythmChordActivity

                groupColor: "#f8e9a1"
                idleColor: "#faefbd"
                selectedColor: "#cb981d"

                onSelected: (level) =>
                    root.controller
                        .setRhythmChordActivity(
                            level
                        )
            }

            ActivitySelector {
                x:
                    2
                    * (
                        controlsArea.standardActivityWidth
                        + controlsArea.activityGap
                    )
                y: 0
                width: controlsArea.bassActivityWidth
                height: 52

                label: "bass activity"
                levels: [1, 2, 3, 4, 5]
                levelLabels: ["1", "2", "3", "4", "R"]
                currentLevel:
                    root.controller
                        .rhythmBassActivity

                groupColor: "#faefbd"
                idleColor: "#fff5d1"
                selectedColor: "#d4aa3a"

                onSelected: (level) =>
                    root.controller
                        .setRhythmBassActivity(
                            level
                        )
            }

            LabeledSlider {
                id: bassFunctionSlider

                x:
                    2
                    * (
                        controlsArea.standardActivityWidth
                        + controlsArea.activityGap
                    )
                y: 56
                width: controlsArea.bassActivityWidth
                height: 48

                label:
                    root.controller.bassRiffMode
                    ? "riff selector"
                    : "bass voicing"
                currentValue:
                    root.controller.bassRiffMode
                    ? root.controller.bassRiffSelector
                    : root.controller.bassVoicingShift
                fromValue:
                    root.controller.bassRiffMode ? 1 : -6
                toValue:
                    root.controller.bassRiffMode
                    ? root.controller.bassRiffSelectorMaximum
                    : 6
                stepValue: 1
                decimals: 0

                textColor: "#4c3b08"
                trackColor: "#eee2a5"
                fillColor: "#c59518"
                handleColor: "#fffbea"
                borderColor: "#8a6810"
                midiControlRouter: root.controller.midiPlayer
                midiTarget:
                    root.controller.bassRiffMode
                    ? ({
                        "screen": "omni",
                        "kind": "bass_riff_selector"
                    })
                    : ({
                        "screen": "omni",
                        "kind": "bass_voicing"
                    })

                onEdited: (value) => {
                    if (root.controller.bassRiffMode) {
                        root.controller.setBassRiffSelector(value)
                    } else {
                        root.controller.setBassVoicingShift(value)
                    }
                }
            }
        }
    }
}
