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
    readonly property bool midiBound: numeric.midiBound
    readonly property string midiVisualState: numeric.midiVisualState

    signal edited(real value)
    signal activated()

    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.right: parent.right
        text:
            root.label
            + " "
            + (
                root.valueLabels.length > Math.round(numeric.displayValue)
                ? String(root.valueLabels[Math.round(numeric.displayValue)])
                : Number(numeric.displayValue).toFixed(root.decimals)
            )
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
        height: 30
        currentValue: root.currentValue
        fromValue: root.fromValue
        toValue: root.toValue
        stepValue: root.stepValue
        snapMode: Slider.SnapAlways
        controlHeight: 30
        handleDiameter: 19
        trackColor: root.trackColor
        fillColor: root.fillColor
        handleColor: root.handleColor
        borderColor: root.borderColor
        midiControlRouter: root.midiControlRouter
        midiTarget: root.midiTarget
        accessibleName: root.label
        traceKind: "labeled"
        traceLabel: String(root.label)
        onActivated: root.activated()
        onEdited: (value) => root.edited(value)
    }
}
