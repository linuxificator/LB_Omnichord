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

    function midiButtonHandled(target) {
        const learned = root.controller.midiPlayer.activateControlTarget(target)
        if (learned)
            return true
        return root.controller.midiPlayer.midiButtonTargetBlocked(target)
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
        property var midiTarget: ({
            "screen": "omni",
            "kind": "button",
            "action": "rhythm_toggle"
        })
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
        MidiButtonLed {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 8
            z: 2
            midiControlRouter: root.controller.midiPlayer
            midiTarget: runButton.midiTarget
        }
        onClicked: {
            if (!root.midiButtonHandled(runButton.midiTarget)) {
                root.controller.toggleRhythm()
            }
        }
    }

    Item {
        id: controlsArea
        x: runButton.x + runButton.width + 12; y: 0; width: parent.width - x; height: parent.height

        // Percussion, chord and bass each use five columns. Tempo and fill
        // density share the remaining strip.
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
        readonly property real bassColumnX:
            2 * bassActivityWidth + 2 * activityGap
        readonly property real expandedActivityWidth:
            3 * bassActivityWidth
            + 2 * activityGap

        LabeledSlider {
            id: tempoSlider

            x: 0
            y: 0
            width:
                parent.width
                - 14
                - controlsArea.expandedActivityWidth
            height: 52

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

        LabeledSlider {
            id: fillDensitySlider
            x: 0
            y: 56
            width: tempoSlider.width
            height: parent.height - y
            label: "fill density"
            currentValue: root.controller.rhythmFillDensityIndex
            fromValue: 0
            toValue: 7
            stepValue: 1
            decimals: 0
            valueLabels: root.controller.rhythmFillDensityLabels
            midiControlRouter: root.controller.midiPlayer
            midiTarget: ({
                "screen": "omni",
                "kind": "rhythm_fill_density"
            })
            onEdited: (value) =>
                root.controller.setRhythmFillDensity(value)
        }

        Item {
            id: activityArea

            x: tempoSlider.width + 14
            y: 0
            width: parent.width - x
            height: parent.height

            PercussionActivitySelector {
                x: 0
                y: 0
                width: controlsArea.bassActivityWidth
                height: parent.height
                currentLevel:
                    root.controller.rhythmBusyness
                fillEnabled:
                    root.controller.rhythmFillEnabled

                groupColor: "#f5df78"
                idleColor: "#f7e9a8"
                selectedColor: "#bc8410"
                midiControlRouter: root.controller.midiPlayer
                activityMidiTargetForLevel: function(level) {
                    return {
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_busyness",
                        "level": level
                    }
                }
                fillMidiTargetForIndex: function(fillIndex) {
                    return {
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_fill",
                        "fill": fillIndex
                    }
                }

                onActivitySelected: (level) => {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_busyness",
                        "level": level
                    })) {
                        root.controller.setRhythmBusyness(
                            level
                        )
                    }
                }
                onFillToggled: (fillIndex) => {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_fill",
                        "fill": fillIndex
                    })) {
                        root.controller.toggleRhythmFill(fillIndex)
                    }
                }
            }

            ChordActivitySelector {
                x:
                    controlsArea.bassActivityWidth
                    + controlsArea.activityGap
                y: 0
                width: controlsArea.bassActivityWidth
                height: parent.height
                currentLevel:
                    root.controller
                        .rhythmChordActivity
                arpeggioEnabled:
                    root.controller
                        .chordArpeggioEnabled
                arpeggioRate:
                    root.controller
                        .chordArpeggioRate
                arpeggioDescending:
                    root.controller
                        .chordArpeggioDescending
                directionLabel:
                    root.controller
                        .chordArpeggioDirectionLabel

                groupColor: "#f8e9a1"
                idleColor: "#faefbd"
                selectedColor: "#cb981d"
                midiControlRouter: root.controller.midiPlayer
                activityMidiTargetForLevel: function(level) {
                    return {
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_chord_activity",
                        "level": level
                    }
                }
                arpeggioMidiTarget: ({
                    "screen": "omni",
                    "kind": "button",
                    "action": "chord_arpeggio"
                })
                rateMidiTargetForRate: function(rate) {
                    return {
                        "screen": "omni",
                        "kind": "button",
                        "action": "chord_arpeggio_rate",
                        "rate": rate
                    }
                }
                directionMidiTarget: ({
                    "screen": "omni",
                    "kind": "button",
                    "action": "chord_arpeggio_direction"
                })

                onActivitySelected: (level) => {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_chord_activity",
                        "level": level
                    })) {
                        root.controller
                            .setRhythmChordActivity(
                                level
                            )
                    }
                }
                onArpeggioToggled: {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "chord_arpeggio"
                    })) {
                        root.controller
                            .toggleChordArpeggio()
                    }
                }
                onRateSelected: (rate) => {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "chord_arpeggio_rate",
                        "rate": rate
                    })) {
                        root.controller
                            .setChordArpeggioRate(rate)
                    }
                }
                onDirectionToggled: {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "chord_arpeggio_direction"
                    })) {
                        root.controller
                            .toggleChordArpeggioDirection()
                    }
                }
            }

            ActivitySelector {
                x: controlsArea.bassColumnX
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
                midiControlRouter: root.controller.midiPlayer
                midiTargetForLevel: function(level) {
                    return {
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_bass_activity",
                        "level": level
                    }
                }

                onSelected: (level) => {
                    if (!root.midiButtonHandled({
                        "screen": "omni",
                        "kind": "button",
                        "action": "rhythm_bass_activity",
                        "level": level
                    })) {
                        root.controller
                            .setRhythmBassActivity(
                                level
                            )
                    }
                }
            }

            LabeledSlider {
                id: bassFunctionSlider

                x: controlsArea.bassColumnX
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
