import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: root

    required property var hostWindow
    property bool tuningCoupled: true
    property int activeMidiRow: 0
    property var midiControlModel: []
    property var midiInputTechModel: backend.midiPlayer.midiInputTechs
    readonly property bool tuningMidiLocked:
        root.hostWindow.midiTuningMidiBound
        || (
            root.tuningCoupled
            && root.hostWindow.omniTuningMidiBound
        )

    signal showOmniRequested()
    signal toggleTuningCouplingRequested()

    onVisibleChanged: {
        if (visible) {
            Qt.callLater(function() {
                midiControlBar.publishCapacity()
            })
        }
    }

    Timer {
        interval: 100
        running: root.visible || backend.midiPlayer.testCcLogging
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            backend.midiPlayer.setControlIndicatorCapacity(
                midiControlBar.indicatorCapacity
            )
            root.midiControlModel = backend.midiPlayer
                .commonControls(-1)
                .slice(0, midiControlBar.indicatorCapacity)
            backend.midiPlayer.testLogControlIndicatorLayout(
                midiControlBar.x,
                midiControlBar.width,
                midiControlBar.indicatorCapacity,
                midiControlRow.implicitWidth,
                midiControlRepeater.count,
                midiControlBar.x
                + midiControlBar.horizontalPadding
                + midiControlRow.implicitWidth
            )
            backend.midiPlayer.testLogControlIndicatorState(
                root.midiControlModel
            )
        }
    }

    readonly property var synthThemes: [
        {
            "panel": "#f4d8dc",
            "border": "#c97b84",
            "accent": "#b84957",
            "text": "#45151b"
        },
        {
            "panel": "#f6dfc8",
            "border": "#c98a4f",
            "accent": "#c46c27",
            "text": "#4c280c"
        },
        {
            "panel": "#f5edbd",
            "border": "#c5ac49",
            "accent": "#b18b13",
            "text": "#413408"
        },
        {
            "panel": "#dcefd8",
            "border": "#83ad7d",
            "accent": "#4a9251",
            "text": "#153819"
        },
        {
            "panel": "#dcecf7",
            "border": "#8bb9d8",
            "accent": "#2f7fb4",
            "text": "#102f45"
        },
        {
            "panel": "#e8dcf5",
            "border": "#9270b6",
            "accent": "#75479d",
            "text": "#32194b"
        }
    ]

    readonly property color activeStrumColor:
        root.synthThemes[root.activeMidiRow].accent

    Rectangle {
        id: midiControlBar

        readonly property int indicatorWidth: 74
        readonly property int indicatorSpacing: 10
        readonly property int horizontalPadding: 8
        readonly property int indicatorCapacity: Math.max(
            1,
            Math.floor(
                (width - 2 * horizontalPadding)
                / (indicatorWidth + indicatorSpacing)
            )
        )

        function publishCapacity() {
            backend.midiPlayer.setControlIndicatorCapacity(indicatorCapacity)
        }

        onIndicatorCapacityChanged: {
            if (root.visible || backend.midiPlayer.testCcLogging) {
                publishCapacity()
            }
        }

        anchors.fill: parent
        color: "#f4f0e6"
    }

    // Consume unused-space touches so no hidden Omnichord control underneath
    // the MIDI screen can be activated through a transparent gap.
    MouseArea {
        anchors.fill: parent
    }

    Item {
        id: midiTitle
        x: 0
        y: 0
        width: root.width
        height: root.hostWindow.sectionHeight
        visible: root.hostWindow.titleHeight > 0

        Text {
            x: root.hostWindow.omniTitleX
            y: 0
            width: root.hostWindow.omniTitleWidth
            height: parent.height
            text: headerTitleText
            color: "#493a38"
            font.family: headerTitleFont
            font.pixelSize:
                Math.max(
                    14,
                    root.hostWindow.titleHeight * 0.62
                )
            font.weight: Font.Medium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    ReverbPanel {
        id: reverbPanel
        x: 0
        y: root.hostWindow.presetY
        width: root.hostWindow.reverbPanelWidth
        height: root.hostWindow.presetRowHeight
        controller: backend.midiPlayer
        midiControlRouter: backend.midiPlayer
        controlScreen: "midi"
    }

    MidiUtilitySection {
        x: root.hostWindow.contentX
        y: root.hostWindow.utilityY
        width:
            root.hostWindow.volumeX
            + root.hostWindow.volumeWidth
            - root.hostWindow.contentX
        height:
            root.hostWindow.sectionHeight
            + root.hostWindow.sectionGap
            + root.hostWindow.presetRowHeight

        controller: backend.midiPlayer
        omniController: backend
        tuningModeModel: tuningModeNames
        fullScreen:
            root.hostWindow.visibility
            === Window.FullScreen
        leftExtension: root.hostWindow.leftRailWidth
        tuningCoupled: root.tuningCoupled
        tuningRowHeight: root.hostWindow.sectionHeight
        presetRowY:
            root.hostWindow.sectionHeight
            + root.hostWindow.sectionGap
        presetRowHeight: root.hostWindow.presetRowHeight
        utilityRightEdge:
            reverbPanel.width
            - root.hostWindow.contentX
        presetX:
            reverbPanel.width
            + root.hostWindow.sectionGap
            - root.hostWindow.contentX

        onToggleFullscreenRequested:
            root.hostWindow.toggleFullscreenMode()

        onToggleTuningCouplingRequested:
            root.toggleTuningCouplingRequested()
    }

    PresetResetButton {
        x: (root.hostWindow.leftRailWidth - width) / 2
        y: root.hostWindow.utilityY + 7
        width: 42
        height: 42
        text: "UP"
        enabled: !root.tuningMidiLocked
        panelColor: "#efb05c"
        borderColor: "#a75d0a"
        textColor: "#492606"
        onPressedChanged: {
            if (pressed) {
                if (root.tuningCoupled) backend.beginPitchBend(1)
                else backend.beginMidiPitchBend(1)
            } else {
                if (root.tuningCoupled) backend.endPitchBend()
                else backend.endMidiPitchBend()
            }
        }
    }

    PresetResetButton {
        x: (root.hostWindow.leftRailWidth - width) / 2
        y:
            root.hostWindow.utilityY
            + root.hostWindow.sectionHeight
            - height
            - 7
        width: 42
        height: 42
        text: "DWN"
        enabled: !root.tuningMidiLocked
        panelColor: "#efb05c"
        borderColor: "#a75d0a"
        textColor: "#492606"
        onPressedChanged: {
            if (pressed) {
                if (root.tuningCoupled) backend.beginPitchBend(-1)
                else backend.beginMidiPitchBend(-1)
            } else {
                if (root.tuningCoupled) backend.endPitchBend()
                else backend.endMidiPitchBend()
            }
        }
    }

    Repeater {
        model: root.synthThemes

        delegate: MidiSynthSection {
            required property var modelData
            required property int index

            x: 0
            y:
                root.hostWindow.rhythmY
                + index
                * (
                    root.hostWindow.sectionHeight
                    + root.hostWindow.sectionGap
                )
            width:
                root.hostWindow.volumeX
                + root.hostWindow.volumeWidth
            height: root.hostWindow.sectionHeight

            controller: backend.midiPlayer
            rowIndex: index
            synthModel: backend.midiPlayer.synthNames
            leftRailWidth: root.hostWindow.leftRailWidth
            contentX: root.hostWindow.contentX
            volumeX: root.hostWindow.volumeX
            volumeWidth: root.hostWindow.volumeWidth
            wheelWidth: root.hostWindow.wheelWidth

            panelColor: modelData.panel
            borderColor: modelData.border
            accentColor: modelData.accent
            textColor: modelData.text

            onInteracted: (rowIndex) =>
                root.activeMidiRow = rowIndex
        }
    }

    RainbowModeButton {
        id: omniButton
        x: 0
        y:
            root.hostWindow.chordRowsY
            + 3
            * (
                root.hostWindow.rowHeight
                + root.hostWindow.rowSpacing
            )
        width:
            root.hostWindow.contentX
            + 2 * root.hostWindow.rowIndent
            - root.hostWindow.controlSpacing
            + omniButton.extensionWidth
        height: root.hostWindow.rowHeight
        text: "OMNI"
        midiControlRouter: backend.midiPlayer
        bindingLocationScreen: "omni"
        onClicked: {
            backend.finishMidiPreview()
            root.showOmniRequested()
        }
    }

    Rectangle {
        id: midiCcPanel
        x:
            omniButton.x
            + omniButton.width
            + root.hostWindow.controlSpacing
        y:
            root.hostWindow.chordRowsY
            + 3 * (root.hostWindow.rowHeight + root.hostWindow.rowSpacing)
        width: Math.max(
            0,
            root.hostWindow.volumeX
            + root.hostWindow.volumeWidth
            - x
        )
        height: root.hostWindow.rowHeight
        radius: 12
        color: "#c8c8c4"
        border.color: "#777772"
        clip: true

        Row {
            id: midiControlRow
            anchors.left: parent.left
            anchors.leftMargin: midiControlBar.horizontalPadding
            anchors.verticalCenter: parent.verticalCenter
            spacing: midiControlBar.indicatorSpacing

            Repeater {
                id: midiControlRepeater
                model: root.midiControlModel

                delegate: Button {
                    required property var modelData
                    width: midiControlBar.indicatorWidth
                    height: 68
                    enabled: !modelData.evicting
                    padding: 0
                    background: Item {}
                    contentItem: Item {}

                    Rectangle {
                        id: controlLed
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 0
                        width: 10
                        height: 10
                        radius: 5
                        color: {
                            if (modelData.evicting)
                                return "#9b3030"
                            if (modelData.state === "learn")
                                return "#f22b2b"
                            if (modelData.state === "bound")
                                return "#35b85a"
                            if (modelData.state === "blue")
                                return "#3186d7"
                            return "#a5a5a0"
                        }

                        SequentialAnimation on opacity {
                            running:
                                modelData.state === "learn"
                                && !modelData.evicting
                            loops: Animation.Infinite
                            NumberAnimation { from: 1.0; to: 0.2; duration: 240 }
                            NumberAnimation { from: 0.2; to: 1.0; duration: 240 }
                        }
                    }

                    Item {
                        id: f06Control
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 12
                        width: 40
                        height: 40
                        readonly property bool pitchBend:
                            modelData.displayType === "pitch_bend"
                        readonly property bool noteButton:
                            modelData.displayType === "note_button"
                        readonly property color bodyColor:
                            modelData.evicting ? "#d62f2f" : "#686864"

                        Rectangle {
                            visible: !f06Control.noteButton
                            anchors.centerIn: parent
                            width: 40
                            height: 40
                            radius: 20
                            color: "#353532"
                            border.color: "#d8d4c8"
                            border.width: 1
                        }

                        Rectangle {
                            id: knobSkirt
                            visible: !f06Control.noteButton
                            anchors.centerIn: parent
                            width: 34
                            height: 34
                            radius: 17
                            color: f06Control.bodyColor
                            border.color: "#f0ece1"
                            border.width: 2
                            rotation: f06Control.pitchBend
                                ? (Number(modelData.displayValue) - 64) * 180 / 64
                                : Number(modelData.displayValue) * 270 / 127 - 135

                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 3
                                width: 4
                                height: f06Control.pitchBend ? 10 : 14
                                radius: 2
                                color:
                                    f06Control.pitchBend ? "#82d6ff" : "#f2d56b"
                            }

                            Behavior on rotation {
                                NumberAnimation { duration: 90 }
                            }
                        }

                        Repeater {
                            model: 9
                            delegate: Rectangle {
                                visible: !f06Control.noteButton
                                width: 2
                                height: 5
                                radius: 1
                                color: "#252522"
                                opacity: 0.55
                                x: f06Control.width / 2 - width / 2
                                y: 1
                                transform: Rotation {
                                    origin.x: 1
                                    origin.y: f06Control.height / 2 - 1
                                    angle: index * 30 - 120
                                }
                            }
                        }

                        Rectangle {
                            visible: f06Control.pitchBend
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: -1
                            width: 2
                            height: 7
                            radius: 1
                            color: "#82d6ff"
                            opacity: 0.7
                        }

                        Rectangle {
                            visible: f06Control.noteButton
                            anchors.centerIn: parent
                            width: 36
                            height: 36
                            radius: 7
                            scale:
                                modelData.buttonDown && !modelData.evicting
                                ? 0.92
                                : 1.0
                            color:
                                modelData.buttonDown && !modelData.evicting
                                ? "#f4d85f"
                                : f06Control.bodyColor
                            border.color:
                                modelData.buttonDown && !modelData.evicting
                                ? "#fff4a8"
                                : "#e8e8df"
                            border.width: 2

                            Behavior on scale {
                                NumberAnimation { duration: 70 }
                            }

                            Text {
                                anchors.centerIn: parent
                                text: "BTN"
                                color:
                                    modelData.buttonDown && !modelData.evicting
                                    ? "#3c2d00"
                                    : "#f4f0e6"
                                font.pixelSize: 9
                                font.bold: true
                            }
                        }
                    }

                    Text {
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: modelData.displayLabel
                        color: "#292927"
                        font.pixelSize: 11
                    }

                    SequentialAnimation on opacity {
                        running: Boolean(modelData.evicting)
                        loops: 2
                        NumberAnimation { from: 1.0; to: 0.2; duration: 100 }
                        NumberAnimation { from: 0.2; to: 1.0; duration: 100 }
                    }

                    onClicked: {
                        backend.midiPlayer.selectControlIndicator(
                            modelData.channel,
                            modelData.controller
                        )
                    }
                }
            }
        }
    }

    Item {
        id: midiInputTechPanel

        readonly property int panelY:
            root.hostWindow.rhythmY
            + 6 * root.hostWindow.sectionHeight
            + 5 * root.hostWindow.sectionGap
        readonly property int panelBottom:
            root.hostWindow.chordRowsY
            + 3 * (
                root.hostWindow.rowHeight
                + root.hostWindow.rowSpacing
            )

        x: root.hostWindow.contentX
        y: panelY
        width:
            Math.max(
                0,
                midiCcPanel.x
                + midiCcPanel.width
                - root.hostWindow.contentX
            )
        height: Math.max(0, panelBottom - panelY)
        visible:
            height >= 24
            && root.midiInputTechModel.length > 0

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 18

            Repeater {
                model: root.midiInputTechModel

                delegate: Item {
                    required property var modelData

                    width: techText.implicitWidth + 20
                    height: 22

                    Rectangle {
                        id: techLed
                        x: 0
                        anchors.verticalCenter: parent.verticalCenter
                        width: 11
                        height: 11
                        radius: 5.5
                        color:
                            modelData.state === "unavailable"
                            ? "#c73434"
                            : "#35b85a"
                        border.width: 1
                        border.color:
                            modelData.state === "unavailable"
                            ? "#7e1c1c"
                            : "#1d7738"

                        SequentialAnimation on opacity {
                            running: modelData.state === "activity"
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: 1.0
                                to: 0.25
                                duration: 90
                            }
                            NumberAnimation {
                                from: 0.25
                                to: 1.0
                                duration: 90
                            }
                        }
                    }

                    Text {
                        id: techText
                        x: 17
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        color: "#363632"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }
                }
            }
        }
    }

    MidiStrumPad {
        x: root.hostWindow.strumX
        y: 0
        width: root.hostWindow.strumWidth
        height: root.hostWindow.totalControlHeight
        controller: backend
        rowIndex: root.activeMidiRow
        tuningCoupled: root.tuningCoupled
        padColor: root.activeStrumColor
    }
}
