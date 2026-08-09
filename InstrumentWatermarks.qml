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

        source: "tuba_watermark.png"
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
