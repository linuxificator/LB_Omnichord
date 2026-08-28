import QtQuick

Rectangle {
    id: root

    required property var midiControlRouter
    required property string targetScreen
    property int targetPreset: 0
    property bool locationEnabled: true

    color: "#31d158"
    border.color: "#14752f"
    border.width: 1
    opacity: 0.0

    onLocationEnabledChanged: {
        if (!locationEnabled) {
            locationAnimation.stop()
            opacity = 0.0
        }
    }

    Connections {
        target: root.midiControlRouter

        function onBindingLocationRequested(screen, presetNumber) {
            if (
                root.locationEnabled
                && screen === root.targetScreen
                && (
                    root.targetPreset <= 0
                    || presetNumber === root.targetPreset
                )
            ) {
                locationAnimation.restart()
            }
        }
    }

    SequentialAnimation {
        id: locationAnimation
        loops: 5

        NumberAnimation {
            target: root
            property: "opacity"
            from: 0.0
            to: 1.0
            duration: 90
        }
        PauseAnimation { duration: 110 }
        NumberAnimation {
            target: root
            property: "opacity"
            from: 1.0
            to: 0.0
            duration: 90
        }
        PauseAnimation { duration: 110 }
    }
}
