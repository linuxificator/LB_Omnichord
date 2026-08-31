import QtQuick
import QtQuick.Controls

Item {
    id: root

    property string label: ""
    property real currentValue: 0
    property real fromValue: 0
    property real toValue: 1
    property real stepValue: 0.01
    property int decimals: 2
    property var valueLabels: []

    property color textColor: "#4c3b08"
    property color trackColor: "#eee2a5"
    property color fillColor: "#c59518"
    property color handleColor: "#fffbea"
    property color borderColor: "#8a6810"
    property var midiControlRouter: null
    property var midiTarget: ({})
    property bool midiBindingGesture: false
    property bool midiManualTakeoverPending: false
    readonly property bool traceGestures:
        typeof sliderTrace !== "undefined" && sliderTrace

    readonly property bool midiBound: {
        if (root.midiControlRouter === null)
            return false
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.isControlTargetBound(root.midiTarget)
    }
    readonly property string midiVisualState: {
        if (root.midiControlRouter === null)
            return "idle"
        root.midiControlRouter.bindingVersion
        return root.midiControlRouter.controlTargetVisualState(root.midiTarget)
    }
    readonly property bool midiPresetFeedback:
        root.midiVisualState === "preset-displaced"
        || root.midiVisualState === "preset-incoming"

    signal edited(real value)
    signal activated()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        // A real learn/preset-feedback gesture owns this press. A normal
        // green bound state must still allow mouse/touch drag; onMoved then
        // performs the explicit manual-takeover contract.
        return learned || root.midiPresetFeedback
    }

    function releaseMidiBindingForManualEdit() {
        if (root.midiControlRouter !== null) {
            root.midiControlRouter.releaseControlTargetForManualEdit(
                root.midiTarget
            )
        }
    }

    function restoreCurrentValueBinding() {
        slider.value = Qt.binding(function() {
            return root.currentValue
        })
    }

    function beginSliderDrag() {
        // Break the backend-value binding while Qt owns an active slider drag.
        // The backend may echo the edit asynchronously; keeping the binding
        // alive during the drag can make the handle fight that older value.
        slider.value = Number(slider.value)
    }

    function traceSlider(event, value) {
        if (!root.traceGestures)
            return
        console.log(
            "SLIDER_TRACE",
            "labeled",
            String(root.label),
            event,
            "pressed",
            slider.pressed,
            "value",
            Number(slider.value),
            "current",
            Number(root.currentValue),
            "eventValue",
            Number(value)
        )
    }

    onCurrentValueChanged:
        root.traceSlider("currentValueChanged", root.currentValue)

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right

        text:
            root.label
            + " "
            + (
                root.valueLabels.length > Math.round(slider.value)
                ? String(root.valueLabels[Math.round(slider.value)])
                : Number(slider.value).toFixed(root.decimals)
            )

        color: root.textColor
        font.pixelSize: 13
        font.bold: true
        elide: Text.ElideRight

    }

    Slider {
        id: slider

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 30

        from: root.fromValue
        to: root.toValue
        stepSize: root.stepValue
        value: root.currentValue
        live: true
        snapMode: Slider.SnapAlways

        onPressedChanged: {
            root.traceSlider("pressedChanged", value)
            if (pressed) {
                root.beginSliderDrag()
                root.midiBindingGesture = root.beginMidiInteraction()
                root.midiManualTakeoverPending =
                    !root.midiBindingGesture && root.midiBound
                root.activated()
            } else {
                root.restoreCurrentValueBinding()
                root.midiBindingGesture = false
                root.midiManualTakeoverPending = false
            }
        }

        onMoved: {
            root.traceSlider("moved", value)
            if (root.midiBindingGesture) {
                root.restoreCurrentValueBinding()
                return
            }
            if (root.midiManualTakeoverPending) {
                // Deliberately release MIDI ownership before applying the
                // first value produced by this UI drag.
                root.releaseMidiBindingForManualEdit()
                root.midiManualTakeoverPending = false
            }
            root.edited(value)
        }

        background: Rectangle {
            x: slider.leftPadding
            y:
                slider.topPadding
                + slider.availableHeight / 2
                - height / 2
            width: slider.availableWidth
            height: 8
            radius: 4
            color: root.trackColor

            Rectangle {
                width:
                    slider.visualPosition
                    * parent.width
                height: parent.height
                radius: 4
                color: root.fillColor
            }
        }

        handle: Rectangle {
            x:
                slider.leftPadding
                + slider.visualPosition
                * (
                    slider.availableWidth
                    - width
                )
            y:
                slider.topPadding
                + slider.availableHeight / 2
                - height / 2
            implicitWidth: 19
            implicitHeight: 19
            width: implicitWidth
            height: implicitHeight
            radius: 10
            color: {
                if (root.midiVisualState === "preset-displaced")
                    return "#f22b2b"
                if (root.midiVisualState === "preset-incoming")
                    return "#3186d7"
                return root.midiBound ? "#35b85a" : root.handleColor
            }
            border.color: root.borderColor
            border.width: 2

            SequentialAnimation on opacity {
                running: root.midiPresetFeedback
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.2; duration: 110 }
                NumberAnimation { from: 0.2; to: 1.0; duration: 110 }
            }
        }
    }
}
