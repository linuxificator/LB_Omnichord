import QtQuick

Rectangle {
    id: root

    property var midiControlRouter: null
    property var midiTarget: ({})

    width: 8
    height: 8
    radius: width / 2
    visible: root.midiControlRouter !== null

    readonly property string midiVisualState: {
        if (root.midiControlRouter === null)
            return "idle"
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.controlTargetVisualState(
            root.midiTarget
        )
    }
    readonly property bool midiBound: {
        if (root.midiControlRouter === null)
            return false
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.isControlTargetBound(
            root.midiTarget
        )
    }
    readonly property bool midiPresetFeedback:
        root.midiVisualState === "preset-displaced"
        || root.midiVisualState === "preset-incoming"

    color: {
        if (root.midiVisualState === "preset-displaced")
            return "#f22b2b"
        if (root.midiVisualState === "preset-incoming")
            return "#3186d7"
        return root.midiBound ? "#35b85a" : "#a5a5a0"
    }

    SequentialAnimation on opacity {
        running: root.midiPresetFeedback
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.2; duration: 110 }
        NumberAnimation { from: 0.2; to: 1.0; duration: 110 }
    }
}
