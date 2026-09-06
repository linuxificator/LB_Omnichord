pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes

Item {
    id: root

    objectName: "migraine"

    property bool active: false
    property real targetCenterX: 0
    property real targetCenterY: 0
    property real morphPhase: 0
    property int fadeDuration: 500
    property int morphInterval: 34
    property bool animatePosition: true

    property real pendingMorphDistance: 0

    readonly property var pointAngles: [
        -0.08, 0.79, 1.72, 2.58, 3.48, 4.39, 5.32
    ]
    readonly property var pointLengths: [
        40.0, 35.5, 42.0, 37.0, 40.5, 36.5, 39.0
    ]
    readonly property string outlinePathData: buildOutlinePath()

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

    function polarPoint(angle, radius) {
        return Qt.point(
            root.width / 2 + Math.cos(angle) * radius,
            root.height / 2 + Math.sin(angle) * radius
        )
    }

    function appendPoint(path, command, point) {
        return path
            + command
            + point.x.toFixed(2)
            + " "
            + point.y.toFixed(2)
            + " "
    }

    function pointAngle(index) {
        return root.pointAngles[index]
            + 0.035
            * Math.sin(root.morphPhase * Math.PI * 2 + index * 1.7)
    }

    function pointLength(index) {
        return root.pointLengths[index]
            + 2.2
            * Math.sin(root.morphPhase * Math.PI * 2 + index * 1.31)
    }

    function shoulderRadius(index) {
        return 26.0
            + 1.5
            * Math.sin(root.morphPhase * Math.PI * 2 + index * 2.13)
    }

    function buildOutlinePath() {
        let path = ""
        const count = root.pointAngles.length
        const shoulderHalfAngle = 0.18
        const firstAngle = root.pointAngle(0)
        const firstShoulder = root.polarPoint(
            firstAngle - shoulderHalfAngle,
            root.shoulderRadius(0)
        )
        path = root.appendPoint(path, "M", firstShoulder)

        for (let index = 0; index < count; ++index) {
            const angle = root.pointAngle(index)
            const shoulder = root.shoulderRadius(index)
            const tip = root.polarPoint(angle, root.pointLength(index))
            const leftControl = root.polarPoint(angle - 0.075, shoulder + 7)
            const rightControl = root.polarPoint(angle + 0.075, shoulder + 7)
            const rightShoulder = root.polarPoint(
                angle + shoulderHalfAngle,
                shoulder
            )
            const nextIndex = (index + 1) % count
            let nextAngle = root.pointAngle(nextIndex)
            if (nextIndex === 0)
                nextAngle += Math.PI * 2
            const nextShoulder = root.polarPoint(
                nextAngle - shoulderHalfAngle,
                root.shoulderRadius(nextIndex)
            )
            const valleyAngle = (
                angle + shoulderHalfAngle
                + nextAngle - shoulderHalfAngle
            ) / 2
            const valleyRadius = 22.5
                + 1.4
                * Math.cos(
                    root.morphPhase * Math.PI * 2 + index * 1.51
                )
            const valleyControl = root.polarPoint(
                valleyAngle,
                valleyRadius
            )

            path = root.appendPoint(path, "Q", leftControl)
            path = root.appendPoint(path, "", tip)
            path = root.appendPoint(path, "Q", rightControl)
            path = root.appendPoint(path, "", rightShoulder)
            path = root.appendPoint(path, "Q", valleyControl)
            path = root.appendPoint(path, "", nextShoulder)
        }
        return path + "Z"
    }

    function beginAt(x, y) {
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

    function moveTo(x, y) {
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

    function advanceMorph() {
        if (root.pendingMorphDistance < 0.1)
            return
        root.morphPhase = (
            root.morphPhase
            + Math.min(0.24, root.pendingMorphDistance / 180)
        ) % 1.0
        root.pendingMorphDistance = 0
    }

    function release() {
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

    Item {
        id: cachedEdge

        objectName: "migraineCachedEdge"
        anchors.fill: parent

        // The pointed RGB edge changes at no more than 30 Hz and is cached as
        // one texture. Pointer tracking, fade and position smoothing then only
        // transform that texture; they do not rebuild particle emitters or
        // retessellate paths at the display's 120 Hz refresh rate.
        layer.enabled: true
        layer.smooth: true

        Repeater {
            id: chromaRepeater
            model: 3

            Shape {
                id: chromaLayer

                required property int index

                readonly property color edgeColor:
                    ["#ff2448", "#38ff70", "#3976ff"][index]
                readonly property color haloColor:
                    ["#4dff2448", "#4d38ff70", "#4d3976ff"][index]
                readonly property real registration:
                    index - 1
                readonly property real registrationAngle:
                    root.morphPhase * Math.PI * 2
                readonly property real registrationX:
                    registration * 3.4 * Math.cos(registrationAngle)
                readonly property real registrationY:
                    registration * 3.4 * Math.sin(registrationAngle)

                objectName: "migraineSharpChromaEdge"
                x: chromaLayer.registrationX
                y: chromaLayer.registrationY
                width: root.width
                height: root.height
                antialiasing: true

                ShapePath {
                    strokeColor: chromaLayer.haloColor
                    strokeWidth: 6.0
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.MiterJoin

                    PathSvg {
                        path: root.outlinePathData
                    }
                }

                ShapePath {
                    strokeColor: chromaLayer.edgeColor
                    strokeWidth: 2.2
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.MiterJoin

                    PathSvg {
                        path: root.outlinePathData
                    }
                }
            }
        }
    }
}
