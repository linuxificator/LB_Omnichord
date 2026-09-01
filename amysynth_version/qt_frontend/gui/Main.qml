import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: window

    width: 1920
    height: 850
    minimumWidth: 800
    minimumHeight: 480

    // Deliberately leave Window.flags at Qt's platform default. On a normal
    // Raspberry Pi OS desktop this lets the Wayland compositor own decoration,
    // placement and movement of the top-level window.
    visible: true
    title: "LB Omnichord"
    color: "#f4f0e6"

    property int rowHeight: 74
    property int titleHeight:
        Math.max(0, Number(headerTitleHeight))
    property int rowSpacing: 12
    property int rowIndent: 30
    property int wheelWidth: 150
    property int noteButtonWidth: 65
    property int octaveButtonWidth: 57
    property int inversionButtonWidth: 94
    property int controlSpacing: 6
    property int leftRailWidth: 64
    property int leftSliderWidth: 52
    property int contentX: leftRailWidth

    property int chordRowContentWidth:
        wheelWidth
        + 12 * noteButtonWidth
        + 6 * octaveButtonWidth
        + inversionButtonWidth
        + 8
        + 20 * controlSpacing

    property int maximumChordRowWidth:
        contentX
        + rowIndent * 3
        + chordRowContentWidth

    property int sectionHeight: 104
    property int sectionGap: 10
    property int presetRowHeight: 64
    property int reverbPanelWidth: 572
    property int synthToChordGap: 16
    property int volumeWidth: 52
    property int volumeGap: 8
    property int strumWidth: 150
    property int strumGap: 12

    property int utilityY:
        0
    property int presetY:
        utilityY
        + sectionHeight
        + sectionGap
    property int rhythmY:
        presetY
        + presetRowHeight
        + sectionGap
    property int bassSynthY:
        rhythmY
        + sectionHeight
        + sectionGap
    property int strumSynthY:
        bassSynthY
        + sectionHeight
        + sectionGap
    property int chordSynthY:
        strumSynthY
        + sectionHeight
        + sectionGap

    property int chordRowsHeight:
        4 * rowHeight
        + 3 * rowSpacing

    property int chordRowsY:
        chordSynthY
        + sectionHeight
        + synthToChordGap

    property int totalControlHeight:
        chordRowsY
        + chordRowsHeight

    property int volumeX:
        contentX
        + chordRowContentWidth
        + volumeGap

    property int strumX:
        maximumChordRowWidth
        + strumGap

    readonly property int omniTitleX:
        reverbPanelWidth + 12
    readonly property int omniTitleWidth:
        Math.max(
            0,
            strumX
            - omniTitleX
            - 86
        )

    property color chordPanelColor: "#ddd2a9"
    property color chordPanelBorderColor: "#a69a6e"
    property color accentColor: "#2474b8"
    property color textColor: "#171717"

    // Screen mode is deliberately presentation-only. Switching never sends a
    // transport, note, patch or effect command to AMY.
    property bool midiScreen: backend.midiPlayer.testCcLogging
    property bool tuningCoupled: true
    property bool strumLadderMode: backend.strumLadderMode
    readonly property bool omniTuningMidiBound: {
        backend.midiPlayer.bindingVersion
        return backend.midiPlayer.isControlTargetBound({
            "screen": "omni",
            "kind": "tuning_reference"
        })
    }
    readonly property bool midiTuningMidiBound: {
        backend.midiPlayer.bindingVersion
        return backend.midiPlayer.isControlTargetBound({
            "screen": "midi",
            "kind": "tuning_reference"
        })
    }
    readonly property bool omniTuningLocked:
        window.omniTuningMidiBound
        || (window.tuningCoupled && window.midiTuningMidiBound)
    readonly property bool rhythmTempoMidiBound: {
        backend.midiPlayer.bindingVersion
        return backend.midiPlayer.isControlTargetBound({
            "screen": "omni",
            "kind": "rhythm_tempo"
        })
    }

    function midiButtonHandled(target) {
        const learned = backend.midiPlayer.activateControlTarget(target)
        if (learned)
            return true
        return backend.midiPlayer.midiButtonTargetBlocked(target)
    }

    function setFullscreenMode(fullscreen) {
        if (fullscreen) {
            window.showFullScreen()
        } else {
            // showNormal() is preferable to merely assigning visibility:
            // it explicitly clears fullscreen/maximized/minimized state.
            window.showNormal()
            window.requestActivate()
        }
    }

    function toggleFullscreenMode() {
        setFullscreenMode(
            window.visibility
            !== Window.FullScreen
        )
    }

    Component.onCompleted: {
        // In normal/windowed mode do nothing at all: the compositor receives a
        // standard visible top-level window. Only request a state transition
        // when fullscreen was explicitly requested.
        if (startFullscreen) {
            Qt.callLater(
                function() {
                    window.showFullScreen()
                }
            )
        }
    }

    function octaveColor(index) {
        return [
            "#4d0812",
            "#70101a",
            "#941a24",
            "#b92a34",
            "#dc4a50",
            "#f17c75"
        ][index]
    }

    function octaveTextColor(index) {
        return index >= 5 ? "#3b0808" : "#ffffff"
    }

    Shortcut {
        sequence: "F11"

        onActivated:
            window.toggleFullscreenMode()
    }

    Shortcut {
        sequence: "Escape"
        enabled:
            window.visibility === Window.FullScreen

        onActivated:
            window.setFullscreenMode(false)
    }

    Flickable {
        id: viewport
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        readonly property real fittedScale:
            scaleToFit
            ? Math.min(
                width / contentArea.implicitWidth,
                height / contentArea.implicitHeight
            )
            : 1.0

        interactive: !scaleToFit
        flickableDirection:
            Flickable.HorizontalAndVerticalFlick

        contentWidth: Math.max(
            width,
            contentArea.implicitWidth
                * viewport.fittedScale
        )
        contentHeight: Math.max(
            height,
            contentArea.implicitHeight
                * viewport.fittedScale
        )

        boundsBehavior:
            Flickable.StopAtBounds

        ScrollBar.horizontal: ScrollBar {
            policy:
                scaleToFit
                ? ScrollBar.AlwaysOff
                : ScrollBar.AsNeeded
        }

        ScrollBar.vertical: ScrollBar {
            policy:
                scaleToFit
                ? ScrollBar.AlwaysOff
                : ScrollBar.AsNeeded
        }

        Item {
            id: contentArea

            implicitWidth:
                window.strumX
                + window.strumWidth

            implicitHeight:
                window.totalControlHeight

            x: Math.max(
                0,
                (
                    viewport.width
                    - implicitWidth
                        * viewport.fittedScale
                ) / 2
            )
            y: Math.max(
                0,
                (
                    viewport.height
                    - implicitHeight
                        * viewport.fittedScale
                ) / 2
            )
            scale: viewport.fittedScale
            transformOrigin: Item.TopLeft

            OmniTitleSection {
                x: 0
                y: 0
                width: contentArea.implicitWidth
                height: window.sectionHeight
                visible: window.titleHeight > 0
                titleText: headerTitleText
                titleFont: headerTitleFont
                titleHeight: window.titleHeight
                titleX: window.omniTitleX
                titleWidth: window.omniTitleWidth
                strumPanelX: window.strumX - window.presetRowHeight
                presetRowHeight: window.presetRowHeight
                strumWidth: window.strumWidth
                ladderMode: window.strumLadderMode
                midiControlRouter: backend.midiPlayer
                onStrumModeToggleRequested: {
                    const target = {
                        "screen": "omni",
                        "kind": "button",
                        "action": "strum_ladder"
                    }
                    if (!window.midiButtonHandled(target)) {
                        backend.toggleStrumLadderMode()
                    }
                }
            }

            ReverbPanel {
                id: reverbPanel
                x: 0
                y: window.presetY
                width: window.reverbPanelWidth
                height: window.presetRowHeight
                controller: backend
                midiControlRouter: backend.midiPlayer
                controlScreen: "omni"
            }

            UtilitySection {
                x: window.contentX
                y: window.utilityY
                width:
                    window.volumeX
                    + window.volumeWidth
                    - window.contentX
                height:
                    window.sectionHeight
                    + window.sectionGap
                    + window.presetRowHeight

                controller: backend
                tuningModeModel: tuningModeNames
                fullScreen:
                    window.visibility
                    === Window.FullScreen
                leftExtension: window.leftRailWidth
                tuningCoupled: window.tuningCoupled
                tuningRowHeight: window.sectionHeight
                presetRowY:
                    window.sectionHeight
                    + window.sectionGap
                presetRowHeight: window.presetRowHeight
                utilityRightEdge:
                    reverbPanel.width
                    - window.contentX
                presetX:
                    reverbPanel.width
                    + window.sectionGap
                    - window.contentX

                onToggleFullscreenRequested:
                    window.toggleFullscreenMode()

                onToggleTuningCouplingRequested:
                    window.tuningCoupled = !window.tuningCoupled
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.utilityY + 7
                width: 42
                height: 42
                text: "UP"
                enabled: !window.omniTuningLocked
                panelColor: "#efb05c"
                borderColor: "#a75d0a"
                textColor: "#492606"
                onPressedChanged: {
                    if (pressed) backend.beginPitchBend(1)
                    else backend.endPitchBend()
                }
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.utilityY + window.sectionHeight - height - 7
                width: 42
                height: 42
                text: "DWN"
                enabled: !window.omniTuningLocked
                panelColor: "#efb05c"
                borderColor: "#a75d0a"
                textColor: "#492606"
                onPressedChanged: {
                    if (pressed) backend.beginPitchBend(-1)
                    else backend.endPitchBend()
                }
            }

            // Yellow rhythm/drum family extends through the left control rail.
            Rectangle {
                x: 0
                y: window.rhythmY
                width:
                    window.volumeX
                    + window.volumeWidth
                height: window.sectionHeight
                radius: 12
                color: "#fbf0bd"
                border.color: "#d2b650"
                border.width: 1

                InstrumentWatermarks {
                    anchors.fill: parent
                    family: "percussion"
                    ink: "#b49317"
                }
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.rhythmY + 7
                width: 42
                height: 42
                text: "UP"
                enabled: !window.rhythmTempoMidiBound
                panelColor: "#f4dc78"
                borderColor: "#aa8719"
                textColor: "#4c3505"
                onPressedChanged: {
                    if (pressed) backend.beginTempoNudge(1)
                    else backend.endTempoNudge()
                }
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.rhythmY + window.sectionHeight - height - 7
                width: 42
                height: 42
                text: "DWN"
                enabled: !window.rhythmTempoMidiBound
                panelColor: "#f4dc78"
                borderColor: "#aa8719"
                textColor: "#4c3505"
                onPressedChanged: {
                    if (pressed) backend.beginTempoNudge(-1)
                    else backend.endTempoNudge()
                }
            }

            // Neutral grey bass-synth family, including B VOL.
            Rectangle {
                x: 0
                y: window.bassSynthY
                width:
                    window.volumeX
                    + window.volumeWidth
                height: window.sectionHeight
                radius: 12
                color: "#e3e3e0"
                border.color: "#a6a6a1"
                border.width: 1

                InstrumentWatermarks {
                    anchors.fill: parent
                    family: "bass"
                    ink: "#8f8f88"
                }
            }

            // Green chord-synth family, including C VOL.
            Rectangle {
                x: 0
                y: window.chordSynthY
                width:
                    window.volumeX
                    + window.volumeWidth
                height: window.sectionHeight
                radius: 12
                color: "#e1eee0"
                border.color: "#9cbd9d"
                border.width: 1

                InstrumentWatermarks {
                    anchors.fill: parent
                    family: "chord"
                    ink: "#78a977"
                }
            }

            // Only the blue strum family is visually connected to the pad.
            Rectangle {
                x: 0
                y: window.strumSynthY
                width:
                    window.strumX
                    + window.strumWidth
                height: window.sectionHeight
                radius: 12
                color: "#dcecf7"
                border.color: "#8bb9d8"
                border.width: 1

                InstrumentWatermarks {
                    anchors.fill: parent
                    family: "strum"
                    ink: "#6fa8cd"
                }
            }

            StrumNoteGuide {
                x:
                    window.volumeX
                    + window.volumeWidth
                y: window.sectionHeight
                width:
                    window.strumX
                    - x
                height:
                    window.strumSynthY
                    - y
                noteModel: backend.strumNoteNames
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.bassSynthY + (window.sectionHeight - height) / 2
                width: 50
                height: 50
                text: "RST"
                panelColor: "#d0d0cc"
                borderColor: "#7b7b76"
                onClicked: backend.resetBassToPreset()
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.strumSynthY + (window.sectionHeight - height) / 2
                text: "RST"
                panelColor: "#b9def3"
                borderColor: "#589bc6"
                textColor: "#12344d"
                onClicked: backend.resetStrumToPreset()
            }

            PresetResetButton {
                x: (window.leftRailWidth - width) / 2
                y: window.chordSynthY + (window.sectionHeight - height) / 2
                text: "RST"
                panelColor: "#c7ddc5"
                borderColor: "#649068"
                textColor: "#1d4023"
                onClicked: backend.resetChordSynthToPreset()
            }

            RhythmSection {
                x: window.contentX
                y: window.rhythmY
                width:
                    window.chordRowContentWidth
                height:
                    window.sectionHeight

                controller: backend
                rhythmModel: rhythmNames
            }

            SynthSection {
                id: bassSynthSection

                x: window.contentX
                y: window.bassSynthY
                width:
                    window.chordRowContentWidth
                height:
                    window.sectionHeight

                controller: backend
                synthModel: synthNames
                role: "bass"

                wheelColor: "#a6a6a3"
                wheelBorderColor: "#666662"
                wheelTextColor: "#202020"
                selectionColor: "#52524f"

                commonTextColor: "#303030"
                commonTrackColor: "#d0d0cd"
                commonFillColor: "#686864"
                commonHandleColor: "#fafafa"
                commonBorderColor: "#555552"

                extraTextColor: "#404040"
                extraTrackColor: "#e1e1de"
                extraFillColor: "#92928e"
                extraHandleColor: "#ffffff"
                extraBorderColor: "#73736e"
            }

            SynthSection {
                id: strumSynthSection

                x: window.contentX
                y: window.strumSynthY
                width:
                    window.chordRowContentWidth
                height:
                    window.sectionHeight

                controller: backend
                synthModel: synthNames
                role: "strum"

                wheelColor: "#5d9fd0"
                wheelBorderColor: "#2f648c"
                wheelTextColor: "#071c2c"
                selectionColor: "#164b77"

                commonTextColor: "#08243d"
                commonTrackColor: "#b8d9ef"
                commonFillColor: "#245f91"
                commonHandleColor: "#f3fbff"
                commonBorderColor: "#164b77"

                extraTextColor: "#0d3552"
                extraTrackColor: "#d5ecfa"
                extraFillColor: "#74bde8"
                extraHandleColor: "#f5fcff"
                extraBorderColor: "#3d91c7"
            }

            SynthSection {
                id: chordSynthSection

                x: window.contentX
                y: window.chordSynthY
                width:
                    window.chordRowContentWidth
                height:
                    window.sectionHeight

                controller: backend
                synthModel: synthNames
                role: "chord"

                wheelColor: "#78a57c"
                wheelBorderColor: "#476b4b"
                wheelTextColor: "#102417"
                selectionColor: "#315b39"

                commonTextColor: "#102417"
                commonTrackColor: "#c5d8c9"
                commonFillColor: "#426f4c"
                commonHandleColor: "#f4fff5"
                commonBorderColor: "#315b39"

                extraTextColor: "#16301e"
                extraTrackColor: "#d8eadb"
                extraFillColor: "#77ad82"
                extraHandleColor: "#f4fff5"
                extraBorderColor: "#4d8759"
            }

            VerticalVolume {
                x: window.volumeX
                y: window.rhythmY
                width: window.volumeWidth
                height: window.sectionHeight

                currentValue:
                    backend.percussionVolume
                panelColor: "#f4dc78"
                panelBorderColor: "#aa8719"
                fillColor: "#d69b10"
                textColor: "#4c3505"
                midiControlRouter: backend.midiPlayer
                midiTarget: ({
                    "screen": "omni",
                    "kind": "volume",
                    "role": "percussion"
                })

                onEdited: (value) =>
                    backend.setPercussionVolume(
                        value
                    )
            }

            VerticalVolume {
                x: window.volumeX
                y: window.bassSynthY
                width: window.volumeWidth
                height: window.sectionHeight

                currentValue:
                    backend.bassVolume
                panelColor: "#c9c9c5"
                panelBorderColor: "#6d6d68"
                fillColor: "#686864"
                textColor: "#242422"
                midiControlRouter: backend.midiPlayer
                midiTarget: ({
                    "screen": "omni",
                    "kind": "volume",
                    "role": "bass"
                })

                onEdited: (value) =>
                    backend.setBassVolume(value)
            }

            VerticalVolume {
                x: window.volumeX
                y: window.strumSynthY
                width: window.volumeWidth
                height: window.sectionHeight

                currentValue:
                    backend.strumVolume
                panelColor: "#a8d8f2"
                panelBorderColor: "#4b95c4"
                fillColor: "#18a8e0"
                textColor: "#08243d"
                midiControlRouter: backend.midiPlayer
                midiTarget: ({
                    "screen": "omni",
                    "kind": "volume",
                    "role": "strum"
                })

                onEdited: (value) =>
                    backend.setStrumVolume(value)
            }

            VerticalVolume {
                x: window.volumeX
                y: window.chordSynthY
                width: window.volumeWidth
                height: window.sectionHeight

                currentValue:
                    backend.chordVolume
                panelColor: "#b9d5b7"
                panelBorderColor: "#58855b"
                fillColor: "#3d9348"
                textColor: "#14321a"
                midiControlRouter: backend.midiPlayer
                midiTarget: ({
                    "screen": "omni",
                    "kind": "volume",
                    "role": "chord"
                })

                onEdited: (value) =>
                    backend.setChordVolume(value)
            }

            Column {
                id: chordRows

                x: window.contentX
                y: window.chordRowsY
                spacing: window.rowSpacing

                Repeater {
                    model: 4

                    delegate: Item {
                        id: rowItem

                        required property int index
                        property int rowIndex: index

                        width:
                            window.maximumChordRowWidth
                            - window.contentX
                        height: window.rowHeight

                        Rectangle {
                            id: chordControlPanel

                            visible: rowItem.rowIndex === 0
                            x: -window.contentX
                            y: 0
                            width: window.contentX
                            height:
                                2 * window.rowHeight
                                + window.rowSpacing
                            radius: 10
                            color: window.chordPanelColor
                            border.color: window.chordPanelBorderColor
                            border.width: 1

                            readonly property real controlGap:
                                (
                                    height
                                    - 3 * 42
                                ) / 4
                        }

                        Column {
                            visible: rowItem.rowIndex === 0
                            x: -window.contentX + (window.contentX - 42) / 2
                            y: chordControlPanel.controlGap
                            spacing: chordControlPanel.controlGap

                            PresetResetButton {
                                width: 42
                                height: 42
                                text: "RST"
                                panelColor: "#e5d9b2"
                                borderColor: "#9f9165"
                                textColor: "#4a4022"
                                onClicked: backend.resetChordRowsToPreset()
                            }

                            PresetResetButton {
                                width: 42
                                height: 42
                                text: "UP"
                                panelColor: "#e5d9b2"
                                borderColor: "#9f9165"
                                textColor: "#4a4022"
                                onClicked: backend.rollChordRows(-1)
                            }

                            PresetResetButton {
                                width: 42
                                height: 42
                                text: "DWN"
                                panelColor: "#e5d9b2"
                                borderColor: "#9f9165"
                                textColor: "#4a4022"
                                onClicked: backend.rollChordRows(1)
                            }
                        }

                        // The gate control moved to the shared left edge below
                        // the chord-type RST/UP/DWN stack.
                        Button {
                            id: offButton
                            visible: false
                            width: 1
                            height: 1
                        }

                        Row {
                            id: chordRow

                            x:
                                rowItem.rowIndex
                                * window.rowIndent

                            height: window.rowHeight
                            spacing:
                                window.controlSpacing

                            Frame {
                                width: window.wheelWidth
                                height: window.rowHeight
                                padding: 0

                                background: Rectangle {
                                    radius: 10
                                    color:
                                        window
                                            .chordPanelColor
                                    border.color:
                                        window
                                            .chordPanelBorderColor
                                }

                                Tumbler {
                                    id: chordWheel

                                    anchors.fill: parent
                                    anchors.margins: 2
                                    model: chordNames
                                    visibleItemCount: 3
                                    wrap: true

                                    property bool initialized:
                                        false
                                    property bool
                                        syncingFromBackend:
                                            false

                                    Component.onCompleted: {
                                        syncingFromBackend =
                                            true
                                        currentIndex =
                                            backend
                                                .chordIndexForRow(
                                                    rowItem
                                                        .rowIndex
                                                )

                                        Qt.callLater(
                                            function() {
                                                chordWheel
                                                    .syncingFromBackend =
                                                    false
                                                chordWheel
                                                    .initialized =
                                                    true
                                            }
                                        )
                                    }

                                    Connections {
                                        target: backend

                                        function onStateChanged() {
                                            if (
                                                !chordWheel
                                                    .initialized
                                            ) {
                                                return
                                            }

                                            const wanted =
                                                backend
                                                    .chordIndexForRow(
                                                        rowItem
                                                            .rowIndex
                                                    )

                                            if (
                                                chordWheel
                                                    .currentIndex
                                                !== wanted
                                            ) {
                                                chordWheel
                                                    .syncingFromBackend =
                                                    true
                                                chordWheel
                                                    .currentIndex =
                                                    wanted

                                                Qt.callLater(
                                                    function() {
                                                        chordWheel
                                                            .syncingFromBackend =
                                                            false
                                                    }
                                                )
                                            }
                                        }
                                    }

                                    delegate: Item {
                                        required property var
                                            modelData
                                        required property int
                                            index

                                        width:
                                            chordWheel.width
                                        height:
                                            chordWheel.height
                                            / chordWheel
                                                .visibleItemCount

                                        Text {
                                            anchors.centerIn:
                                                parent
                                            width:
                                                parent.width
                                                - 10
                                            text: modelData
                                            color:
                                                window.textColor
                                            elide:
                                                Text.ElideRight
                                            horizontalAlignment:
                                                Text.AlignHCenter
                                            verticalAlignment:
                                                Text.AlignVCenter

                                            font.pixelSize:
                                                Math.abs(
                                                    Tumbler
                                                        .displacement
                                                ) < 0.5
                                                ? 18 : 15

                                            font.bold:
                                                Math.abs(
                                                    Tumbler
                                                        .displacement
                                                ) < 0.5

                                            opacity:
                                                0.30
                                                + Math.max(
                                                    0,
                                                    1
                                                    - Math.abs(
                                                        Tumbler
                                                            .displacement
                                                    )
                                                ) * 0.70
                                        }

                                        TapHandler {
                                            gesturePolicy:
                                                TapHandler.DragThreshold

                                            onTapped:
                                                chordWheel.currentIndex =
                                                    index
                                        }
                                    }

                                    onCurrentIndexChanged: {
                                        if (
                                            initialized
                                            && !syncingFromBackend
                                            && currentIndex >= 0
                                        ) {
                                            backend
                                                .setRowChordType(
                                                    rowItem
                                                        .rowIndex,
                                                    currentIndex
                                                )
                                        }
                                    }

                                }

                                Rectangle {
                                    anchors.horizontalCenter:
                                        parent
                                            .horizontalCenter
                                    y:
                                        parent.height / 2
                                        - 14
                                    width:
                                        parent.width - 12
                                    height: 28
                                    radius: 7
                                    color: "transparent"
                                    border.color:
                                        window.accentColor
                                    border.width: 2
                                }
                            }

                            Repeater {
                                model: noteDefinitions

                                // Musical chord keys deliberately do not use
                                // AbstractButton. A note-on must remain held
                                // until the physical touch actually ends.
                                delegate: Item {
                                    id: noteButton

                                    objectName:
                                        "chordButton_"
                                        + rowItem.rowIndex
                                        + "_"
                                        + modelData.semitone

                                    required property var
                                        modelData

                                    width:
                                        window
                                            .noteButtonWidth
                                    height:
                                        window.rowHeight

                                    property bool touchActive:
                                        false

                                    function beginChordPointer(x, y) {
                                        if (touchActive) {
                                            return
                                        }

                                        touchActive = true
                                        backend.debugChordTouch(
                                            "pressed",
                                            rowItem.rowIndex,
                                            modelData.semitone,
                                            x,
                                            y
                                        )
                                        backend.pressChord(
                                            rowItem.rowIndex,
                                            modelData.semitone
                                        )
                                    }

                                    function endChordPointer(x, y) {
                                        if (!touchActive) {
                                            return
                                        }

                                        backend.debugChordTouch(
                                            "released",
                                            rowItem.rowIndex,
                                            modelData.semitone,
                                            x,
                                            y
                                        )
                                        backend.releaseChord(
                                            rowItem.rowIndex,
                                            modelData.semitone
                                        )
                                        touchActive = false
                                    }

                                    function promoteChordPointer() {
                                        if (!touchActive) {
                                            return
                                        }

                                        backend.debugChordTouch(
                                            "long-pressed",
                                            rowItem.rowIndex,
                                            modelData.semitone,
                                            chordPointer.point.position.x,
                                            chordPointer.point.position.y
                                        )
                                        backend.promoteChordHold(
                                            rowItem.rowIndex,
                                            modelData.semitone
                                        )
                                    }

                                    property bool selected: {
                                        backend.stateVersion

                                        return (
                                            noteButton
                                                .touchActive
                                            || (
                                                backend
                                                    .activeRowIndex
                                                === rowItem
                                                    .rowIndex
                                                && backend
                                                    .activeRootSemitone
                                                === modelData
                                                    .semitone
                                            )
                                        )
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 8

                                        color:
                                            modelData
                                                .accidental
                                            ? (
                                                noteButton
                                                    .touchActive
                                                ? "#383838"
                                                : "#111111"
                                            )
                                            : (
                                                noteButton
                                                    .touchActive
                                                ? "#e8e8e3"
                                                : "#fffef8"
                                            )

                                        border.color:
                                            noteButton
                                                .selected
                                            ? window
                                                .accentColor
                                            : (
                                                modelData
                                                    .accidental
                                                ? "#000000"
                                                : "#9a967f"
                                            )

                                        border.width:
                                            noteButton
                                                .selected
                                            ? 4 : 1
                                    }

                                    Text {
                                        anchors.centerIn: parent

                                        text:
                                            modelData.label

                                        color:
                                            modelData
                                                .accidental
                                            ? "#ffffff"
                                            : "#111111"

                                        font.pixelSize: 18
                                        font.bold:
                                            noteButton.selected

                                        horizontalAlignment:
                                            Text.AlignHCenter
                                        verticalAlignment:
                                            Text.AlignVCenter
                                    }

                                    // Qt classifies press, long-press and
                                    // release using its platform style hints
                                    // for mouse, touch and pen input alike.
                                    TapHandler {
                                        id: chordPointer

                                        acceptedButtons:
                                            Qt.LeftButton
                                        gesturePolicy:
                                            TapHandler.ReleaseWithinBounds

                                        onPressedChanged: {
                                            if (pressed) {
                                                noteButton
                                                    .beginChordPointer(
                                                        point
                                                            .position.x,
                                                        point
                                                            .position.y
                                                    )
                                            } else {
                                                noteButton
                                                    .endChordPointer(
                                                        point
                                                            .position.x,
                                                        point
                                                            .position.y
                                                    )
                                            }
                                        }

                                        onLongPressed:
                                            noteButton
                                                .promoteChordPointer()
                                    }
                                }
                            }

                            Item {
                                width: 8
                                height: 1
                            }

                            Repeater {
                                model: octaveNames

                                delegate: Button {
                                    id: octaveButton

                                    required property string
                                        modelData
                                    required property int
                                        index

                                    width:
                                        window
                                            .octaveButtonWidth
                                    height:
                                        window.rowHeight
                                    text: modelData

                                    property bool selected: {
                                        backend.stateVersion

                                        return (
                                            backend
                                                .octaveIndexForRow(
                                                    rowItem
                                                        .rowIndex
                                                )
                                            === index
                                        )
                                    }

                                    font.pixelSize: 17
                                    font.bold: true

                                    contentItem: Text {
                                        text:
                                            octaveButton.text
                                        color:
                                            octaveButton.selected
                                            ? "#ffffff"
                                            : window
                                                .octaveTextColor(
                                                    index
                                                )
                                        font:
                                            octaveButton.font
                                        horizontalAlignment:
                                            Text.AlignHCenter
                                        verticalAlignment:
                                            Text.AlignVCenter
                                    }

                                    background: Rectangle {
                                        radius: 9
                                        color:
                                            octaveButton.selected
                                            ? "#7142a6"
                                            : window
                                                .octaveColor(
                                                    index
                                                )
                                        opacity:
                                            octaveButton
                                                .pressed
                                            ? 0.72 : 1.0
                                        border.color:
                                            octaveButton.selected
                                            ? "#d6b8ff"
                                            : "#5a2024"
                                        border.width:
                                            octaveButton.selected
                                            ? 4 : 1
                                    }

                                    onClicked:
                                        backend.setRowOctave(
                                            rowItem.rowIndex,
                                            index
                                        )
                                }
                            }

                            Button {
                                id: inversionButton

                                width:
                                    window
                                        .inversionButtonWidth
                                height:
                                    window.rowHeight

                                text: {
                                    backend.stateVersion
                                    return backend
                                        .inversionLabelForRow(
                                            rowItem
                                                .rowIndex
                                        )
                                }

                                font.pixelSize: 15
                                font.bold: true

                                contentItem: Text {
                                    text:
                                        inversionButton.text
                                    color: "#f7f0ff"
                                    font:
                                        inversionButton.font
                                    horizontalAlignment:
                                        Text.AlignHCenter
                                    verticalAlignment:
                                        Text.AlignVCenter
                                }

                                background: Rectangle {
                                    radius: 9
                                    color:
                                        inversionButton
                                            .pressed
                                        ? "#5b3b82"
                                        : (
                                            inversionButton
                                                .hovered
                                            ? "#684a91"
                                            : "#493365"
                                        )
                                    border.color:
                                        "#a98bd1"
                                }

                                onClicked:
                                    backend
                                        .cycleRowInversion(
                                            rowItem
                                                .rowIndex
                                        )
                            }
                        }

                        // Copies the complete blue synth state and blue
                        // volume into the green chord engine.
                        Button {
                            id: copyButton

                            visible:
                                rowItem.rowIndex === 0

                            x:
                                window.chordRowContentWidth
                                + 6
                            y:
                                (
                                    window.rowHeight
                                    - height
                                ) / 2
                            width: 52
                            height: 52

                            text: "↓"
                            font.pixelSize: 31
                            font.bold: true

                            contentItem: Text {
                                text: copyButton.text
                                color: "#1769aa"
                                font: copyButton.font
                                horizontalAlignment:
                                    Text.AlignHCenter
                                verticalAlignment:
                                    Text.AlignVCenter
                            }

                            background: Rectangle {
                                radius: 26
                                color:
                                    copyButton.pressed
                                    ? "#73ad75"
                                    : "#94c896"
                                border.color: "#3d7d43"
                                border.width: 2
                            }

                            ToolTip.visible:
                                copyButton.hovered
                            ToolTip.text:
                                "Copy blue strum synth and volume to green chord synth"

                            onClicked:
                                backend.copyStrumToChord()
                        }
                    }
                }
            }

            // Moved left and up: aligned with the third chord row and with the
            // left edge of the section backgrounds.
            Button {
                id: chordGateButton

                x: 0
                y:
                    window.chordRowsY
                    + 2
                    * (
                        window.rowHeight
                        + window.rowSpacing
                    )
                width:
                    window.contentX
                    + 2 * window.rowIndent
                    - window.controlSpacing
                height: window.rowHeight
                text: backend.chordGateButtonText

                readonly property bool selectedState:
                    backend.chordGateState === 1

                font.pixelSize: 14
                font.bold: true

                contentItem: Text {
                    text: chordGateButton.text
                    color:
                        chordGateButton.selectedState
                        ? "#fff9dd"
                        : "#4c3b08"
                    font: chordGateButton.font
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: 9
                    color:
                        chordGateButton.selectedState
                        ? "#c79214"
                        : (
                            chordGateButton.pressed
                            ? "#e1ca6a"
                            : "#f3e5a5"
                        )
                    border.color: "#96720f"
                    border.width:
                        chordGateButton.selectedState ? 2 : 1
                }

                onClicked:
                    backend.toggleChordGate()
            }

            RainbowModeButton {
                id: midiModeButton
                x: 0
                y:
                    window.chordRowsY
                    + 3
                    * (
                        window.rowHeight
                        + window.rowSpacing
                    )
                width:
                    window.contentX
                    + 2 * window.rowIndent
                    - window.controlSpacing
                    + midiModeButton.extensionWidth
                height: window.rowHeight
                text: "MIDI"
                midiControlRouter: backend.midiPlayer
                bindingLocationScreen: "midi"
                midiLearnActive:
                    backend.midiPlayer.omniControlLedState === "learn"
                onClicked:
                    window.midiScreen = true
            }

            StrumPad {
                x: window.strumX
                y: 0
                width: window.strumWidth
                height:
                    window.totalControlHeight
                controller: backend
                ladderMode: window.strumLadderMode
            }

            MidiScreen {
                anchors.fill: parent
                z: 10000
                visible: window.midiScreen
                hostWindow: window
                tuningCoupled: window.tuningCoupled

                onShowOmniRequested:
                    window.midiScreen = false

                onToggleTuningCouplingRequested:
                    window.tuningCoupled = !window.tuningCoupled
            }
        }
    }
}
