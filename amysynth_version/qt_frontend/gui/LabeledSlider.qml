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

    signal edited(real value)
    signal activated()

    function beginMidiInteraction() {
        if (root.midiControlRouter === null)
            return false
        const learned = root.midiControlRouter.activateControlTarget(
            root.midiTarget
        )
        // A real learn/preset-feedback gesture owns this press.  A normal
        // green bound state must still allow mouse drag; onMoved then performs
        // manual takeover through controlTargetMoved().
        return learned || root.midiPresetFeedback
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

    function applySliderValue(value) {
        if (root.midiBindingGesture) {
            root.restoreCurrentValueBinding()
            return
        }
        if (root.midiControlRouter !== null) {
            root.midiControlRouter.controlTargetMoved(root.midiTarget)
        }
        root.edited(value)
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
        height: 30

        from: root.fromValue
        to: root.toValue
        stepSize: root.stepValue
        value: root.currentValue
        live: true
        snapMode: Slider.SnapAlways

        onPressedChanged: {
            if (pressed) {
                root.beginSliderDrag()
                root.midiBindingGesture = root.beginMidiInteraction()
                root.activated()
            } else {
                root.restoreCurrentValueBinding()
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
                width: 19
                height: 19
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
                    root.restoreCurrentValueBinding()
                    root.sliderDragActive = false
                    root.midiBindingGesture = false
                }

                onCanceled: {
                    root.restoreCurrentValueBinding()
                    root.sliderDragActive = false
                    root.midiBindingGesture = false
                }
            }
        }
    }
}
