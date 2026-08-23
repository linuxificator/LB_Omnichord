import QtQuick

Item {
    id: root

    property color padColor: "#5d9fd0"
    property bool gestureActive: false

    Rectangle {
        anchors.fill: parent
        radius: 13
        border.color: Qt.lighter(root.padColor, 1.35)
        border.width: 2

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Qt.darker(root.padColor, 1.20)
            }
            GradientStop {
                position: 0.5
                color: Qt.darker(root.padColor, 1.65)
            }
            GradientStop {
                position: 1.0
                color: Qt.darker(root.padColor, 2.15)
            }
        }
    }

    Repeater {
        model: 15

        Rectangle {
            required property int index

            x: 12
            y:
                18
                + index
                * (root.height - 36) / 14
            width: root.width - 24
            height: index % 2 === 0 ? 2 : 1
            radius: 1
            color:
                index % 2 === 0
                ? Qt.lighter(root.padColor, 1.35)
                : Qt.lighter(root.padColor, 1.12)
            opacity: root.gestureActive ? 1.0 : 0.75
        }
    }

    // MIDI-screen strumming is deliberately UI-only for this stage. Capture
    // the touch so the outer Flickable does not scroll, but send no music.
    MultiPointTouchArea {
        anchors.fill: parent
        z: 1000
        minimumTouchPoints: 1
        maximumTouchPoints: 1
        mouseEnabled: true

        onPressed:
            root.gestureActive = true

        onReleased:
            root.gestureActive = false

        onCanceled:
            root.gestureActive = false

        onGestureStarted: (gesture) =>
            gesture.grab()
    }
}
