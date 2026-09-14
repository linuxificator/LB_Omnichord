pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root
    required property var controller
    required property int rowIndex
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

    readonly property bool drumRow: root.rowIndex === 5
    readonly property string synthKind: {
        root.controller.stateVersion
        return root.controller.synthKind(root.rowIndex)
    }
    readonly property int browserIndex: {
        root.controller.stateVersion
        return root.controller.synthBrowserIndex(root.rowIndex)
    }
    // Keep the wheel's model stable while unrelated row state changes.  A
    // freshly converted Python list on every stateVersion update makes the
    // Tumbler rebuild itself while it is synchronizing currentIndex, which can
    // create a QML binding loop under rapid program changes.
    property var browserModel: root.controller.synthBrowserNames(root.rowIndex)
    readonly property var sampleColumns: {
        root.controller.stateVersion
        return root.controller.sampleChoiceColumns(root.rowIndex)
    }
    readonly property bool sampleSustainAvailable: {
        root.controller.stateVersion
        return root.controller.sampleSustainAvailable(root.rowIndex)
    }
    readonly property bool sampleSustainEnabled: {
        root.controller.stateVersion
        return root.controller.sustainEnabled(root.rowIndex)
    }
    readonly property var commonControls: {
        root.controller.stateVersion
        return root.controller.commonControls(root.rowIndex)
    }
    readonly property var extraControls: {
        root.controller.stateVersion
        return root.controller.extraControls(root.rowIndex)
    }

    onBrowserModelChanged: Qt.callLater(root.synchronizeWheel)
    onBrowserIndexChanged: Qt.callLater(root.synchronizeWheel)

    function markInteraction() { root.interacted(root.rowIndex) }
    function refreshBrowserModel() {
        const next = root.controller.synthBrowserNames(root.rowIndex)
        if (next.length !== root.browserModel.length) {
            root.browserModel = next
            return
        }
        for (let index = 0; index < next.length; ++index) {
            if (next[index] !== root.browserModel[index]) {
                root.browserModel = next
                return
            }
        }
    }
    function synchronizeWheel() {
        if (!synthWheel.initialized) return
        const wanted = root.controller.synthBrowserIndex(root.rowIndex)
        if (synthWheel.currentIndex !== wanted) {
            synthWheel.syncing = true
            synthWheel.currentIndex = wanted
            Qt.callLater(function() { synthWheel.syncing = false })
        }
    }
    function midiButtonHandled(target) {
        const learned = root.controller.activateControlTarget(target)
        if (learned) return true
        return root.controller.midiButtonTargetBlocked(target)
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: root.panelColor
        border.color: root.borderColor
        border.width: 1
    }
    TapHandler {
        gesturePolicy: TapHandler.DragThreshold
        onPressedChanged: if (pressed) root.markInteraction()
    }

    Column {
        x: (root.leftRailWidth - width) / 2
        y: root.drumRow ? (root.height - 42) / 2 : 4
        width: 50
        spacing: 8
        PresetResetButton {
            visible: !root.drumRow
            width: 42; height: 42
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.synthKind === "sample" ? "PCM" : "SYN"
            panelColor: root.synthKind === "sample"
                ? Qt.darker(root.panelColor, 1.16) : Qt.lighter(root.panelColor, 1.05)
            borderColor: root.borderColor
            textColor: root.textColor
            onClicked: {
                root.controller.toggleSynthKind(root.rowIndex)
                root.markInteraction()
            }
        }
        PresetResetButton {
            width: 42; height: 42
            anchors.horizontalCenter: parent.horizontalCenter
            text: "RST"
            panelColor: Qt.lighter(root.panelColor, 1.05)
            borderColor: root.borderColor
            textColor: root.textColor
            onClicked: {
                root.controller.resetRow(root.rowIndex)
                root.markInteraction()
            }
        }
    }

    Frame {
        id: wheelFrame
        x: root.contentX; y: 0
        width: root.wheelWidth; height: parent.height; padding: 0
        background: Rectangle {
            radius: 10
            color: Qt.lighter(root.accentColor, 1.45)
            border.color: root.borderColor
            border.width: 1
        }
        Tumbler {
            id: synthWheel
            objectName: root.drumRow ? "midiDrumKitWheel" : "midiInstrumentWheel" + root.rowIndex
            anchors.fill: parent; anchors.margins: 3
            model: root.browserModel
            visibleItemCount: 3; wrap: true
            property bool initialized: false
            property bool syncing: false
            Component.onCompleted: {
                syncing = true
                currentIndex = root.browserIndex
                Qt.callLater(function() {
                    synthWheel.syncing = false
                    synthWheel.initialized = true
                })
            }
            Connections {
                target: root.controller
                function onStateChanged() {
                    root.refreshBrowserModel()
                    Qt.callLater(root.synchronizeWheel)
                }
                function onDrumKitChanged() {
                    if (root.drumRow) {
                        root.refreshBrowserModel()
                        Qt.callLater(root.synchronizeWheel)
                    }
                }
            }
            delegate: Item {
                id: synthItem
                required property var modelData
                required property int index
                width: synthWheel.width
                height: synthWheel.height / synthWheel.visibleItemCount
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: synthItem.modelData
                    color: root.textColor
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: Math.abs(Tumbler.displacement) < 0.5 ? 18 : 15
                    font.bold: Math.abs(Tumbler.displacement) < 0.5
                    opacity: 0.30 + Math.max(0, 1 - Math.abs(Tumbler.displacement)) * 0.70
                }
                TapHandler {
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: synthWheel.currentIndex = synthItem.index
                }
            }
            onCurrentIndexChanged: {
                if (initialized && !syncing && currentIndex >= 0) {
                    root.controller.setSynthBrowserIndex(root.rowIndex, currentIndex)
                    root.markInteraction()
                }
            }
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height / 2 - 16
            width: parent.width - 12; height: 32; radius: 7
            color: "transparent"
            border.color: Qt.darker(root.accentColor, 1.25)
            border.width: 2
        }
    }

    MidiChannelButton {
        id: channelButton
        x: root.contentX + root.wheelWidth + 7
        y: (parent.height - height) / 2
        midiTarget: ({"screen": "midi", "kind": "button", "action": "cycle_channel", "row": root.rowIndex})
        channel: {
            root.controller.stateVersion
            return root.controller.channel(root.rowIndex)
        }
        panelColor: Qt.lighter(root.panelColor, 1.05)
        pressedPanelColor: Qt.darker(root.panelColor, 1.12)
        borderColor: root.accentColor
        textColor: root.textColor
        showMidiLed: true
        midiControlRouter: root.controller
        onClicked: {
            if (!root.midiButtonHandled(channelButton.midiTarget)) {
                root.controller.cycleChannel(root.rowIndex)
                root.markInteraction()
            }
        }
    }

    Column {
        id: sliderColumn
        visible: !root.drumRow && root.synthKind !== "sample"
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
                anchors.fill: parent; spacing: 8
                Repeater {
                    id: extraRepeater
                    model: root.extraControls
                    delegate: ParameterSlider {
                        required property var modelData
                        width: (extraRow.width - Math.max(0, extraRepeater.count - 1) * extraRow.spacing) / Math.max(1, extraRepeater.count)
                        height: extraRow.height
                        control: modelData
                        textColor: root.textColor
                        trackColor: Qt.lighter(root.panelColor, 1.08)
                        fillColor: root.accentColor
                        handleColor: "#ffffff"
                        borderColor: Qt.darker(root.accentColor, 1.2)
                        midiControlRouter: root.controller
                        midiTarget: ({"screen": "midi", "kind": "synth_control", "row": root.rowIndex, "control": modelData.key})
                        onActivated: root.markInteraction()
                        onEdited: (key, value) => {
                            root.controller.editControl(root.rowIndex, key, value)
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
                anchors.fill: parent; spacing: 8
                Repeater {
                    id: commonRepeater
                    model: root.commonControls
                    delegate: ParameterSlider {
                        required property var modelData
                        width: (commonRow.width - Math.max(0, commonRepeater.count - 1) * commonRow.spacing) / Math.max(1, commonRepeater.count)
                        height: commonRow.height
                        control: modelData
                        textColor: root.textColor
                        trackColor: Qt.lighter(root.panelColor, 1.08)
                        fillColor: root.accentColor
                        handleColor: "#ffffff"
                        borderColor: Qt.darker(root.accentColor, 1.2)
                        midiControlRouter: root.controller
                        midiTarget: ({"screen": "midi", "kind": "synth_control", "row": root.rowIndex, "control": modelData.key})
                        onActivated: root.markInteraction()
                        onEdited: (key, value) => {
                            root.controller.editControl(root.rowIndex, key, value)
                            root.markInteraction()
                        }
                    }
                }
            }
        }
    }

    Item {
        id: sampleChoiceRow
        visible: !root.drumRow && root.synthKind === "sample"
        x: channelButton.x + channelButton.width + 10
        y: 0
        width: root.volumeX - x - 8
        height: parent.height
        Row {
            id: choiceColumnsRow
            anchors.fill: parent
            spacing: 8
            Repeater {
                id: sampleColumnRepeater
                model: root.sampleColumns
                delegate: Column {
                    id: sampleColumn
                    required property var modelData
                    width: (choiceColumnsRow.width - Math.max(0, sampleColumnRepeater.count - 1) * choiceColumnsRow.spacing) / Math.max(1, sampleColumnRepeater.count)
                    height: choiceColumnsRow.height; spacing: 8
                    Button {
                        width: parent.width; height: 48
                        visible: sampleColumn.modelData.showVariant
                        text: sampleColumn.modelData.label
                        font.pixelSize: 12; font.bold: sampleColumn.modelData.selected
                        background: Rectangle {
                            radius: 8
                            color: sampleColumn.modelData.selected ? root.accentColor : Qt.lighter(root.panelColor, 1.08)
                            border.color: root.borderColor
                            border.width: sampleColumn.modelData.selected ? 2 : 1
                        }
                        onClicked: {
                            const choices = sampleColumn.modelData.choices
                            if (sampleColumn.modelData.variantSelectable && choices.length > 0)
                                root.controller.selectSampleChoice(root.rowIndex, choices[0].synthIndex)
                        }
                    }
                    Row {
                        width: parent.width; height: 48; spacing: 4
                        Repeater {
                            id: articulationRepeater
                            model: sampleColumn.modelData.choices.length > 1 ? sampleColumn.modelData.choices : []
                            delegate: Button {
                                id: articulationButton
                                required property var modelData
                                width: (sampleColumn.width - Math.max(0, articulationRepeater.count - 1) * 4) / Math.max(1, articulationRepeater.count)
                                height: 48
                                text: articulationButton.modelData.label
                                font.pixelSize: 11; font.bold: articulationButton.modelData.selected
                                background: Rectangle {
                                    radius: 8
                                    color: articulationButton.modelData.selected ? root.accentColor : Qt.lighter(root.panelColor, 1.16)
                                    border.color: root.borderColor
                                    border.width: articulationButton.modelData.selected ? 2 : 1
                                }
                                onClicked: root.controller.selectSampleChoice(root.rowIndex, articulationButton.modelData.synthIndex)
                            }
                        }
                    }
                }
            }
        }
        Button {
            visible: root.sampleSustainAvailable
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            width: Math.min(150, parent.width / 2)
            height: 44
            text: root.sampleSustainEnabled ? "SUSTAIN ON" : "SUSTAIN OFF"
            font.pixelSize: 11
            font.bold: true
            background: Rectangle {
                radius: 8
                color: root.sampleSustainEnabled
                    ? root.accentColor : Qt.lighter(root.panelColor, 1.16)
                border.color: root.borderColor
                border.width: root.sampleSustainEnabled ? 2 : 1
            }
            onClicked: {
                root.controller.toggleSustain(root.rowIndex)
                root.markInteraction()
            }
        }
    }

    VerticalVolume {
        x: root.volumeX; y: 0
        width: root.volumeWidth; height: parent.height
        currentValue: {
            root.controller.stateVersion
            return root.controller.volume(root.rowIndex)
        }
        panelColor: Qt.lighter(root.panelColor, 1.03)
        panelBorderColor: root.borderColor
        fillColor: root.accentColor
        textColor: root.textColor
        midiControlRouter: root.controller
        midiTarget: ({"screen": "midi", "kind": "volume", "row": root.rowIndex})
        onEdited: (value) => {
            root.controller.setVolume(root.rowIndex, value)
            root.markInteraction()
        }
    }
}
