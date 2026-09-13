pragma ComponentBehavior: Bound

import QtQuick

Item {
    id: root

    objectName: "migraine"

    property bool active: false
    property real targetCenterX: 0
    property real targetCenterY: 0
    property real morphPhase: 0
    property int morphFrame: 0
    property int fadeDuration: 500
    property int morphInterval: 34
    property bool animatePosition: true

    property real pendingMorphDistance: 0

    readonly property int morphFrameCount: 6

    opacity: 0.0
    visible: active || opacity > 0.001

    states: [
        State {
            name: "shown"
            when: root.active
            PropertyChanges {
                root.opacity: 0.65
            }
        },
        State {
            name: "fading"
            when: !root.active
            PropertyChanges {
                root.opacity: 0.0
            }
        }
    ]

    transitions: [
        Transition {
            from: "fading"
            to: "shown"
            NumberAnimation {
                property: "opacity"
                duration: 90
                easing.type: Easing.OutCubic
            }
        },
        Transition {
            from: "shown"
            to: "fading"
            NumberAnimation {
                property: "opacity"
                duration: root.fadeDuration
                easing.type: Easing.OutCubic
            }
        }
    ]

    function beginAt(x: real, y: real): void {
        const wasVisible = root.visible
        root.animatePosition = wasVisible
        root.targetCenterX = x
        root.targetCenterY = y
        root.x = x - root.width / 2
        root.y = y - root.height / 2
        root.animatePosition = true
        root.pendingMorphDistance = 0
        root.active = true
    }

    function moveTo(x: real, y: real): void {
        const distance = Math.hypot(
            x - root.targetCenterX,
            y - root.targetCenterY
        )
        root.pendingMorphDistance += distance
        root.targetCenterX = x
        root.targetCenterY = y
        root.x = x - root.width / 2
        root.y = y - root.height / 2
    }

    function advanceMorph(): void {
        if (root.pendingMorphDistance < 0.1)
            return
        root.morphPhase = (
            root.morphPhase
            + Math.min(0.24, root.pendingMorphDistance / 180)
        ) % 1.0
        root.morphFrame = Math.floor(
            root.morphPhase * root.morphFrameCount
        ) % root.morphFrameCount
        root.pendingMorphDistance = 0
    }

    function release(): void {
        root.pendingMorphDistance = 0
        root.active = false
    }

    Behavior on x {
        enabled: root.animatePosition
        SmoothedAnimation {
            velocity: 900
            maximumEasingTime: 100
        }
    }

    Behavior on y {
        enabled: root.animatePosition
        SmoothedAnimation {
            velocity: 900
            maximumEasingTime: 100
        }
    }

    Timer {
        interval: root.morphInterval
        running: root.active && root.pendingMorphDistance >= 0.1
        repeat: true
        onTriggered: root.advanceMorph()
    }

    Repeater {
        model: root.morphFrameCount

        Image {
            required property int index

            objectName: "migraineSpriteFrame"
            anchors.fill: parent
            source: Qt.resolvedUrl(
                "migraine_frames/migraine_" + index + ".svg"
            )
            sourceSize.width: root.width
            sourceSize.height: root.height
            asynchronous: false
            cache: true
            smooth: true
            visible: index === root.morphFrame
        }
    }
}
