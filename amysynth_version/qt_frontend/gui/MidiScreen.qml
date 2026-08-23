import QtQuick
import QtQuick.Window

Item {
    id: root

    required property var hostWindow
    property bool tuningCoupled: true
    property color activeStrumColor: "#5d9fd0"

    signal showOmniRequested()
    signal toggleTuningCouplingRequested()

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

    Rectangle {
        anchors.fill: parent
        color: "#f4f0e6"
    }

    // Consume unused-space touches so no hidden Omnichord control underneath
    // the MIDI screen can be activated through a transparent gap.
    MouseArea {
        anchors.fill: parent
    }

    QtObject {
        id: midiReverbState

        property real reverbLevel: 0.0
        property real reverbLiveness: 0.5
        property real reverbDamping: 0.5
        property bool reverbDrumsIncluded: false

        function setReverbLevel(value) {
            reverbLevel = Math.max(0, Math.min(2, Number(value)))
        }

        function setReverbLiveness(value) {
            reverbLiveness = Math.max(0, Math.min(1, Number(value)))
        }

        function setReverbDamping(value) {
            reverbDamping = Math.max(0, Math.min(1, Number(value)))
        }

        function toggleReverbDrums() {
            reverbDrumsIncluded = !reverbDrumsIncluded
        }
    }

    Item {
        id: midiTitle
        x: 0
        y: 0
        width: root.width
        height: root.hostWindow.titleHeight
        visible: root.hostWindow.titleHeight > 0

        ReverbPanel {
            id: reverbPanel
            x: 0
            y: 0
            width: 520
            height: parent.height
            controller: midiReverbState
        }

        Text {
            x: reverbPanel.width + 12
            y: 0
            width: Math.max(0, root.hostWindow.strumX - x - 12)
            height: parent.height
            text: headerTitleText
            color: "#493a38"
            font.family: headerTitleFont
            font.pixelSize: Math.max(14, midiTitle.height * 0.62)
            font.weight: Font.Medium
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }

    MidiUtilitySection {
        x: root.hostWindow.contentX
        y: root.hostWindow.utilityY
        width:
            root.hostWindow.volumeX
            + root.hostWindow.volumeWidth
            - root.hostWindow.contentX
        height: root.hostWindow.sectionHeight

        controller: backend
        tuningModeModel: tuningModeNames
        fullScreen:
            root.hostWindow.visibility
            === Window.FullScreen
        leftExtension: root.hostWindow.leftRailWidth
        tuningCoupled: root.tuningCoupled

        onToggleFullscreenRequested:
            root.hostWindow.toggleFullscreenMode()

        onToggleTuningCouplingRequested:
            root.toggleTuningCouplingRequested()
    }

    // Keep the orange UP/DWN controls visually identical, but MIDI tuning is
    // UI-only in this first stage so these deliberately have no callbacks.
    PresetResetButton {
        x: (root.hostWindow.leftRailWidth - width) / 2
        y: root.hostWindow.utilityY + 7
        width: 42
        height: 42
        text: "UP"
        panelColor: "#efb05c"
        borderColor: "#a75d0a"
        textColor: "#492606"
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
        panelColor: "#efb05c"
        borderColor: "#a75d0a"
        textColor: "#492606"
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

            synthModel: synthNames
            leftRailWidth: root.hostWindow.leftRailWidth
            contentX: root.hostWindow.contentX
            volumeX: root.hostWindow.volumeX
            volumeWidth: root.hostWindow.volumeWidth
            wheelWidth: root.hostWindow.wheelWidth

            panelColor: modelData.panel
            borderColor: modelData.border
            accentColor: modelData.accent
            textColor: modelData.text

            onInteracted: (barColor) =>
                root.activeStrumColor = barColor
        }
    }

    RainbowModeButton {
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
        height: root.hostWindow.rowHeight
        text: "OMNI"
        onClicked: root.showOmniRequested()
    }

    MidiStrumPad {
        x: root.hostWindow.strumX
        y: 0
        width: root.hostWindow.strumWidth
        height: root.hostWindow.totalControlHeight
        padColor: root.activeStrumColor
    }
}
