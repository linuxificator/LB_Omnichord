import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var controller
    required property var midiControlRouter
    property string controlScreen: "omni"
    readonly property real controlSliderWidth:
        Math.max(
            0,
            (
                controlsRow.width
                - drumButton.width
                - 3 * controlsRow.spacing
            ) / 3
        )

    Rectangle {
        anchors.fill: parent
        radius: 11
        color: "#f7dce6"
        border.color: "#c98da5"
        border.width: 1
    }

    Row {
        id: controlsRow
        anchors.fill: parent
        anchors.margins: 4
        spacing: 6

        LabeledSlider {
            width: root.controlSliderWidth
            height: parent.height
            label: "LEV"
            currentValue: root.controller.reverbLevel
            fromValue: 0
            toValue: 3
            stepValue: 0.01
            decimals: 2
            textColor: "#6b3048"
            trackColor: "#e8b7ca"
            fillColor: "#d87fa5"
            handleColor: "#fff7fb"
            borderColor: "#a75f7d"
            midiControlRouter: root.midiControlRouter
            midiTarget: ({
                "screen": root.controlScreen,
                "kind": "reverb_level"
            })
            onEdited: (value) => root.controller.setReverbLevel(value)
        }

        LabeledSlider {
            width: root.controlSliderWidth
            height: parent.height
            label: "LIVE"
            currentValue: root.controller.reverbLiveness
            fromValue: 0
            toValue: 1
            stepValue: 0.01
            decimals: 2
            textColor: "#6b3048"
            trackColor: "#e8b7ca"
            fillColor: "#d87fa5"
            handleColor: "#fff7fb"
            borderColor: "#a75f7d"
            midiControlRouter: root.midiControlRouter
            midiTarget: ({
                "screen": root.controlScreen,
                "kind": "reverb_liveness"
            })
            onEdited: (value) => root.controller.setReverbLiveness(value)
        }

        LabeledSlider {
            width: root.controlSliderWidth
            height: parent.height
            label: "DAMP"
            currentValue: root.controller.reverbDamping
            fromValue: 0
            toValue: 1
            stepValue: 0.01
            decimals: 2
            textColor: "#6b3048"
            trackColor: "#e8b7ca"
            fillColor: "#d87fa5"
            handleColor: "#fff7fb"
            borderColor: "#a75f7d"
            midiControlRouter: root.midiControlRouter
            midiTarget: ({
                "screen": root.controlScreen,
                "kind": "reverb_damping"
            })
            onEdited: (value) => root.controller.setReverbDamping(value)
        }

        Button {
            id: drumButton
            width: 50
            height: Math.min(50, parent.height)
            anchors.verticalCenter: parent.verticalCenter
            text: "DRM"
            font.pixelSize: 12
            font.bold: true

            contentItem: Text {
                text: drumButton.text
                color: root.controller.reverbDrumsIncluded ? "#ffffff" : "#6b3048"
                font: drumButton.font
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: width / 2
                color: root.controller.reverbDrumsIncluded
                       ? "#b64f7a"
                       : (drumButton.pressed ? "#d48aa8" : "#efbfd1")
                border.color: root.controller.reverbDrumsIncluded ? "#7e294d" : "#b96e8d"
                border.width: root.controller.reverbDrumsIncluded ? 3 : 2
            }

            onClicked: root.controller.toggleReverbDrums()
        }
    }
}
