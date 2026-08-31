import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
import "AudioHardwareStyle.js" as AudioStyle

Dial {
    id: control

    property int family: 6
    property bool encoder: false
    property bool calibrated: family === 6 && !encoder
    property bool physicalInteractive: false
    readonly property var s: AudioStyle.family(family)

    from: 0
    to: 127
    value: 0
    inputMode: Dial.Vertical
    enabled: physicalInteractive
    opacity: 1.0

    readonly property real size: Math.min(width, height)
    readonly property real center: size / 2
    readonly property real capSize: size * 0.68
    readonly property real capX: width / 2 - capSize / 2
    readonly property real capY: height / 2 - capSize / 2
    readonly property real normalizedValue:
        Math.max(
            0.0,
            Math.min(
                1.0,
                (Number(value) - Number(from))
                / Math.max(1e-9, Number(to) - Number(from))
            )
        )
    readonly property real capRotation:
        encoder
        ? ((Number(value) - (Number(from) + Number(to)) / 2)
            * 270 / Math.max(1e-9, Number(to) - Number(from)))
        : (-135 + normalizedValue * 270)

    background: Item {
        anchors.fill: parent

        // 1: panel recess
        Rectangle {
            anchors.centerIn: parent
            width: control.size * 0.92
            height: width
            radius: width / 2
            color: Qt.darker(control.s.panel, 1.12)
            border.width: 1
            border.color: control.s.bezel
        }

        // 2: calibrated F06 mounting skirt / scale ring
        Rectangle {
            anchors.centerIn: parent
            width: control.size * 0.98
            height: width
            radius: width / 2
            color: control.encoder ? control.s.bezel : control.s.metalMid
            border.width: 1
            border.color: control.s.bezel
        }

        Shape {
            anchors.fill: parent
            visible: control.calibrated
            ShapePath {
                strokeColor: control.s.bezel
                strokeWidth: 2
                fillColor: "transparent"
                PathAngleArc {
                    centerX: control.width / 2
                    centerY: control.height / 2
                    radiusX: control.size * 0.43
                    radiusY: control.size * 0.43
                    startAngle: 135
                    sweepAngle: 270
                }
            }
        }

        // Calibrated tick ring for console potentiometers. Encoders deliberately
        // do not get a 270-degree hard-stop scale.
        Repeater {
            model: control.calibrated ? 11 : 0
            delegate: Item {
                required property int index
                anchors.fill: parent
                rotation: -135 + index * 27
                Rectangle {
                    x: parent.width / 2 - 1
                    y: control.size * 0.03
                    width: 2
                    height: index % 5 === 0
                        ? control.size * 0.12
                        : control.size * 0.075
                    radius: 1
                    color: control.s.bezel
                }
            }
        }
    }

    handle: Item {
        id: rotatingCap
        width: control.capSize
        height: control.capSize
        x: control.capX
        y: control.capY
        rotation: control.capRotation

        // 7: local/contact shadow without virtual lighting effects.
        Rectangle {
            x: 4
            y: 6
            width: parent.width - 4
            height: parent.height - 2
            radius: width / 2
            color: "#33000000"
        }

        // 3-5: cap, depth and material shading
        Rectangle {
            id: capBody
            anchors.fill: parent
            radius: width / 2
            border.width: 2
            border.color: control.s.bezel
            gradient: Gradient {
                GradientStop { position: 0.00; color: control.s.capTop }
                GradientStop { position: 0.25; color: control.s.capTop }
                GradientStop { position: 0.58; color: control.s.capMid }
                GradientStop { position: 1.00; color: control.s.capBottom }
            }

            Repeater {
                model: control.encoder ? 16 : 18
                delegate: Item {
                    required property int index
                    anchors.fill: parent
                    rotation: index * (control.encoder ? 22.5 : 20)
                    Rectangle {
                        x: parent.width / 2 - 1
                        y: 2
                        width: 2
                        height: control.size * 0.09
                        radius: 1
                        color: control.s.bezel
                        opacity: 0.86
                    }
                }
            }

            // 5: muted top bevel; no white virtual-lighting patch.
            Rectangle {
                x: parent.width * 0.16
                y: parent.height * 0.11
                width: parent.width * 0.47
                height: 2
                radius: height / 2
                color: "#55cfc9b9"
            }

            // 6: physical index. Encoder uses a short notch/dot and no scale.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.09
                width: 4
                height: control.encoder
                    ? parent.height * 0.16
                    : parent.height * 0.30
                radius: 2
                color: control.s.index
            }

            // Mechanical center boss / push-center.
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * (control.encoder ? 0.23 : 0.17)
                height: width
                radius: width / 2
                color: Qt.darker(control.s.capMid, 1.15)
                border.width: 1
                border.color: control.s.bezel
            }
        }

        Behavior on rotation {
            NumberAnimation { duration: 90 }
        }
    }
}
