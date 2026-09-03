import QtQuick
import QtQuick.Controls
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

        // 1: F06 bezel / mounting rim
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

        // 2-4: physical plunger/cap with lamp material
        Rectangle {
            id: plunger
            objectName: "physicalButtonPlunger"
            x: parent.width * 0.15
            y: parent.height * 0.20 + (control.physicallyDown ? 3 : 0)
            width: parent.width * 0.70
            height: parent.height * 0.44
            radius: 5
            border.width: 1
            border.color:
                control.family === 1
                ? control.s.bezel
                : (control.physicallyDown ? "#fff7f7" : "#efe8df")
            gradient: Gradient {
                GradientStop {
                    objectName: "physicalButtonGradientStop0"
                    position: 0.00
                    color: control.family === 1
                        ? (control.physicallyDown ? "#c64545" : "#d95555")
                        : (control.physicallyDown ? "#fff3f3" : "#ffe3dc")
                }
                GradientStop {
                    objectName: "physicalButtonGradientStop1"
                    position: 0.22
                    color: control.family === 1
                        ? (control.physicallyDown ? "#c64545" : "#d95555")
                        : (control.physicallyDown ? "#ffb6b6" : "#ff9b91")
                }
                GradientStop {
                    objectName: "physicalButtonGradientStop2"
                    position: 0.62
                    color: control.family === 1
                        ? (control.physicallyDown ? "#c64545" : "#d95555")
                        : (control.physicallyDown ? "#ff6868" : "#f45d5d")
                }
                GradientStop {
                    objectName: "physicalButtonGradientStop3"
                    position: 1.00
                    color: control.family === 1
                        ? (control.physicallyDown ? "#c64545" : "#d95555")
                        : (control.physicallyDown ? "#bd2d2d" : "#cf3e3e")
                }
            }

            Rectangle {
                visible: control.family !== 1
                x: 5
                y: control.physicallyDown ? 3 : 2
                width: parent.width - 10
                height: 3
                radius: 2
                color: "#e2c6bf"
                opacity: control.physicallyDown ? 0.35 : 0.58
            }

            Behavior on y {
                NumberAnimation { duration: 65 }
            }
        }
    }

    contentItem: Item {}
}
