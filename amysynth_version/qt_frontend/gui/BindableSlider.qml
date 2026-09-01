import QtQuick
import QtQuick.Controls

Item {
    id: root

    property real currentValue: 0
    property real fromValue: 0
    property real toValue: 1
    property real stepValue: 0
    property int snapMode: Slider.NoSnap
    property int controlHeight: 30
    property int handleDiameter: 19
    property color trackColor: "#eee2a5"
    property color fillColor: "#c59518"
    property color handleColor: "#fffbea"
    property color borderColor: "#8a6810"
    property var midiControlRouter: null
    property var midiTarget: ({})
    property string accessibleName: ""
    property string traceKind: "numeric"
    property string traceLabel: ""

    property bool midiBindingGesture: false
    property bool midiManualTakeoverPending: false
    readonly property bool traceGestures:
        typeof sliderTrace !== "undefined" && sliderTrace
    readonly property real displayValue: slider.value
    readonly property real visualPosition: slider.visualPosition
    readonly property bool pressed: slider.pressed
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
        const learned = root.midiControlRouter.activateControlTarget(root.midiTarget)
        return learned || root.midiPresetFeedback
    }

    function releaseMidiBindingForManualEdit() {
        if (root.midiControlRouter !== null) {
            root.midiControlRouter.releaseControlTargetForManualEdit(root.midiTarget)
        }
    }

    function beginSliderDrag() {
        // Qt owns the value for the complete native drag, even when an older
        // backend value is echoed or a wrapper's model object is replaced.
        slider.value = Number(slider.value)
    }

    function synchronizeFromBackend() {
        slider.value = Qt.binding(function() { return root.currentValue })
    }

    function traceSlider(event, value) {
        if (!root.traceGestures)
            return
        console.log(
            "SLIDER_TRACE",
            root.traceKind,
            root.traceLabel,
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

    onCurrentValueChanged: {
        root.traceSlider("currentValueChanged", root.currentValue)
        if (!slider.pressed)
            root.synchronizeFromBackend()
    }

    Slider {
        id: slider
        objectName: "nativeSlider"

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.controlHeight
        from: root.fromValue
        to: root.toValue
        stepSize: root.stepValue
        value: root.currentValue
        live: true
        snapMode: root.snapMode
        Accessible.name: root.accessibleName

        onPressedChanged: {
            root.traceSlider("pressedChanged", value)
            if (pressed) {
                root.beginSliderDrag()
                root.midiBindingGesture = root.beginMidiInteraction()
                root.midiManualTakeoverPending =
                    !root.midiBindingGesture && root.midiBound
                root.activated()
            } else {
                root.synchronizeFromBackend()
                root.midiBindingGesture = false
                root.midiManualTakeoverPending = false
            }
        }

        onMoved: {
            root.traceSlider("moved", value)
            if (root.midiBindingGesture) {
                root.synchronizeFromBackend()
                return
            }
            if (root.midiManualTakeoverPending) {
                root.releaseMidiBindingForManualEdit()
                root.midiManualTakeoverPending = false
            }
            root.edited(value)
        }

        background: Rectangle {
            objectName: "sliderTrack"
            x: slider.leftPadding
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: slider.availableWidth
            height: 8
            radius: 4
            color: root.trackColor

            Rectangle {
                objectName: "sliderFill"
                width: slider.visualPosition * parent.width
                height: parent.height
                radius: 4
                color: root.fillColor
            }
        }

        handle: Rectangle {
            objectName: "sliderHandle"
            x:
                slider.leftPadding
                + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            implicitWidth: root.handleDiameter
            implicitHeight: root.handleDiameter
            width: implicitWidth
            height: implicitHeight
            radius: width / 2
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
