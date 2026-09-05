pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Particles
import QtQuick.Shapes

Item {
    id: root

    objectName: "migraine"

    property bool active: false
    property real targetCenterX: 0
    property real targetCenterY: 0
    property real morphPhase: 0
    property int fadeDuration: 500
    property bool animatePosition: true

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

    function haloRadius(angle) {
        let nearestDistance = Math.PI
        let nearestIndex = 0
        for (let index = 0; index < root.pointAngles.length; ++index) {
            let distance = Math.abs(angle - root.pointAngle(index))
            distance = Math.min(distance, Math.PI * 2 - distance)
            if (distance < nearestDistance) {
                nearestDistance = distance
                nearestIndex = index
            }
        }
        const pointStrength = Math.pow(
            Math.max(0, 1 - nearestDistance / 0.23),
            2.2
        )
        return root.shoulderRadius(nearestIndex)
            + pointStrength
            * (root.pointLength(nearestIndex) - root.shoulderRadius(nearestIndex))
    }

    function beginAt(x, y) {
        const wasVisible = root.visible
        root.animatePosition = wasVisible
        root.targetCenterX = x
        root.targetCenterY = y
        root.x = x - root.width / 2
        root.y = y - root.height / 2
        root.animatePosition = true
        root.active = true
        for (let index = 0; index < chromaRepeater.count; ++index) {
            const layer = chromaRepeater.itemAt(index)
            if (layer)
                layer.burst()
        }
    }

    function moveTo(x, y) {
        const distance = Math.hypot(
            x - root.targetCenterX,
            y - root.targetCenterY
        )
        root.morphPhase = (
            root.morphPhase + Math.min(0.24, distance / 180)
        ) % 1.0
        root.targetCenterX = x
        root.targetCenterY = y
        root.x = x - root.width / 2
        root.y = y - root.height / 2
    }

    function release() {
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

    ParticleSystem {
        id: particleSystem
    }

    ImageParticle {
        objectName: "migraineRedParticles"
        system: particleSystem
        groups: ["red"]
        source: "assets/migraine_particle.png"
        color: "#ff2448"
        colorVariation: 0.01
        alpha: 0.15
        alphaVariation: 0.03
        rotationVariation: 180
        entryEffect: ImageParticle.Fade
    }

    ImageParticle {
        objectName: "migraineGreenParticles"
        system: particleSystem
        groups: ["green"]
        source: "assets/migraine_particle.png"
        color: "#38ff70"
        colorVariation: 0.01
        alpha: 0.14
        alphaVariation: 0.03
        rotationVariation: 180
        entryEffect: ImageParticle.Fade
    }

    ImageParticle {
        objectName: "migraineBlueParticles"
        system: particleSystem
        groups: ["blue"]
        source: "assets/migraine_particle.png"
        color: "#3976ff"
        colorVariation: 0.01
        alpha: 0.15
        alphaVariation: 0.03
        rotationVariation: 180
        entryEffect: ImageParticle.Fade
    }

    Repeater {
        id: chromaRepeater
        model: 3

        Item {
            id: chromaLayer

            required property int index

            readonly property string groupName:
                ["red", "green", "blue"][index]
            readonly property color edgeColor:
                ["#ff2448", "#38ff70", "#3976ff"][index]
            readonly property real registration:
                index - 1
            readonly property real registrationAngle:
                root.morphPhase * Math.PI * 2
            readonly property real registrationX:
                registration * 3.4 * Math.cos(registrationAngle)
            readonly property real registrationY:
                registration * 3.4 * Math.sin(registrationAngle)

            function burst() {
                for (let index = 0; index < haloRepeater.count; ++index) {
                    const emitter = haloRepeater.itemAt(index)
                    if (emitter)
                        emitter.burst(1)
                }
            }

            Shape {
                objectName: "migraineSharpChromaEdge"
                x: chromaLayer.registrationX
                y: chromaLayer.registrationY
                width: root.width
                height: root.height
                antialiasing: true

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

            Repeater {
                id: haloRepeater
                model: 56

                Emitter {
                    id: haloEmitter

                    required property int index

                    readonly property real angle:
                        index * Math.PI * 2 / haloRepeater.count
                    readonly property real radius:
                        root.haloRadius(angle)

                    x:
                        root.width / 2
                        + Math.cos(angle) * radius
                        + chromaLayer.registrationX
                    y:
                        root.height / 2
                        + Math.sin(angle) * radius
                        + chromaLayer.registrationY
                    width: 1
                    height: 1
                    system: particleSystem
                    group: chromaLayer.groupName
                    enabled: root.active
                    emitRate: 2
                    lifeSpan: 280
                    lifeSpanVariation: 40
                    maximumEmitted: 4
                    size: 9
                    endSize: 6
                    sizeVariation: 2

                    velocity: AngleDirection {
                        angle: haloEmitter.angle * 180 / Math.PI
                        angleVariation: 10
                        magnitude: 2
                        magnitudeVariation: 1
                    }
                }
            }
        }
    }

    Wander {
        system: particleSystem
        groups: ["red", "green", "blue"]
        xVariance: 1.2
        yVariance: 1.2
        pace: 24
    }
}
