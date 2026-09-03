import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "physical_controls"

Item {
    id: root

    required property var hostWindow
    property bool tuningCoupled: true
    property int activeMidiRow: 0
    property var midiControlModel: []
    property var inputTechModel: backend.midiPlayer.midiInputTechs
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
                        id: hardwareControl
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 9
                        width: 52
                        height: 52
                        readonly property bool pitchBend:
                            modelData.displayType === "pitch_bend"
                        readonly property bool noteButton:
                            modelData.displayType === "note_button"
                            || modelData.displayType === "button"

                        PhysicalRotary {
                            visible: !hardwareControl.noteButton
                            anchors.centerIn: parent
                            width: 52
                            height: 52
                            family:
                                modelData.displayProtocol === "osc" ? 1 : 6
                            encoder: hardwareControl.pitchBend
                            from: 0
                            to: 127
                            value: Number(modelData.displayValue)
                            physicalInteractive: false
                            opacity: modelData.evicting ? 0.55 : 1.0
                        }

                        PhysicalPushButton {
                            visible: hardwareControl.noteButton
                            anchors.centerIn: parent
                            width: 58
                            height: 42
                            family:
                                modelData.displayProtocol === "osc" ? 1 : 6
                            forcedDown:
                                modelData.buttonDown && !modelData.evicting
                        }
                    }

                    Text {
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width
                        text: modelData.displayLabel
                        color: "#292927"
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideMiddle
                    }

                    SequentialAnimation on opacity {
                        running: Boolean(modelData.evicting)
                        loops: 2
                        NumberAnimation { from: 1.0; to: 0.2; duration: 100 }
                        NumberAnimation { from: 0.2; to: 1.0; duration: 100 }
                    }

                    onClicked: {
                        backend.midiPlayer.clickControlIndicator(
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
            && root.inputTechModel.length > 0

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 18

            Repeater {
                model: root.inputTechModel

                delegate: InputTechnologyIndicator {
                    required property var modelData
                    technology: modelData
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
