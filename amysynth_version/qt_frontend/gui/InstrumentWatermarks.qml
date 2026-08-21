import QtQuick

Item {
    id: root

    property string family: "percussion"
    property color ink: "#d6bb50"
    property real watermarkOpacity: 0.72

    Canvas {
        id: canvas

        anchors.fill: parent
        opacity: root.watermarkOpacity

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        function setup(ctx) {
            ctx.strokeStyle = root.ink
            ctx.fillStyle = root.ink
            ctx.lineWidth = 3.2
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
        }

        function line(ctx, x1, y1, x2, y2) {
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.stroke()
        }

        function circle(ctx, x, y, r) {
            ctx.beginPath()
            ctx.arc(x, y, r, 0, Math.PI * 2)
            ctx.stroke()
        }

        function drawDrum(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.ellipse(-23, -14, 46, 14)
            ctx.stroke()
            ctx.beginPath()
            ctx.ellipse(-23, 10, 46, 14)
            ctx.stroke()
            line(ctx, -23, -7, -23, 17)
            line(ctx, 23, -7, 23, 17)
            line(ctx, -19, -1, 18, 13)
            line(ctx, 19, -1, -18, 13)
            line(ctx, -8, -25, 12, -5)
            line(ctx, 8, -27, -10, -4)

            ctx.restore()
        }

        function drawTambourine(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            circle(ctx, 0, 0, 24)
            circle(ctx, 0, 0, 19)

            for (let i = 0; i < 8; ++i) {
                const a = i * Math.PI / 4
                circle(
                    ctx,
                    Math.cos(a) * 21.5,
                    Math.sin(a) * 21.5,
                    2.3
                )
            }

            ctx.restore()
        }

        function drawMaracas(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.ellipse(-22, -25, 18, 24)
            ctx.stroke()
            line(ctx, -15, -4, 2, 23)

            ctx.beginPath()
            ctx.ellipse(7, -20, 18, 24)
            ctx.stroke()
            line(ctx, 13, 2, 27, 28)

            ctx.restore()
        }

        function drawCymbal(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.moveTo(-29, -8)
            ctx.quadraticCurveTo(0, 7, 29, -8)
            ctx.quadraticCurveTo(0, -16, -29, -8)
            ctx.stroke()

            circle(ctx, 0, -8, 3)
            line(ctx, 0, -5, 0, 25)
            line(ctx, -13, 25, 13, 25)

            ctx.restore()
        }

        function drawDoubleBass(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.moveTo(0, -32)
            ctx.lineTo(0, -15)
            ctx.bezierCurveTo(-8, -13, -8, -4, -16, 1)
            ctx.bezierCurveTo(-28, 9, -21, 29, 0, 31)
            ctx.bezierCurveTo(21, 29, 28, 9, 16, 1)
            ctx.bezierCurveTo(8, -4, 8, -13, 0, -15)
            ctx.stroke()

            line(ctx, 0, -44, 0, -30)
            line(ctx, -5, -44, 5, -44)
            line(ctx, 0, 31, 0, 42)
            line(ctx, -3, -12, -3, 26)
            line(ctx, 3, -12, 3, 26)
            line(ctx, -7, 10, 7, 10)

            ctx.restore()
        }

        // The tuba watermark itself is rendered from tuba_watermark.png,
        // derived from the supplied upright-tuba reference image.

        function drawSousaphone(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            circle(ctx, -4, 5, 27)
            circle(ctx, -4, 5, 17)

            line(ctx, 14, -14, 26, -29)
            ctx.beginPath()
            ctx.moveTo(22, -28)
            ctx.quadraticCurveTo(39, -38, 42, -20)
            ctx.quadraticCurveTo(30, -18, 22, -28)
            ctx.stroke()

            line(ctx, -10, 22, 12, 2)
            line(ctx, 4, 20, 16, 8)

            ctx.restore()
        }

        function drawHarp(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.moveTo(-25, 31)
            ctx.lineTo(-14, -30)
            ctx.quadraticCurveTo(17, -18, 27, 31)
            ctx.closePath()
            ctx.stroke()

            line(ctx, -14, -30, 11, -16)

            for (let i = 0; i < 6; ++i) {
                const sx = -10 + i * 5
                line(ctx, sx, -23 + i * 2, sx + 6, 25)
            }

            ctx.restore()
        }

        function drawLyre(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.moveTo(-22, -25)
            ctx.quadraticCurveTo(-28, 8, -12, 27)
            ctx.quadraticCurveTo(0, 36, 12, 27)
            ctx.quadraticCurveTo(28, 8, 22, -25)
            ctx.stroke()

            line(ctx, -21, -16, 21, -16)
            line(ctx, -10, -14, -7, 25)
            line(ctx, -3, -14, -2, 29)
            line(ctx, 4, -14, 3, 29)
            line(ctx, 11, -14, 8, 25)

            ctx.restore()
        }

        function drawAccordion(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.strokeRect(-31, -22, 18, 44)
            ctx.strokeRect(13, -22, 18, 44)

            ctx.beginPath()
            ctx.moveTo(-13, -20)
            for (let i = 0; i < 7; ++i) {
                const xx = -11 + i * 4
                ctx.lineTo(xx, i % 2 === 0 ? 18 : -18)
            }
            ctx.lineTo(13, 20)
            ctx.stroke()

            for (let i = 0; i < 4; ++i) {
                circle(ctx, -22, -12 + i * 8, 1.5)
                line(ctx, 19, -14 + i * 8, 28, -14 + i * 8)
            }

            ctx.restore()
        }

        function drawMandolin(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            ctx.beginPath()
            ctx.moveTo(-8, 15)
            ctx.bezierCurveTo(-29, 7, -27, -22, -8, -30)
            ctx.bezierCurveTo(8, -34, 23, -18, 17, 0)
            ctx.bezierCurveTo(12, 14, 2, 20, -8, 15)
            ctx.stroke()

            circle(ctx, -3, -7, 5)
            line(ctx, 10, -22, 30, -40)
            line(ctx, 27, -42, 35, -36)
            line(ctx, -6, -25, 26, -39)
            line(ctx, -3, -24, 29, -36)

            ctx.restore()
        }

        function drawOmnichord(ctx, x, y, s) {
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(s, s)

            // Classic Suzuki Omnichord / OM-84 silhouette:
            // a long low chord-key wing on the left flowing into the
            // characteristic large rounded strum/speaker body on the right.
            ctx.beginPath()
            ctx.moveTo(-55, 14)
            ctx.quadraticCurveTo(-58, -4, -44, -14)
            ctx.lineTo(1, -36)
            ctx.quadraticCurveTo(31, -46, 49, -25)
            ctx.quadraticCurveTo(63, -7, 59, 15)
            ctx.quadraticCurveTo(55, 39, 30, 43)
            ctx.quadraticCurveTo(12, 45, -2, 32)
            ctx.lineTo(-46, 27)
            ctx.quadraticCurveTo(-55, 25, -55, 14)
            ctx.closePath()
            ctx.stroke()

            // Chord-key wing.
            ctx.beginPath()
            ctx.moveTo(-52, 5)
            ctx.lineTo(-10, 0)
            ctx.lineTo(-1, 24)
            ctx.lineTo(-48, 21)
            ctx.closePath()
            ctx.stroke()

            for (let row = 0; row < 3; ++row) {
                for (let col = 0; col < 8; ++col) {
                    const xx = -47 + col * 5.2
                    const yy = 6 + row * 5.1
                    ctx.strokeRect(xx, yy, 3.4, 3.2)
                }
            }

            // Sloping control panel across the upper middle.
            ctx.beginPath()
            ctx.moveTo(-35, -10)
            ctx.lineTo(9, -29)
            ctx.lineTo(23, -14)
            ctx.lineTo(-9, -2)
            ctx.closePath()
            ctx.stroke()

            circle(ctx, -25, -10, 4)
            circle(ctx, -10, -16, 3)
            circle(ctx, 4, -21, 4)

            // Distinctive slanted touch/strum plate.
            ctx.beginPath()
            ctx.moveTo(13, -11)
            ctx.lineTo(28, -17)
            ctx.lineTo(20, 20)
            ctx.lineTo(7, 19)
            ctx.closePath()
            ctx.stroke()

            for (let i = 0; i < 7; ++i) {
                line(
                    ctx,
                    11 + i * 1.9,
                    -8 - i * 0.7,
                    10 + i * 1.7,
                    16
                )
            }

            // Rounded speaker field on the large right-hand body.
            ctx.beginPath()
            ctx.arc(39, 7, 15, -1.15, 1.2)
            ctx.stroke()

            for (let i = 0; i < 6; ++i) {
                line(
                    ctx,
                    33,
                    -5 + i * 4,
                    51,
                    -1 + i * 3.2
                )
            }

            ctx.restore()
        }

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            setup(ctx)

            const y = height / 2

            if (root.family === "percussion") {
                drawDrum(ctx, width * 0.18, y, 0.85)
                drawTambourine(ctx, width * 0.43, y, 0.88)
                drawMaracas(ctx, width * 0.68, y, 0.78)
                drawCymbal(ctx, width * 0.88, y, 0.85)
            } else if (root.family === "bass") {
                drawDoubleBass(ctx, width * 0.54, y, 1.00)
                drawSousaphone(ctx, width * 0.82, y, 0.94)
            } else if (root.family === "strum") {
                drawHarp(ctx, width * 0.28, y, 0.95)
                drawLyre(ctx, width * 0.58, y, 0.95)
                drawHarp(ctx, width * 0.84, y, 0.72)
            } else if (root.family === "chord") {
                drawAccordion(ctx, width * 0.22, y, 0.92)
                drawMandolin(ctx, width * 0.52, y, 0.90)
                drawOmnichord(ctx, width * 0.82, y, 1.02)
            }
        }
    }

    Image {
        visible:
            root.family === "bass"

        source: "data:image/png;base64,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"
        asynchronous: false
        smooth: true
        fillMode: Image.PreserveAspectFit

        x:
            root.width * 0.20
            - width / 2
        y: 4
        width: 92
        height: root.height - 8

        opacity: 0.94
    }
}
