"""The grandfather (long-case) clock: mahogany case, painted dial with a
moon-phase arch and seconds dial, and a pendulum you can see swinging
through the trunk door.

The case and dial face don't change from second to second, so they're
painted into the inside scene's cached layer (paint_case). The hands,
pendulum and weights are painted every frame on top (paint_moving).
"""
from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen

from simple_cabin.gui.paint import alpha, hgrad, poly, radial, rgb, scaled, vgrad

CX = 320.0  # the clock's centre line
DIAL = QPointF(CX, 322)  # centre of the hour dial
DIAL_R = 90.0
ARCH = QPointF(CX, 224)  # centre of the moon arch
ARCH_R = 98.0
SECONDS = QPointF(CX, 286)
PIVOT = QPointF(CX, 430)  # where the pendulum hangs from
ROD = 236.0
SWING_DEGREES = 7.5
TRUNK_WINDOW = QRectF(252, 478, 136, 236)

MAHOGANY = rgb(122, 52, 30)
MAHOGANY_LIGHT = rgb(164, 80, 44)
MAHOGANY_DARK = rgb(70, 28, 18)
BRASS = rgb(214, 168, 72)
BRASS_DARK = rgb(140, 100, 36)
DIAL_FACE = rgb(240, 230, 204)
INK = rgb(28, 24, 26)

ROMAN = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


def _wood(p: QPainter, rect: QRectF, light: float = 1.0) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(hgrad(rect.left(), rect.right(), (0, scaled(MAHOGANY_DARK, light)), (0.25, scaled(MAHOGANY_LIGHT, light)),
                     (0.55, scaled(MAHOGANY, light)), (1, scaled(MAHOGANY_DARK, light))))
    p.drawRect(rect)
    # a little figure in the grain
    p.setPen(QPen(alpha(MAHOGANY_DARK, 70), 1))
    step = 9
    x = rect.left() + 4
    while x < rect.right() - 2:
        path = QPainterPath()
        path.moveTo(x, rect.top())
        y = rect.top()
        while y < rect.bottom():
            y2 = min(rect.bottom(), y + 30)
            path.quadTo(x + math.sin(y * 0.05 + x) * 3, (y + y2) / 2, x, y2)
            y = y2
        p.drawPath(path)
        x += step
    p.setPen(Qt.NoPen)


def _moulding(p: QPainter, x0: float, x1: float, y: float, h: float) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(vgrad(y, y + h, MAHOGANY_LIGHT, MAHOGANY, MAHOGANY_DARK))
    p.drawRect(QRectF(x0, y, x1 - x0, h))
    p.setBrush(alpha(BRASS, 140))
    p.drawRect(QRectF(x0, y + h * 0.35, x1 - x0, 1.5))


def paint_case(p: QPainter, moon_phase: float) -> None:
    p.setRenderHint(QPainter.Antialiasing)
    # Shadow on the wall behind
    p.setPen(Qt.NoPen)
    p.setBrush(rgb(0, 0, 0, 60))
    p.drawRoundedRect(QRectF(196, 40, 270, 840), 30, 30)

    # Plinth and bracket feet
    p.setBrush(MAHOGANY_DARK)
    p.drawPolygon(poly((186, 864), (190, 846), (450, 846), (454, 864), (430, 864), (424, 856), (216, 856), (210, 864)))
    _moulding(p, 184, 456, 830, 18)
    # Base box with a burr-walnut panel
    _wood(p, QRectF(198, 720, 244, 112))
    p.setBrush(vgrad(735, 815, rgb(150, 92, 52), rgb(120, 70, 40)))
    p.drawRoundedRect(QRectF(222, 736, 196, 80), 10, 10)
    p.setPen(QPen(alpha(BRASS, 150), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(226, 740, 188, 72), 8, 8)
    p.setPen(Qt.NoPen)
    _moulding(p, 192, 448, 708, 16)

    # Trunk, with its glazed door
    _wood(p, QRectF(214, 452, 212, 258))
    p.setBrush(MAHOGANY_DARK)
    p.drawRoundedRect(TRUNK_WINDOW.adjusted(-9, -9, 9, 9), 8, 8)
    # inside of the case, seen through the glass
    p.setBrush(vgrad(TRUNK_WINDOW.top(), TRUNK_WINDOW.bottom(), rgb(40, 18, 12), rgb(58, 26, 16), rgb(30, 14, 10)))
    p.drawRoundedRect(TRUNK_WINDOW, 4, 4)
    _moulding(p, 200, 440, 432, 22)

    # Hood
    _wood(p, QRectF(196, 112, 248, 322))
    # Columns either side of the dial
    for x in (198, 426):
        p.setBrush(hgrad(x, x + 16, MAHOGANY_DARK, MAHOGANY_LIGHT, MAHOGANY_DARK))
        p.drawRect(QRectF(x, 128, 16, 296))
        p.setBrush(BRASS)
        p.drawRect(QRectF(x - 2, 124, 20, 7))
        p.drawRect(QRectF(x - 2, 418, 20, 7))
    # Swan-neck pediment
    ped = QPainterPath()
    ped.moveTo(190, 120)
    ped.lineTo(190, 92)
    ped.cubicTo(214, 54, 266, 62, 290, 80)
    ped.lineTo(290, 96)
    ped.lineTo(350, 96)
    ped.lineTo(350, 80)
    ped.cubicTo(374, 62, 426, 54, 450, 92)
    ped.lineTo(450, 120)
    ped.closeSubpath()
    p.setBrush(vgrad(56, 120, MAHOGANY_LIGHT, MAHOGANY, MAHOGANY_DARK))
    p.drawPath(ped)
    for cx, cy in ((290, 82), (350, 82)):
        p.setBrush(radial(cx - 2, cy - 2, 8, BRASS, BRASS_DARK))
        p.drawEllipse(QPointF(cx, cy), 7, 7)
    # Finials
    for x, base, s in ((CX, 96, 1.2), (198, 92, 0.9), (442, 92, 0.9)):
        p.setBrush(BRASS_DARK)
        p.drawRect(QRectF(x - 7 * s, base - 8 * s, 14 * s, 8 * s))
        p.setBrush(radial(x - 3 * s, base - 20 * s, 12 * s, rgb(250, 220, 140), BRASS, BRASS_DARK))
        p.drawEllipse(QPointF(x, base - 18 * s), 10 * s, 10 * s)
        p.setBrush(BRASS)
        p.drawPolygon(poly((x - 3 * s, base - 26 * s), (x, base - 44 * s), (x + 3 * s, base - 26 * s)))

    # The dial: a square plate with a break-arch on top
    plate = QPainterPath()
    plate.moveTo(DIAL.x() - 98, ARCH.y())
    plate.arcTo(QRectF(ARCH.x() - ARCH_R, ARCH.y() - ARCH_R, ARCH_R * 2, ARCH_R * 2), 180, -180)
    plate.lineTo(DIAL.x() + 98, DIAL.y() + 98)
    plate.lineTo(DIAL.x() - 98, DIAL.y() + 98)
    plate.closeSubpath()
    p.setBrush(BRASS_DARK)
    p.drawPath(plate)
    p.save()
    p.translate(CX, DIAL.y())
    p.scale(0.965, 0.965)
    p.translate(-CX, -DIAL.y())
    p.setBrush(vgrad(ARCH.y() - ARCH_R, DIAL.y() + 98, rgb(246, 238, 214), DIAL_FACE, rgb(226, 212, 182)))
    p.drawPath(plate)
    p.restore()

    _paint_moon_arch(p, moon_phase)
    _paint_spandrels(p)
    _paint_chapter_ring(p)
    _paint_seconds_dial(p)

    # Winding holes
    for dx in (-36, 36):
        p.setBrush(rgb(40, 34, 30))
        p.drawEllipse(QPointF(DIAL.x() + dx, DIAL.y() + 30), 6, 6)
        p.setBrush(BRASS)
        p.drawEllipse(QPointF(DIAL.x() + dx, DIAL.y() + 30), 2.5, 2.5)
    # A maker's cartouche
    p.setBrush(rgb(236, 226, 200))
    p.setPen(QPen(alpha(INK, 90), 0.8))
    p.drawRoundedRect(QRectF(CX - 34, DIAL.y() + 46, 68, 15), 5, 5)
    p.setPen(INK)
    f = QFont("serif")
    f.setPixelSize(8)
    f.setItalic(True)
    p.setFont(f)
    p.drawText(QRectF(CX - 34, DIAL.y() + 46, 68, 15), Qt.AlignCenter, "Tempus Fugit")
    p.setPen(Qt.NoPen)


def _paint_moon_arch(p: QPainter, phase: float) -> None:
    clip = QPainterPath()
    r = ARCH_R - 12
    clip.moveTo(ARCH.x() - r, ARCH.y())
    clip.arcTo(QRectF(ARCH.x() - r, ARCH.y() - r, r * 2, r * 2), 180, -180)
    clip.closeSubpath()
    p.save()
    p.setClipPath(clip)
    p.setBrush(vgrad(ARCH.y() - r, ARCH.y(), rgb(20, 36, 92), rgb(44, 70, 140)))
    p.drawRect(QRectF(ARCH.x() - r, ARCH.y() - r, r * 2, r))
    # gold stars painted on the moon disc
    p.setBrush(rgb(240, 210, 120))
    for i in range(16):
        a = i * 2.39996
        d = 30 + (i * 37) % 50
        p.drawEllipse(QPointF(ARCH.x() + math.cos(a) * d, ARCH.y() - abs(math.sin(a)) * d * 0.9 - 6), 1.6, 1.6)
    # The painted moon rides round on the disc: overhead at full moon,
    # down behind the humps at new moon (half a turn per lunar month).
    angle = (phase - 0.5) * math.pi
    mc = QPointF(ARCH.x() + math.sin(angle) * 54, ARCH.y() - math.cos(angle) * 54)
    p.setBrush(radial(mc.x() - 6, mc.y() - 6, 30, rgb(255, 250, 225), rgb(236, 222, 170)))
    p.drawEllipse(mc, 24, 24)
    p.setPen(QPen(alpha(rgb(150, 120, 60), 160), 1))
    p.drawArc(QRectF(mc.x() - 10, mc.y() - 2, 8, 6), 200 * 16, 140 * 16)  # a sleepy face
    p.drawArc(QRectF(mc.x() + 2, mc.y() - 2, 8, 6), 200 * 16, 140 * 16)
    p.drawArc(QRectF(mc.x() - 6, mc.y() + 6, 12, 6), 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    # The two humps (hemispheres) the moon hides behind
    for side in (-1, 1):
        hc = QPointF(ARCH.x() + side * 44, ARCH.y() + 2)
        p.setBrush(radial(hc.x() - 10, hc.y() - 20, 50, rgb(250, 242, 220), rgb(226, 210, 176)))
        p.drawEllipse(hc, 44, 44)
        p.setPen(QPen(alpha(rgb(120, 140, 120), 120), 0.8))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(hc, 30, 40)
        p.drawLine(QPointF(hc.x() - 44, hc.y() - 14), QPointF(hc.x() + 44, hc.y() - 14))
        p.setPen(Qt.NoPen)
    p.restore()
    p.setPen(QPen(BRASS_DARK, 2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(clip)
    p.setPen(Qt.NoPen)


def _paint_spandrels(p: QPainter) -> None:
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = DIAL.x() + sx * 82, DIAL.y() + sy * 82
        p.setBrush(radial(cx, cy, 16, rgb(240, 200, 110), BRASS_DARK))
        p.drawEllipse(QPointF(cx, cy), 9, 9)
        for k in range(3):
            a = math.atan2(-sy, -sx) + (k - 1) * 0.7
            p.drawEllipse(QPointF(cx + math.cos(a) * 12, cy + math.sin(a) * 12), 4.5, 3)


def _paint_chapter_ring(p: QPainter) -> None:
    c = DIAL
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(INK, 1.4))
    p.drawEllipse(c, DIAL_R, DIAL_R)
    p.drawEllipse(c, DIAL_R - 7, DIAL_R - 7)
    p.setPen(QPen(INK, 1))
    p.drawEllipse(c, DIAL_R - 27, DIAL_R - 27)
    for i in range(60):
        a = i / 60 * 2 * math.pi
        r0 = DIAL_R - 7
        p.setPen(QPen(INK, 2.2 if i % 5 == 0 else 1))
        p.drawLine(QPointF(c.x() + math.sin(a) * r0, c.y() - math.cos(a) * r0),
                   QPointF(c.x() + math.sin(a) * DIAL_R, c.y() - math.cos(a) * DIAL_R))
    font = QFont("serif")
    font.setPixelSize(15)
    font.setBold(True)
    p.setFont(font)
    p.setPen(INK)
    for i, numeral in enumerate(ROMAN):
        a = i / 12 * 2 * math.pi
        r = DIAL_R - 17
        p.save()
        p.translate(c.x() + math.sin(a) * r, c.y() - math.cos(a) * r)
        p.rotate(i * 30)
        p.drawText(QRectF(-20, -10, 40, 20), Qt.AlignCenter, numeral)
        p.restore()
    # half-hour fleurs
    p.setPen(Qt.NoPen)
    p.setBrush(INK)
    for i in range(12):
        a = (i + 0.5) / 12 * 2 * math.pi
        r = DIAL_R - 17
        p.drawEllipse(QPointF(c.x() + math.sin(a) * r, c.y() - math.cos(a) * r), 1.6, 1.6)


def _paint_seconds_dial(p: QPainter) -> None:
    c = SECONDS
    p.setPen(QPen(INK, 0.8))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, 19, 19)
    p.drawEllipse(c, 15, 15)
    for i in range(60):
        a = i / 60 * 2 * math.pi
        r1 = 19 if i % 5 == 0 else 17
        p.drawLine(QPointF(c.x() + math.sin(a) * 15, c.y() - math.cos(a) * 15),
                   QPointF(c.x() + math.sin(a) * r1, c.y() - math.cos(a) * r1))
    p.setPen(Qt.NoPen)


def pendulum_angle(now_seconds: float) -> float:
    """Degrees from vertical. A seconds pendulum: it reaches the end of
    each swing exactly on the second, which is when the clock ticks."""
    return SWING_DEGREES * math.cos(math.pi * now_seconds)


def paint_moving(p: QPainter, now: datetime, now_seconds: float, glow: float = 0.0) -> None:
    """Pendulum, weights and hands. now_seconds is a float clock (for the
    pendulum); now is the wall-clock time the hands show."""
    p.setRenderHint(QPainter.Antialiasing)
    _paint_pendulum_and_weights(p, now, now_seconds)
    _paint_hands(p, now)
    # Reflections on the glass of the hood and trunk door
    p.setPen(Qt.NoPen)
    for rect in (QRectF(222, 140, 196, 280), TRUNK_WINDOW):
        p.setBrush(hgrad(rect.left(), rect.right(), (0, rgb(255, 255, 255, 0)), (0.18, rgb(255, 255, 255, 28)),
                         (0.26, rgb(255, 255, 255, 6)), (0.3, rgb(255, 255, 255, 0))))
        p.drawRect(rect)
    if glow > 0:  # firelight catching the brass bezel
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgb(255, 180, 90, 60 * glow), 3))
        p.drawEllipse(DIAL, DIAL_R + 6, DIAL_R + 6)
        p.setPen(Qt.NoPen)


def _paint_pendulum_and_weights(p: QPainter, now: datetime, now_seconds: float) -> None:
    p.save()
    p.setClipRect(TRUNK_WINDOW)
    angle = math.radians(pendulum_angle(now_seconds))
    bob = QPointF(PIVOT.x() + math.sin(angle) * ROD, PIVOT.y() + math.cos(angle) * ROD)
    # rod
    p.setPen(QPen(BRASS_DARK, 4))
    p.drawLine(PIVOT, bob)
    p.setPen(QPen(rgb(240, 210, 130), 1.2))
    p.drawLine(PIVOT, bob)
    p.setPen(Qt.NoPen)
    # bob (with a soft shadow on the case back)
    p.setBrush(rgb(0, 0, 0, 70))
    p.drawEllipse(bob + QPointF(6, 5), 33, 33)
    p.setBrush(radial(bob.x() - 11, bob.y() - 12, 46, (0, rgb(255, 238, 170)), (0.35, BRASS), (1, BRASS_DARK)))
    p.drawEllipse(bob, 32, 32)
    p.setPen(QPen(alpha(BRASS_DARK, 200), 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(bob, 24, 24)
    p.setPen(Qt.NoPen)

    # Three weights on chains, lower as the week runs down (wound on Sundays).
    week = (now.weekday() + 1) % 7 * 24 + now.hour + now.minute / 60  # Sunday 00:00 = 0
    drop = week / 168
    for i, x in enumerate((276, CX, 364)):
        top = 486 + drop * 64 + (i % 2) * 6
        p.setPen(QPen(rgb(180, 150, 80), 1.6, Qt.DotLine))
        p.drawLine(QPointF(x, TRUNK_WINDOW.top()), QPointF(x, top))
        p.setPen(Qt.NoPen)
        p.setBrush(hgrad(x - 11, x + 11, (0, BRASS_DARK), (0.35, rgb(250, 222, 150)), (0.6, BRASS), (1, BRASS_DARK)))
        p.drawRoundedRect(QRectF(x - 11, top, 22, 74), 3, 3)
        p.setBrush(BRASS_DARK)
        p.drawRect(QRectF(x - 11, top + 8, 22, 2))
        p.drawRect(QRectF(x - 11, top + 64, 22, 2))
    p.restore()


def _hand(length: float, width: float, tail: float, spade: float) -> QPainterPath:
    """A blued-steel hand pointing up (towards -y), with a spade near the tip."""
    path = QPainterPath()
    path.moveTo(-width / 2, tail)
    path.lineTo(-width / 2, -length + spade * 2.2)
    path.cubicTo(-spade, -length + spade * 2.4, -spade * 1.1, -length + spade * 0.9, 0, -length)
    path.cubicTo(spade * 1.1, -length + spade * 0.9, spade, -length + spade * 2.4, width / 2, -length + spade * 2.2)
    path.lineTo(width / 2, tail)
    path.closeSubpath()
    return path


def _paint_hands(p: QPainter, now: datetime) -> None:
    hours = (now.hour % 12) + now.minute / 60 + now.second / 3600
    minutes = now.minute + now.second / 60
    steel = rgb(22, 24, 38)

    p.setPen(Qt.NoPen)
    # seconds (jumps once a second, like the real thing)
    p.save()
    p.translate(SECONDS)
    p.rotate(now.second * 6)
    p.setBrush(steel)
    p.drawRect(QRectF(-0.8, -16, 1.6, 20))
    p.restore()
    p.drawEllipse(SECONDS, 2, 2)

    for value, length, width, spade in ((hours / 12, 52, 3.4, 9), (minutes / 60, 82, 2.4, 5)):
        p.save()
        p.translate(DIAL)
        p.rotate(value * 360)
        p.setBrush(rgb(0, 0, 0, 50))
        p.drawPath(_hand(length, width, 14, spade).translated(2, 2))
        p.setBrush(steel)
        p.drawPath(_hand(length, width, 14, spade))
        p.restore()
    p.setBrush(radial(DIAL.x() - 1, DIAL.y() - 1, 6, rgb(250, 220, 140), BRASS_DARK))
    p.drawEllipse(DIAL, 5, 5)
