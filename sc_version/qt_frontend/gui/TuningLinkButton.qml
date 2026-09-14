import QtQuick
import QtQuick.Controls

Button {
    id: root

    property bool coupled: true

    contentItem: Canvas {
        id: forkCanvas
        anchors.fill: parent

        Connections {
            target: root
            function onCoupledChanged() {
                forkCanvas.requestPaint()
            }
        }

        function drawHalf(c, side, offset) {
            const cx = width / 2 + offset
            const top = height * 0.20
            const shoulder = height * 0.48
            const bottom = height * 0.78
            const spread = 10

            c.beginPath()
            c.moveTo(cx + side * spread, top)
            c.lineTo(cx + side * spread, height * 0.38)
            c.quadraticCurveTo(
                cx + side * spread,
                shoulder,
                cx,
                shoulder
            )
            c.lineTo(cx, bottom)
            c.stroke()
        }

        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.strokeStyle = "#8c4a08"
            c.lineWidth = 4
            c.lineCap = "round"

            if (root.coupled) {
                drawHalf(c, -1, 0)
                drawHalf(c, 1, 0)

                c.beginPath()
                c.moveTo(width / 2 - 9, height * 0.78)
                c.lineTo(width / 2 + 9, height * 0.78)
                c.stroke()
            } else {
                drawHalf(c, -1, -8)
                drawHalf(c, 1, 8)
            }
        }
    }

    background: Rectangle {
        radius: 9
        color:
            root.pressed
            ? "#df9138"
            : (
                root.coupled
                ? "#efb05c"
                : "#f5d09a"
            )
        border.color: root.coupled ? "#a75d0a" : "#c38a43"
        border.width: root.coupled ? 2 : 1
    }
}
