import QtQuick

Item {
    id: root

    property string family: "percussion"
    property color ink: "#d6bb50"
    property real watermarkOpacity: 0.72

    Canvas {
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
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
        }

        function circle(ctx, x, y, r) {
            ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke()
        }

        function ellipse(ctx, x, y, rx, ry) {
            ctx.beginPath(); ctx.ellipse(x - rx, y - ry, rx * 2, ry * 2); ctx.stroke()
        }

        function drawDrum(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ellipse(ctx, 0, -8, 24, 8); ellipse(ctx, 0, 13, 24, 8)
            line(ctx, -24, -8, -24, 13); line(ctx, 24, -8, 24, 13)
            line(ctx, -20, -1, 19, 13); line(ctx, 20, -1, -19, 13)
            line(ctx, -9, -27, 10, -7); line(ctx, 9, -27, -10, -7)
            ctx.restore()
        }

        function drawTambourine(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            circle(ctx, 0, 0, 24); circle(ctx, 0, 0, 19)
            for (let i = 0; i < 8; ++i) {
                const a = i * Math.PI / 4
                circle(ctx, Math.cos(a) * 21.5, Math.sin(a) * 21.5, 2.3)
            }
            ctx.restore()
        }

        function drawMaracas(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ellipse(ctx, -15, -14, 10, 14); line(ctx, -10, -2, 4, 25)
            ellipse(ctx, 12, -12, 10, 14); line(ctx, 16, 0, 29, 26)
            ctx.restore()
        }

        function drawCymbal(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-29, -8); ctx.quadraticCurveTo(0, 7, 29, -8); ctx.quadraticCurveTo(0, -16, -29, -8); ctx.stroke()
            circle(ctx, 0, -8, 3); line(ctx, 0, -5, 0, 25); line(ctx, -13, 25, 13, 25)
            ctx.restore()
        }

        function drawDoubleBass(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(0, -32); ctx.lineTo(0, -15)
            ctx.bezierCurveTo(-8, -13, -8, -4, -16, 1); ctx.bezierCurveTo(-28, 9, -21, 29, 0, 31)
            ctx.bezierCurveTo(21, 29, 28, 9, 16, 1); ctx.bezierCurveTo(8, -4, 8, -13, 0, -15); ctx.stroke()
            line(ctx, 0, -44, 0, -30); line(ctx, -5, -44, 5, -44); line(ctx, 0, 31, 0, 42)
            line(ctx, -3, -12, -3, 26); line(ctx, 3, -12, 3, 26); line(ctx, -7, 10, 7, 10)
            ctx.restore()
        }

        // Upright tuba is drawn directly into the bass background.  This
        // replaces the former external tuba_watermark.png runtime asset.
        function drawTuba(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-3, 30); ctx.bezierCurveTo(-22, 25, -25, 7, -16, -5)
            ctx.bezierCurveTo(-8, -15, 6, -13, 9, -2); ctx.bezierCurveTo(12, 10, 4, 18, -5, 17); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(-14, -6); ctx.bezierCurveTo(-17, -24, -4, -37, 16, -35)
            ctx.lineTo(25, -35); ctx.quadraticCurveTo(37, -34, 41, -25); ctx.quadraticCurveTo(30, -20, 18, -22)
            ctx.lineTo(8, -22); ctx.stroke()
            line(ctx, -4, 17, -4, 31); line(ctx, 2, 16, 2, 31); line(ctx, -9, 31, 8, 31)
            line(ctx, 7, -20, 14, 2); line(ctx, 13, -19, 20, 0)
            circle(ctx, 11, 4, 3); circle(ctx, 17, 4, 3); circle(ctx, 23, 4, 3)
            line(ctx, 11, 7, 11, 14); line(ctx, 17, 7, 17, 14); line(ctx, 23, 7, 23, 14)
            ctx.restore()
        }

        function drawSousaphone(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            circle(ctx, -4, 5, 27); circle(ctx, -4, 5, 17); line(ctx, 14, -14, 26, -29)
            ctx.beginPath(); ctx.moveTo(22, -28); ctx.quadraticCurveTo(39, -38, 42, -20); ctx.quadraticCurveTo(30, -18, 22, -28); ctx.stroke()
            line(ctx, -10, 22, 12, 2); line(ctx, 4, 20, 16, 8); ctx.restore()
        }

        function drawHarp(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-25, 31); ctx.lineTo(-14, -30); ctx.quadraticCurveTo(17, -18, 27, 31); ctx.closePath(); ctx.stroke()
            line(ctx, -14, -30, 11, -16)
            for (let i = 0; i < 6; ++i) { const sx = -10 + i * 5; line(ctx, sx, -23 + i * 2, sx + 6, 25) }
            ctx.restore()
        }

        function drawLyre(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-22, -25); ctx.quadraticCurveTo(-28, 8, -12, 27); ctx.quadraticCurveTo(0, 36, 12, 27); ctx.quadraticCurveTo(28, 8, 22, -25); ctx.stroke()
            line(ctx, -21, -16, 21, -16)
            for (let i = -2; i <= 2; ++i) line(ctx, i * 6, -14, i * 4, 25)
            ctx.restore()
        }

        function drawAccordion(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.strokeRect(-31, -22, 18, 44); ctx.strokeRect(13, -22, 18, 44)
            ctx.beginPath(); ctx.moveTo(-13, -20)
            for (let i = 0; i < 7; ++i) { const xx = -11 + i * 4; ctx.lineTo(xx, i % 2 === 0 ? 18 : -18) }
            ctx.lineTo(13, 20); ctx.stroke(); ctx.restore()
        }

        function drawMandolin(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-8, 15); ctx.bezierCurveTo(-29, 7, -27, -22, -8, -30); ctx.bezierCurveTo(8, -34, 23, -18, 17, 0); ctx.bezierCurveTo(12, 14, 2, 20, -8, 15); ctx.stroke()
            circle(ctx, -3, -7, 5); line(ctx, 10, -22, 30, -40); line(ctx, 27, -42, 35, -36); ctx.restore()
        }

        function drawOmnichord(ctx, x, y, s) {
            ctx.save(); ctx.translate(x, y); ctx.scale(s, s)
            ctx.beginPath(); ctx.moveTo(-55, 14); ctx.quadraticCurveTo(-58, -4, -44, -14); ctx.lineTo(1, -36)
            ctx.quadraticCurveTo(31, -46, 49, -25); ctx.quadraticCurveTo(63, -7, 59, 15); ctx.quadraticCurveTo(55, 39, 30, 43)
            ctx.quadraticCurveTo(12, 45, -2, 32); ctx.lineTo(-46, 27); ctx.quadraticCurveTo(-55, 25, -55, 14); ctx.closePath(); ctx.stroke()
            ctx.strokeRect(-47, 3, 38, 19); ctx.beginPath(); ctx.moveTo(13, -11); ctx.lineTo(28, -17); ctx.lineTo(20, 20); ctx.lineTo(7, 19); ctx.closePath(); ctx.stroke()
            ctx.restore()
        }

        onPaint: {
            const ctx = getContext("2d"); ctx.reset(); setup(ctx); const y = height / 2
            if (root.family === "percussion") {
                drawDrum(ctx, width * 0.18, y, 0.85); drawTambourine(ctx, width * 0.43, y, 0.88)
                drawMaracas(ctx, width * 0.68, y, 0.78); drawCymbal(ctx, width * 0.88, y, 0.85)
            } else if (root.family === "bass") {
                drawTuba(ctx, width * 0.20, y, 0.92); drawDoubleBass(ctx, width * 0.54, y, 1.00); drawSousaphone(ctx, width * 0.82, y, 0.94)
            } else if (root.family === "strum") {
                drawHarp(ctx, width * 0.28, y, 0.95); drawLyre(ctx, width * 0.58, y, 0.95); drawHarp(ctx, width * 0.84, y, 0.72)
            } else if (root.family === "chord") {
                drawAccordion(ctx, width * 0.22, y, 0.92); drawMandolin(ctx, width * 0.52, y, 0.90); drawOmnichord(ctx, width * 0.82, y, 1.02)
            }
        }
    }
}
