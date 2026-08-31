import QtQuick
import QtQuick.Controls

Item {
    id: root

    required property var control

    property color textColor: "#102417"
    property color trackColor: "#c5d8c9"
    property color fillColor: "#426f4c"
    property color handleColor: "#f4fff5"
    property color borderColor: "#315b39"
    property var midiControlRouter: null
    property var midiTarget: ({})
    property bool midiBindingGesture: false
    property bool sliderDragActive: false

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

    signal edited(string key, real value)
    signal activated()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        return learned || root.midiPresetFeedback
    }

    function moveMidiInteraction() {
        if (root.midiControlRouter !== null)
            root.midiControlRouter.controlTargetMoved(root.midiTarget)
    }

    function isLogScale() {
        return String(root.control.scale || "linear") === "log"
    }

    function controlToSlider(value) {
        var numeric = Number(value)
        if (!isLogScale())
            return numeric
        var minimum = Math.max(Number(root.control.minimum), 1e-12)
        return Math.log(Math.max(numeric, minimum))
    }

    function sliderToControl(value) {
        return isLogScale() ? Math.exp(Number(value)) : Number(value)
    }

    function midiNoteName(value) {
        var rounded = Math.round(Number(value))
        var names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
        var note = ((rounded % 12) + 12) % 12
        var octave = Math.floor(rounded / 12) - 1
        return names[note] + octave
    }

    function formattedValue(value) {
        var unit = String(root.control.unit || "")
        if (unit === "note")
            return midiNoteName(value)
        var text = Number(value).toFixed(Number(root.control.decimals))
        return unit.length > 0 ? text + " " + unit : text
    }

    function syncSliderValue() {
        slider.value = controlToSlider(root.control.value)
    }

    function beginSliderDrag() {
        // Keep Qt's active slider drag independent from backend model refreshes.
        // Repeater modelData can be replaced while a Python setter is still
        // converging; during that press Qt must continue to own the handle.
        slider.value = Number(slider.value)
    }

    function applySliderValue(value) {
        if (root.midiBindingGesture) {
            root.syncSliderValue()
            return
        }
        root.moveMidiInteraction()
        root.edited(
            root.control.key,
            root.sliderToControl(value)
        )
    }

    function dragValueFromHandle(mouseX, mouseY) {
        const local = sliderHandle.mapToItem(
            slider,
            Number(mouseX),
            Number(mouseY)
        )
        const span = Math.max(1e-9, slider.availableWidth - sliderHandle.width)
        const position = Math.max(
            0.0,
            Math.min(
                1.0,
                (local.x - slider.leftPadding - sliderHandle.width / 2) / span
            )
        )
        return slider.valueAt(position)
    }

    onControlChanged: {
        if (!slider.pressed && !root.sliderDragActive)
            syncSliderValue()
    }

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right

        text:
            root.control.label
            + " "
            + root.formattedValue(
                root.sliderToControl(slider.value)
            )

        color: root.textColor
        font.pixelSize: 13
        font.bold: true
        elide: Text.ElideRight

        TapHandler {
            gesturePolicy: TapHandler.DragThreshold
            onDoubleTapped: {
                if (root.midiControlRouter !== null) {
                    root.midiControlRouter.controlTargetDoubleTapped(
                        root.midiTarget
                    )
                }
            }
        }
    }

    Slider {
        id: slider

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 28

        from:
            root.isLogScale()
            ? Math.log(Math.max(Number(root.control.minimum), 1e-12))
            : Number(root.control.minimum)
        to:
            root.isLogScale()
            ? Math.log(Math.max(Number(root.control.maximum), 1e-12))
            : Number(root.control.maximum)
        stepSize:
            root.isLogScale()
            ? 0
            : Number(root.control.step)
        live: true

        Component.onCompleted:
            root.syncSliderValue()

        onPressedChanged: {
            if (pressed) {
                root.beginSliderDrag()
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.syncSliderValue()
                root.midiBindingGesture = false
            }
        }

        onMoved: {
            root.applySliderValue(value)
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

        handle: Item {
            id: sliderHandle
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
            implicitWidth: 34
            implicitHeight: 34
            width: implicitWidth
            height: implicitHeight

            Rectangle {
                id: sliderKnob
                anchors.centerIn: parent
                width: 18
                height: 18
                radius: 9
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

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                preventStealing: true

                function updateSlider(mouse) {
                    slider.value = root.dragValueFromHandle(mouse.x, mouse.y)
                    root.applySliderValue(slider.value)
                }

                onPressed: function(mouse) {
                    root.sliderDragActive = true
                    root.beginSliderDrag()
                    root.midiBindingGesture = root.beginMidiInteraction()
                    root.activated()
                    updateSlider(mouse)
                }

                onPositionChanged: function(mouse) {
                    if (pressed)
                        updateSlider(mouse)
                }

                onReleased: {
                    root.sliderDragActive = false
                    root.syncSliderValue()
                    root.midiBindingGesture = false
                }

                onCanceled: {
                    root.sliderDragActive = false
                    root.syncSliderValue()
                    root.midiBindingGesture = false
                }
            }
        }
    }
}
