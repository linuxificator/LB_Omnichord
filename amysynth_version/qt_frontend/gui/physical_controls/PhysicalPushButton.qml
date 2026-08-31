import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "AudioHardwareStyle.js" as AudioStyle

Button {
    id: control

    property int family: 6
    property bool forcedDown: false
    readonly property bool physicallyDown: down || forcedDown
    readonly property var s: AudioStyle.family(family)

    padding: 0
    enabled: false
    opacity: 1.0

    background: Item {
        anchors.fill: parent

        // 1: panel cutout / contact shadow
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.92
            height: parent.height * 0.74
            radius: 8
            color: "#44000000"
            y: parent.height * 0.16
        }

        // 2: F06 bezel / mounting rim
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.90
            height: parent.height * 0.70
            radius: 8
            border.width: 2
            border.color: control.s.bezel
            gradient: Gradient {
                GradientStop { position: 0.00; color: control.s.metalTop }
                GradientStop { position: 0.45; color: control.s.metalMid }
                GradientStop { position: 1.00; color: control.s.metalBottom }
            }
        }

        Rectangle {
            id: capShadowSource
            x: parent.width * 0.17
            y: parent.height * 0.26 + (control.physicallyDown ? 3 : 0)
            width: parent.width * 0.66
            height: parent.height * 0.38
            radius: 5
            color: "white"
            visible: false
            layer.enabled: true
        }

        MultiEffect {
            anchors.fill: capShadowSource
            source: capShadowSource
            shadowEnabled: true
            shadowColor: "#77000000"
            shadowHorizontalOffset: 1
            shadowVerticalOffset: control.physicallyDown ? 1 : 4
            shadowBlur: 0.34
            blurMax: 10
        }

        // 3-5: physical plunger/cap with lamp material and highlight
        Rectangle {
            id: plunger
            x: parent.width * 0.15
            y: parent.height * 0.20 + (control.physicallyDown ? 3 : 0)
            width: parent.width * 0.70
            height: parent.height * 0.44
            radius: 5
            border.width: 1
            border.color: control.physicallyDown ? "#fff7f7" : "#efe8df"
            gradient: Gradient {
                GradientStop { position: 0.00; color: control.physicallyDown ? "#fff3f3" : "#ffe3dc" }
                GradientStop { position: 0.22; color: control.physicallyDown ? "#ffb6b6" : "#ff9b91" }
                GradientStop { position: 0.62; color: control.physicallyDown ? "#ff6868" : "#f45d5d" }
                GradientStop { position: 1.00; color: control.physicallyDown ? "#bd2d2d" : "#cf3e3e" }
            }

            Rectangle {
                x: 5
                y: control.physicallyDown ? 3 : 2
                width: parent.width - 10
                height: 3
                radius: 2
                color: "#ffffff"
                opacity: control.physicallyDown ? 0.45 : 0.76
            }

            Behavior on y {
                NumberAnimation { duration: 65 }
            }
        }
    }

    contentItem: Item {}
}
