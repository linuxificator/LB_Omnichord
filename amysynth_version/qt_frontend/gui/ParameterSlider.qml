import QtQuick

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
    readonly property bool midiBound: numeric.midiBound
    readonly property string midiVisualState: numeric.midiVisualState

    signal edited(string key, real value)
    signal activated()

    function isLogScale() {
        return String(root.control.scale || "linear") === "log"
    }

    function controlToSlider(value) {
        const numericValue = Number(value)
        if (!isLogScale())
            return numericValue
        const minimum = Math.max(Number(root.control.minimum), 1e-12)
        return Math.log(Math.max(numericValue, minimum))
    }

    function sliderToControl(value) {
        return isLogScale() ? Math.exp(Number(value)) : Number(value)
    }

    function midiNoteName(value) {
        const rounded = Math.round(Number(value))
        const names = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]
        const note = ((rounded % 12) + 12) % 12
        const octave = Math.floor(rounded / 12) - 1
        return names[note] + octave
    }

    function formattedValue(value) {
        const unit = String(root.control.unit || "")
        if (unit === "note")
            return midiNoteName(value)
        const text = Number(value).toFixed(Number(root.control.decimals))
        return unit.length > 0 ? text + " " + unit : text
    }

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right
        text:
            root.control.label
            + " "
            + root.formattedValue(root.sliderToControl(numeric.displayValue))
        color: root.textColor
        font.pixelSize: 13
        font.bold: true
        elide: Text.ElideRight
    }

    BindableSlider {
        id: numeric
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 28
        currentValue: root.controlToSlider(root.control.value)
        fromValue:
            root.isLogScale()
            ? Math.log(Math.max(Number(root.control.minimum), 1e-12))
            : Number(root.control.minimum)
        toValue:
            root.isLogScale()
            ? Math.log(Math.max(Number(root.control.maximum), 1e-12))
            : Number(root.control.maximum)
        stepValue: root.isLogScale() ? 0 : Number(root.control.step)
        controlHeight: 28
        handleDiameter: 18
        trackColor: root.trackColor
        fillColor: root.fillColor
        handleColor: root.handleColor
        borderColor: root.borderColor
        midiControlRouter: root.midiControlRouter
        midiTarget: root.midiTarget
        accessibleName: String(root.control.label)
        traceKind: "parameter"
        traceLabel: String(root.control.key)
        onActivated: root.activated()
        onEdited: (value) => root.edited(root.control.key, root.sliderToControl(value))
    }
}
