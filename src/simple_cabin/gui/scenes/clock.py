"""The grandfather (long-case) clock, after a Georgian-style burr walnut
clock: an arched bonnet with three brass finials, turned columns, a gilt
brass dial with a silvered chapter ring and a sun-faced moon in the arch,
and an arched glass trunk door showing three brass tube weights on pulley
wheels, chime rods and a lyre pendulum with a big brass bob.

The case and dial don't change from second to second, so they're painted
into the inside scene's cached layer (paint_case). The hands, pendulum and
weights are painted every frame on top (paint_moving).
"""
from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from simple_cabin.gui import textures as tx
from simple_cabin.gui.paint import alpha, hgrad, mix, poly, radial, rgb, scaled, vgrad

CX = 248.0  # the clock's centre line
TOP = 12.0
FLOOR = 880.0

# Hood and dial
HOOD = QRectF(CX - 128, 128, 256, 330)
DIAL = QPointF(CX, 356)  # centre of the hour dial
DIAL_HALF = 96.0  # the square part of the dial is 2×this wide
DIAL_R = 90.0  # chapter ring
ARCH = QPointF(CX, DIAL.y() - DIAL_HALF)  # centre of the moon arch
ARCH_R = 96.0
SECONDS = QPointF(CX, DIAL.y() - 40)

# Trunk, door and pendulum
TRUNK = QRectF(CX - 96, 486, 192, 262)
DOOR = QRectF(CX - 74, 512, 148, 224)
PIVOT = QPointF(CX, 404)  # behind the dial, where the pendulum hangs from
ROD = 284.0  # pivot to the centre of the bob
BOB_R = 36.0
SWING_DEGREES = 4.2
BASE = QRectF(CX - 120, 770, 240, 92)

WALNUT = rgb(96, 44, 24)
WALNUT_LIGHT = rgb(150, 78, 42)
WALNUT_DARK = rgb(46, 20, 12)
BRASS = rgb(212, 170, 84)
BRASS_LIGHT = rgb(250, 226, 160)
BRASS_DARK = rgb(128, 92, 36)
GILT = rgb(204, 160, 70)
SILVER = rgb(232, 230, 222)
INK = rgb(24, 22, 26)

ROMAN = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]


# --- small helpers


def _burl(p: QPainter, shape, seed: int = 3) -> None:
    """Fill a rect or path with the walnut veneer."""
    rect = shape if isinstance(shape, QRectF) else shape.boundingRect()
    tex = tx.burl(max(8, int(rect.width()) + 2), max(8, int(rect.height()) + 2), seed)
    tx.draw_textured(p, shape, tex)


def _moulding(p: QPainter, x0: float, x1: float, y: float, h: float, overhang: float = 0.0) -> None:
    """A stepped horizontal moulding: light top edge, shadowed cove."""
    r = QRectF(x0 - overhang, y, x1 - x0 + 2 * overhang, h)
    p.setPen(Qt.NoPen)
    p.setBrush(vgrad(r.top(), r.bottom(), (0, WALNUT_LIGHT), (0.3, scaled(WALNUT, 1.15)), (0.55, WALNUT_DARK),
                     (0.75, WALNUT), (1, WALNUT_DARK)))
    p.drawRect(r)
    p.setBrush(alpha(rgb(255, 220, 180), 40))
    p.drawRect(QRectF(r.left(), r.top(), r.width(), 1.5))


def _panel(p: QPainter, rect: QRectF, cut: float, seed: int) -> None:
    """A fielded panel with notched corners, as on the base and hood sides."""
    path = QPainterPath()
    path.moveTo(rect.left() + cut, rect.top())
    path.lineTo(rect.right() - cut, rect.top())
    path.quadTo(rect.right() - cut, rect.top() + cut, rect.right(), rect.top() + cut)
    path.lineTo(rect.right(), rect.bottom() - cut)
    path.quadTo(rect.right() - cut, rect.bottom() - cut, rect.right() - cut, rect.bottom())
    path.lineTo(rect.left() + cut, rect.bottom())
    path.quadTo(rect.left() + cut, rect.bottom() - cut, rect.left(), rect.bottom() - cut)
    path.lineTo(rect.left(), rect.top() + cut)
    path.quadTo(rect.left() + cut, rect.top() + cut, rect.left() + cut, rect.top())
    path.closeSubpath()
    _burl(p, path, seed)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(alpha(WALNUT_DARK, 230), 3))
    p.drawPath(path)
    p.setPen(QPen(alpha(rgb(255, 210, 160), 50), 1))
    p.drawPath(path.translated(1.5, 1.5))
    p.setPen(Qt.NoPen)


def _finial(p: QPainter, x: float, base: float, s: float) -> None:
    """Brass ball-and-spire finial standing on base."""
    p.setPen(Qt.NoPen)
    p.setBrush(hgrad(x - 6 * s, x + 6 * s, BRASS_DARK, BRASS_LIGHT, BRASS, BRASS_DARK))
    p.drawRect(QRectF(x - 6 * s, base - 6 * s, 12 * s, 6 * s))  # collar
    p.drawEllipse(QPointF(x, base - 8 * s), 7 * s, 3 * s)
    ball = QPointF(x, base - 20 * s)
    p.setBrush(radial(ball.x() - 4 * s, ball.y() - 5 * s, 15 * s, (0, BRASS_LIGHT), (0.45, BRASS), (1, BRASS_DARK)))
    p.drawEllipse(ball, 11 * s, 11 * s)
    p.setBrush(hgrad(x - 3 * s, x + 3 * s, BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
    p.drawRect(QRectF(x - 2 * s, base - 34 * s, 4 * s, 4 * s))
    spire = QPainterPath()
    spire.moveTo(x - 4.5 * s, base - 33 * s)
    spire.quadTo(x - 5 * s, base - 44 * s, x, base - 58 * s)
    spire.quadTo(x + 5 * s, base - 44 * s, x + 4.5 * s, base - 33 * s)
    spire.closeSubpath()
    p.setBrush(hgrad(x - 5 * s, x + 5 * s, BRASS_DARK, BRASS_LIGHT, BRASS, BRASS_DARK))
    p.drawPath(spire)
    p.setBrush(radial(x - 1 * s, base - 40 * s, 5 * s, BRASS_LIGHT, BRASS))
    p.drawEllipse(QPointF(x, base - 40 * s), 3.5 * s, 3 * s)


def _column(p: QPainter, x: float, top: float, bottom: float, w: float) -> None:
    """A turned, fluted wooden column with ring mouldings."""
    p.setPen(Qt.NoPen)
    body = QRectF(x - w / 2, top + 10, w, bottom - top - 20)
    p.setBrush(hgrad(body.left(), body.right(), (0, WALNUT_DARK), (0.3, WALNUT_LIGHT), (0.5, scaled(WALNUT, 1.2)), (1, WALNUT_DARK)))
    p.drawRect(body)
    p.setPen(QPen(alpha(WALNUT_DARK, 160), 1))
    for k in range(1, 4):
        fx = body.left() + body.width() * k / 4
        p.drawLine(QPointF(fx, body.top() + 4), QPointF(fx, body.bottom() - 4))
    p.setPen(Qt.NoPen)
    for y, h in ((top, 10), (bottom - 10, 10)):
        p.setBrush(hgrad(x - w / 2 - 3, x + w / 2 + 3, WALNUT_DARK, WALNUT_LIGHT, WALNUT_DARK))
        p.drawRoundedRect(QRectF(x - w / 2 - 3, y, w + 6, h), 3, 3)
        p.setBrush(hgrad(x - w / 2, x + w / 2, BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
        p.drawRect(QRectF(x - w / 2 - 1, y + (h - 2 if y == top else 0), w + 2, 2))


def _scroll(p: QPainter, cx: float, cy: float, r: float, start: float, turns: float, direction: int, width: float) -> None:
    """One curl of gilt ornament: a tapering spiral."""
    path = QPainterPath()
    steps = 24
    for i in range(steps + 1):
        t = i / steps
        a = start + direction * t * turns * 2 * math.pi
        rr = r * (1 - 0.75 * t)
        pt = QPointF(cx + math.cos(a) * rr, cy + math.sin(a) * rr)
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(rgb(90, 60, 20, 200), width + 1.6, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(path.translated(0.8, 0.8))
    p.setPen(QPen(BRASS_LIGHT, width, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(path)


def _spandrel(p: QPainter, cx: float, cy: float, sx: int, sy: int) -> None:
    """Rococo gilt ornament filling a corner of the dial outside the ring:
    a cherub-ish boss with curling leaves and scrolls."""
    p.setPen(Qt.NoPen)
    # leaves fanning out along the two edges
    for k in range(5):
        a = math.atan2(-sy, -sx) + (k - 2) * 0.42
        lx, ly = cx + math.cos(a) * 15, cy + math.sin(a) * 15
        p.save()
        p.translate(lx, ly)
        p.rotate(math.degrees(a))
        p.setBrush(radial(-2, -2, 12, BRASS_LIGHT, GILT, BRASS_DARK))
        p.drawEllipse(QRectF(-4, -4.5, 16, 9))
        p.restore()
    _scroll(p, cx + sx * 10, cy - sy * 14, 9, 0.0, 1.1, sx, 1.8)
    _scroll(p, cx - sx * 14, cy + sy * 10, 9, 1.5, 1.1, -sx, 1.8)
    p.setPen(Qt.NoPen)
    p.setBrush(radial(cx - 2, cy - 3, 11, BRASS_LIGHT, GILT, BRASS_DARK))
    p.drawEllipse(QPointF(cx, cy), 8, 8)
    p.setBrush(rgb(110, 76, 26, 160))
    p.drawEllipse(QPointF(cx - 2.5, cy - 1), 1.3, 1.3)
    p.drawEllipse(QPointF(cx + 2.5, cy - 1), 1.3, 1.3)


# --- the case


def paint_case(p: QPainter, moon_phase: float) -> None:
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    # shadow on the wall behind
    p.setBrush(hgrad(CX - 150, CX + 170, (0, rgb(0, 0, 0, 0)), (0.22, rgb(0, 0, 0, 70)), (0.8, rgb(0, 0, 0, 70)), (1, rgb(0, 0, 0, 0))))
    p.drawRect(QRectF(CX - 150, 100, 320, FLOOR - 100))
    p.setBrush(radial(CX + 10, FLOOR, 200, (0, rgb(0, 0, 0, 110)), (1, rgb(0, 0, 0, 0))))
    p.drawEllipse(QPointF(CX + 10, FLOOR), 200, 20)

    _paint_base(p)
    _paint_trunk(p)
    _paint_hood(p, moon_phase)


def _paint_base(p: QPainter) -> None:
    # ogee bracket feet
    for side in (-1, 1):
        x = CX + side * (BASE.width() / 2 - 4)
        foot = QPainterPath()
        foot.moveTo(x, FLOOR - 26)
        foot.lineTo(x, FLOOR)
        foot.lineTo(x - side * 24, FLOOR)
        foot.cubicTo(x - side * 26, FLOOR - 10, x - side * 40, FLOOR - 8, x - side * 46, FLOOR - 18)
        foot.lineTo(x - side * 52, FLOOR - 26)
        foot.closeSubpath()
        p.setBrush(vgrad(FLOOR - 26, FLOOR, WALNUT_LIGHT, WALNUT, WALNUT_DARK))
        p.drawPath(foot)
    _moulding(p, BASE.left(), BASE.right(), FLOOR - 32, 10, 6)
    # base box
    box = QRectF(BASE.left(), BASE.top() + 14, BASE.width(), FLOOR - 32 - BASE.top() - 14)
    _burl(p, box, 21)
    tx.shade_rect(p, box, top=0.15, bottom=0.25, left=0.35, right=0.4)
    _panel(p, box.adjusted(22, 12, -22, -12), 12, 22)
    # plinth moulding where the trunk meets the base
    _moulding(p, BASE.left(), BASE.right(), BASE.top(), 16, 6)
    p.setBrush(vgrad(BASE.top() - 10, BASE.top(), WALNUT, WALNUT_DARK))
    p.drawRect(QRectF(TRUNK.left() - 8, BASE.top() - 8, TRUNK.width() + 16, 9))


def _paint_trunk(p: QPainter) -> None:
    trunk = QRectF(TRUNK.left(), TRUNK.top(), TRUNK.width(), BASE.top() - TRUNK.top())
    _burl(p, trunk, 11)
    tx.shade_rect(p, trunk, left=0.4, right=0.45)
    # quarter columns at the trunk's front corners
    for x in (trunk.left() + 6, trunk.right() - 6):
        p.setBrush(hgrad(x - 6, x + 6, WALNUT_DARK, WALNUT_LIGHT, WALNUT_DARK))
        p.drawRect(QRectF(x - 6, trunk.top() + 6, 12, trunk.height() - 12))
        p.setBrush(WALNUT_DARK)
        p.drawEllipse(QPointF(x, trunk.bottom() - 10), 7, 4)
        p.drawEllipse(QPointF(x, trunk.top() + 12), 7, 4)

    door = door_path()
    # the door's moulded frame
    p.setBrush(vgrad(DOOR.top(), DOOR.bottom(), WALNUT_LIGHT, WALNUT, WALNUT_DARK))
    p.drawPath(door_path(9))
    p.setBrush(WALNUT_DARK)
    p.drawPath(door_path(3))
    # inside the case: the dark back board with a soft pool of light
    p.save()
    p.setClipPath(door)
    p.fillRect(DOOR.adjusted(-10, -40, 10, 10), vgrad(DOOR.top() - 40, DOOR.bottom(), rgb(30, 16, 10), rgb(48, 24, 14), rgb(26, 12, 8)))
    p.setBrush(radial(CX, DOOR.top() + 120, 140, (0, rgb(90, 50, 26, 120)), (1, rgb(0, 0, 0, 0))))
    p.drawEllipse(QPointF(CX, DOOR.top() + 120), 140, 160)
    # chime rods hanging behind everything
    for i in range(7):
        x = CX - 48 + i * 16
        length = 170 - abs(i - 3) * 8
        p.setBrush(hgrad(x - 2.5, x + 2.5, rgb(110, 84, 40), rgb(230, 200, 130), rgb(110, 84, 40)))
        p.drawRect(QRectF(x - 2, DOOR.top() - 30, 4, length + 30))
        p.setBrush(rgb(80, 60, 30))
        p.drawEllipse(QPointF(x, DOOR.top() + length), 2.5, 2)
    p.restore()
    # brass escutcheon (keyhole) on the left stile, hinges on the right
    ex, ey = DOOR.left() - 1, DOOR.center().y() + 30
    p.setBrush(radial(ex - 1, ey - 4, 10, BRASS_LIGHT, BRASS, BRASS_DARK))
    shield = QPainterPath()
    shield.moveTo(ex, ey - 15)
    shield.cubicTo(ex + 7, ey - 10, ex + 6, ey + 8, ex, ey + 15)
    shield.cubicTo(ex - 6, ey + 8, ex - 7, ey - 10, ex, ey - 15)
    p.drawPath(shield)
    p.setBrush(rgb(30, 20, 10))
    p.drawEllipse(QPointF(ex, ey - 3), 1.6, 1.6)
    p.drawRect(QRectF(ex - 0.8, ey - 2, 1.6, 6))
    for y in (DOOR.top() + 40, DOOR.bottom() - 40):
        p.setBrush(hgrad(DOOR.right() + 2, DOOR.right() + 7, BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
        p.drawRect(QRectF(DOOR.right() + 2, y - 16, 5, 32))
    # moulding at the waist, under the hood
    _moulding(p, TRUNK.left() - 4, TRUNK.right() + 4, TRUNK.top() - 4, 14, 4)


def door_path(grow: float = 0.0) -> QPainterPath:
    """The trunk door's glass: straight sides with a shaped (bonnet) top."""
    r = DOOR.adjusted(-grow, -grow, grow, grow)
    path = QPainterPath()
    shoulder = r.top() + 30
    path.moveTo(r.left(), r.bottom())
    path.lineTo(r.left(), shoulder)
    path.cubicTo(r.left(), r.top() + 8, r.left() + r.width() * 0.25, r.top() + 14, r.left() + r.width() * 0.35, r.top() + 6)
    path.quadTo(CX, r.top() - 8, r.right() - r.width() * 0.35, r.top() + 6)
    path.cubicTo(r.right() - r.width() * 0.25, r.top() + 14, r.right(), r.top() + 8, r.right(), shoulder)
    path.lineTo(r.right(), r.bottom())
    path.closeSubpath()
    return path


def _paint_hood(p: QPainter, moon_phase: float) -> None:
    hood = HOOD
    # cornice under the hood, wider than the trunk
    _moulding(p, hood.left() - 6, hood.right() + 6, hood.bottom() - 4, 18, 4)
    _moulding(p, hood.left() + 6, hood.right() - 6, hood.bottom() + 12, 12, 0)

    # the hood's front: veneer with an arched opening for the dial
    front = QPainterPath()
    front.addRect(QRectF(hood.left(), hood.top() + 12, hood.width(), hood.height() - 12))
    _burl(p, front, 31)
    tx.shade_rect(p, QRectF(hood.left(), hood.top(), hood.width(), hood.height()), top=0.2, bottom=0.25, left=0.35, right=0.4)

    # the arched bonnet top with its thick moulded edge
    bonnet = QPainterPath()
    l, r = hood.left() - 10, hood.right() + 10
    base_y = hood.top() + 22
    bonnet.moveTo(l, base_y)
    bonnet.lineTo(l + 26, base_y)
    bonnet.cubicTo(l + 30, TOP + 84, CX - 70, TOP + 79, CX, TOP + 78)
    bonnet.cubicTo(CX + 70, TOP + 79, r - 30, TOP + 84, r - 26, base_y)
    bonnet.lineTo(r, base_y)
    bonnet.lineTo(r, base_y + 16)
    bonnet.lineTo(l, base_y + 16)
    bonnet.closeSubpath()
    _burl(p, bonnet, 41)
    # stacked mouldings following the arch
    for i, (w, c) in enumerate(((16, WALNUT_DARK), (11, WALNUT_LIGHT), (6, scaled(WALNUT, 1.1)), (2, rgb(255, 210, 170, 70)))):
        arch = QPainterPath()
        arch.moveTo(l + 26, base_y + 4)
        arch.cubicTo(l + 30, TOP + 84 + i, CX - 70, TOP + 79 + i, CX, TOP + 78 + i)
        arch.cubicTo(CX + 70, TOP + 79 + i, r - 30, TOP + 84 + i, r - 26, base_y + 4)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.FlatCap))
        p.drawPath(arch)
    p.setPen(Qt.NoPen)
    # scrolled ends of the arch, and the side plinths for the finials
    for side in (-1, 1):
        sx = CX + side * (hood.width() / 2 + 2)
        p.setBrush(radial(sx, base_y - 4, 14, WALNUT_LIGHT, WALNUT_DARK))
        p.drawEllipse(QPointF(sx - side * 4, base_y - 2), 10, 10)
        plinth = QRectF(sx - 14 + side * 4, base_y - 22, 28, 22)
        p.setBrush(vgrad(plinth.top(), plinth.bottom(), WALNUT_LIGHT, WALNUT, WALNUT_DARK))
        p.drawRect(plinth)
        _moulding(p, plinth.left(), plinth.right(), plinth.top() - 5, 6, 2)
        _finial(p, plinth.center().x(), plinth.top() - 5, 0.95)
    # the central plinth and finial on the crown of the arch
    plinth = QRectF(CX - 17, TOP + 56, 34, 22)
    p.setBrush(vgrad(plinth.top(), plinth.bottom(), WALNUT_LIGHT, WALNUT, WALNUT_DARK))
    p.drawRect(plinth)
    _moulding(p, plinth.left(), plinth.right(), plinth.top() - 5, 6, 2)
    _finial(p, CX, plinth.top() - 5, 1.0)

    # turned columns either side of the dial
    for x in (hood.left() + 14, hood.right() - 14):
        _column(p, x, hood.top() + 40, hood.bottom() - 6, 16)

    # the dial door's frame (a gilt-edged arch)
    frame = dial_path(10)
    p.setBrush(vgrad(ARCH.y() - ARCH_R, DIAL.y() + DIAL_HALF, WALNUT_LIGHT, WALNUT, WALNUT_DARK))
    p.drawPath(frame)
    p.setBrush(BRASS_DARK)
    p.drawPath(dial_path(3))
    _paint_dial(p, moon_phase)


def dial_path(grow: float = 0.0) -> QPainterPath:
    """The arched dial plate's outline."""
    r = ARCH_R + grow
    path = QPainterPath()
    path.moveTo(DIAL.x() - DIAL_HALF - grow, ARCH.y())
    path.arcTo(QRectF(ARCH.x() - r, ARCH.y() - r, r * 2, r * 2), 180, -180)
    path.lineTo(DIAL.x() + DIAL_HALF + grow, DIAL.y() + DIAL_HALF + grow)
    path.lineTo(DIAL.x() - DIAL_HALF - grow, DIAL.y() + DIAL_HALF + grow)
    path.closeSubpath()
    return path


# --- the dial


def _paint_dial(p: QPainter, moon_phase: float) -> None:
    plate = dial_path()
    # gilt brass plate with a faint matted (frosted) finish
    p.setBrush(vgrad(ARCH.y() - ARCH_R, DIAL.y() + DIAL_HALF, rgb(232, 196, 110), GILT, rgb(170, 128, 52)))
    p.drawPath(plate)
    p.save()
    p.setClipPath(plate)
    p.setPen(QPen(rgb(255, 240, 200, 26), 1))
    for i in range(0, 220, 3):
        p.drawLine(QPointF(DIAL.x() - DIAL_HALF, ARCH.y() - ARCH_R + i), QPointF(DIAL.x() + DIAL_HALF, ARCH.y() - ARCH_R + i + 4))
    p.restore()
    p.setPen(Qt.NoPen)

    _paint_moon_arch(p, moon_phase)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        _spandrel(p, DIAL.x() + sx * (DIAL_HALF - 20), DIAL.y() + sy * (DIAL_HALF - 20), sx, sy)
    _paint_chapter_ring(p)
    _paint_seconds_dial(p)
    # winding holes (three trains: time, strike, chime)
    for dx in (-34, 0, 34):
        c = QPointF(DIAL.x() + dx, DIAL.y() + 34)
        p.setBrush(radial(c.x(), c.y(), 7, rgb(60, 50, 40), rgb(20, 16, 12)))
        p.drawEllipse(c, 5.5, 5.5)
        p.setBrush(BRASS)
        p.drawEllipse(c, 2, 2)


def _paint_moon_arch(p: QPainter, phase: float) -> None:
    r = ARCH_R - 8
    clip = QPainterPath()
    clip.moveTo(ARCH.x() - r, ARCH.y())
    clip.arcTo(QRectF(ARCH.x() - r, ARCH.y() - r, r * 2, r * 2), 180, -180)
    clip.closeSubpath()
    # the lunar calendar ring around the arch: tiny numbers 1..29½
    p.setPen(QPen(rgb(80, 54, 18), 1))
    p.setBrush(rgb(236, 222, 186))
    ring = QPainterPath()
    ring.moveTo(ARCH.x() - ARCH_R + 2, ARCH.y())
    ring.arcTo(QRectF(ARCH.x() - ARCH_R + 2, ARCH.y() - ARCH_R + 2, (ARCH_R - 2) * 2, (ARCH_R - 2) * 2), 180, -180)
    ring.closeSubpath()
    p.drawPath(ring)
    font = QFont("serif")
    font.setPixelSize(6)
    p.setFont(font)
    p.setPen(INK)
    for day in range(1, 30, 2):
        a = math.pi - (day / 29.5) * math.pi
        rr = ARCH_R - 5
        pt = QPointF(ARCH.x() + math.cos(a) * rr, ARCH.y() - math.sin(a) * rr)
        p.save()
        p.translate(pt)
        p.rotate(90 - math.degrees(a))
        p.drawText(QRectF(-6, -4, 12, 8), Qt.AlignCenter, str(day))
        p.restore()
    p.setPen(Qt.NoPen)

    p.save()
    p.setClipPath(clip)
    p.setBrush(radial(ARCH.x(), ARCH.y(), r, rgb(40, 64, 140), rgb(18, 30, 84)))
    p.drawRect(QRectF(ARCH.x() - r, ARCH.y() - r, r * 2, r))
    # gold stars and a little painted landscape on the disc
    for i in range(22):
        a = i * 2.39996
        d = 24 + (i * 37) % 60
        sx, sy = ARCH.x() + math.cos(a) * d, ARCH.y() - abs(math.sin(a)) * d * 0.95 - 4
        _star(p, sx, sy, 2.4 if i % 3 else 3.4)
    # The moon rides round on the disc: overhead at full moon, down
    # behind the hemispheres at new moon (half a turn per lunar month).
    angle = (phase - 0.5) * math.pi
    for offset in (0.0, math.pi):  # the disc carries two moons, opposite
        a = angle + offset
        mc = QPointF(ARCH.x() + math.sin(a) * 56, ARCH.y() - math.cos(a) * 56)
        _moon_face(p, mc, 26)
    # the two hemispheres the moon hides behind, gilded
    for side in (-1, 1):
        hc = QPointF(ARCH.x() + side * 46, ARCH.y() + 1)
        p.setBrush(radial(hc.x() - 12, hc.y() - 22, 50, BRASS_LIGHT, GILT, BRASS_DARK))
        p.drawEllipse(hc, 46, 46)
        p.save()
        hemi = QPainterPath()
        hemi.addEllipse(hc, 46, 46)
        p.setClipPath(hemi, Qt.IntersectClip)
        for k in range(4):
            _scroll(p, hc.x() + (k - 1.5) * 18, hc.y() - 20 - (k % 2) * 8, 8, k * 1.2, 1.0, 1 if k % 2 else -1, 1.3)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(BRASS_DARK, 1.2))
        p.drawEllipse(hc, 46, 46)
        p.setPen(Qt.NoPen)
    p.restore()
    p.setPen(QPen(BRASS_DARK, 1.5))
    p.setBrush(Qt.NoBrush)
    p.drawPath(clip)
    p.setPen(Qt.NoPen)


def _star(p: QPainter, x: float, y: float, r: float) -> None:
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.42
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    p.setBrush(rgb(250, 214, 110))
    p.drawPolygon(poly(*pts))


def _moon_face(p: QPainter, c: QPointF, r: float) -> None:
    """The traditional golden moon with a face."""
    p.setPen(Qt.NoPen)
    p.setBrush(radial(c.x() - r * 0.3, c.y() - r * 0.35, r * 1.3, (0, rgb(255, 238, 160)), (0.5, rgb(236, 190, 80)), (1, rgb(170, 120, 40))))
    p.drawEllipse(c, r, r)
    ink = QPen(rgb(120, 72, 20), 1.3, Qt.SolidLine, Qt.RoundCap)
    p.setPen(ink)
    p.setBrush(Qt.NoBrush)
    for dx in (-0.36, 0.36):  # sleepy eyes and brows
        p.drawArc(QRectF(c.x() + dx * r - 5, c.y() - r * 0.22 - 2, 10, 6), 200 * 16, 140 * 16)
        p.drawArc(QRectF(c.x() + dx * r - 6, c.y() - r * 0.42 - 3, 12, 8), 30 * 16, 120 * 16)
    nose = QPainterPath()
    nose.moveTo(c.x(), c.y() - r * 0.12)
    nose.quadTo(c.x() + 4, c.y() + r * 0.18, c.x() - 2, c.y() + r * 0.2)
    p.drawPath(nose)
    p.drawArc(QRectF(c.x() - r * 0.3, c.y() + r * 0.12, r * 0.6, r * 0.36), 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    p.setBrush(rgb(230, 120, 70, 70))
    p.drawEllipse(QPointF(c.x() - r * 0.48, c.y() + r * 0.15), 4.5, 3)
    p.drawEllipse(QPointF(c.x() + r * 0.48, c.y() + r * 0.15), 4.5, 3)


def _paint_chapter_ring(p: QPainter) -> None:
    c = DIAL
    # the silvered ring (and centre, as on the reference clock)
    p.setBrush(radial(c.x() - 30, c.y() - 30, DIAL_R * 1.6, (0, rgb(250, 249, 244)), (0.6, SILVER), (1, rgb(196, 194, 186))))
    p.setPen(QPen(rgb(150, 140, 120), 1))
    p.drawEllipse(c, DIAL_R + 2, DIAL_R + 2)
    p.setPen(QPen(rgb(190, 186, 176, 90), 0.6))
    p.setBrush(Qt.NoBrush)
    for rr in range(8, int(DIAL_R), 6):  # turned (engine-turned) circles
        p.drawEllipse(c, rr, rr)
    p.setPen(QPen(INK, 1.1))
    p.drawEllipse(c, DIAL_R - 3, DIAL_R - 3)
    p.drawEllipse(c, DIAL_R - 9, DIAL_R - 9)
    for i in range(60):
        a = i / 60 * 2 * math.pi
        r0, r1 = DIAL_R - 9, DIAL_R - 3
        p.setPen(QPen(INK, 1.8 if i % 5 == 0 else 0.8))
        p.drawLine(QPointF(c.x() + math.sin(a) * r0, c.y() - math.cos(a) * r0),
                   QPointF(c.x() + math.sin(a) * r1, c.y() - math.cos(a) * r1))
    font = QFont("serif")
    font.setPixelSize(17)
    p.setFont(font)
    p.setPen(INK)
    for i, numeral in enumerate(ROMAN):
        a = i / 12 * 2 * math.pi
        r = DIAL_R - 22
        p.save()
        p.translate(c.x() + math.sin(a) * r, c.y() - math.cos(a) * r)
        p.rotate(i * 30)
        p.scale(0.8, 1.0)  # tall, narrow numerals
        p.drawText(QRectF(-26, -11, 52, 22), Qt.AlignCenter, numeral)
        p.restore()
    p.setPen(QPen(INK, 0.8))
    p.drawEllipse(c, DIAL_R - 33, DIAL_R - 33)
    p.setPen(Qt.NoPen)


def _paint_seconds_dial(p: QPainter) -> None:
    c = SECONDS
    p.setPen(QPen(INK, 0.8))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, 17, 17)
    p.drawEllipse(c, 13, 13)
    for i in range(60):
        a = i / 60 * 2 * math.pi
        r1 = 17 if i % 5 == 0 else 15
        p.drawLine(QPointF(c.x() + math.sin(a) * 13, c.y() - math.cos(a) * 13),
                   QPointF(c.x() + math.sin(a) * r1, c.y() - math.cos(a) * r1))
    p.setPen(Qt.NoPen)


# --- moving parts


def pendulum_angle(now_seconds: float) -> float:
    """Degrees from vertical. A seconds pendulum: it reaches the end of
    each swing exactly on the second, which is when the clock ticks."""
    return SWING_DEGREES * math.cos(math.pi * now_seconds)


def paint_moving(p: QPainter, now: datetime, now_seconds: float, glow: float = 0.0) -> None:
    """Pendulum, weights and hands. now_seconds is a float clock (for the
    pendulum); now is the wall-clock time the hands show."""
    p.setRenderHint(QPainter.Antialiasing)
    p.save()
    p.setClipPath(door_path())
    _paint_pendulum(p, now_seconds)
    _paint_weights(p, now)
    p.restore()
    _paint_hands(p, now)
    # Reflections on the glass of the dial door and trunk door
    p.setPen(Qt.NoPen)
    for path in (dial_path(), door_path()):
        r = path.boundingRect()
        p.save()
        p.setClipPath(path)
        p.setBrush(hgrad(r.left(), r.right(), (0, rgb(255, 255, 255, 0)), (0.12, rgb(255, 255, 255, 30)),
                         (0.2, rgb(255, 255, 255, 8)), (0.24, rgb(255, 255, 255, 0)), (0.8, rgb(255, 255, 255, 0)),
                         (0.86, rgb(255, 255, 255, 14)), (0.9, rgb(255, 255, 255, 0))))
        p.drawRect(r)
        p.restore()
    if glow > 0:  # firelight catching the brass
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgb(255, 180, 90, 50 * glow), 3))
        p.drawPath(dial_path(5))
        p.setPen(Qt.NoPen)


def _paint_pendulum(p: QPainter, now_seconds: float) -> None:
    angle = pendulum_angle(now_seconds)
    p.save()
    p.translate(PIVOT)
    p.rotate(-angle)
    # the rod: a grid of five thin brass rods down to the lyre
    lyre_top = ROD - BOB_R - 66
    for k in range(-2, 3):
        x = k * 4.5
        p.setPen(QPen(rgb(120, 90, 40), 2.2))
        p.drawLine(QPointF(x, 0), QPointF(x, lyre_top + 6))
        p.setPen(QPen(BRASS_LIGHT, 0.9))
        p.drawLine(QPointF(x - 0.4, 0), QPointF(x - 0.4, lyre_top + 6))
    for y in (lyre_top - 150, lyre_top - 70):
        p.setPen(Qt.NoPen)
        p.setBrush(hgrad(-12, 12, BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
        p.drawRect(QRectF(-12, y, 24, 4))
    # the lyre
    p.setBrush(Qt.NoBrush)
    for w, c in ((5, BRASS_DARK), (2.5, BRASS), (1, BRASS_LIGHT)):
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap))
        for side in (-1, 1):
            arm = QPainterPath(QPointF(side * 6, lyre_top))
            arm.cubicTo(side * 38, lyre_top + 6, side * 8, lyre_top + 38, side * 22, lyre_top + 62)
            p.drawPath(arm)
            scroll = QPainterPath(QPointF(side * 6, lyre_top))
            scroll.cubicTo(side * 16, lyre_top - 14, side * 30, lyre_top - 4, side * 22, lyre_top + 6)
            p.drawPath(scroll)
    p.setPen(QPen(BRASS, 1.6))
    for k in range(-2, 3):
        p.drawLine(QPointF(k * 4, lyre_top + 4), QPointF(k * 5, lyre_top + 64))
    p.setPen(Qt.NoPen)
    p.setBrush(hgrad(-20, 20, BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
    p.drawRect(QRectF(-20, lyre_top + 60, 40, 6))
    # the bob: a big polished brass disc
    bob = QPointF(0, ROD)
    p.setBrush(rgb(0, 0, 0, 40))
    p.drawEllipse(bob + QPointF(3, 5), BOB_R, BOB_R)
    p.setBrush(radial(-BOB_R * 0.35, ROD - BOB_R * 0.4, BOB_R * 1.6, (0, rgb(255, 246, 200)), (0.25, BRASS_LIGHT), (0.6, BRASS), (1, BRASS_DARK)))
    p.drawEllipse(bob, BOB_R, BOB_R)
    p.setBrush(radial(BOB_R * 0.1, ROD + BOB_R * 0.1, BOB_R * 0.8, (0, rgb(255, 240, 190, 0)), (0.85, rgb(255, 240, 190, 0)), (1, rgb(120, 86, 30, 120))))
    p.drawEllipse(bob, BOB_R * 0.78, BOB_R * 0.78)
    p.setPen(QPen(rgb(150, 110, 40, 140), 0.8))
    p.drawLine(QPointF(0, ROD - BOB_R + 4), QPointF(0, ROD + BOB_R - 4))
    p.setPen(Qt.NoPen)
    p.setBrush(BRASS_DARK)
    p.drawPolygon(poly((-3, ROD + BOB_R - 1), (3, ROD + BOB_R - 1), (0, ROD + BOB_R + 9)))  # rating nut
    p.restore()


def _paint_weights(p: QPainter, now: datetime) -> None:
    """Three brass tube weights on pulleys, lower as the week runs down
    (wound on Sundays). The middle one hangs lower, as on the reference."""
    week = (now.weekday() + 1) % 7 * 24 + now.hour + now.minute / 60  # Sunday 00:00 = 0
    drop = week / 168 * 40
    for i, x in enumerate((CX - 44, CX, CX + 44)):
        top = DOOR.top() + 12 + drop * 0.4 + (12 if i == 1 else 0)
        # chains (two strands up to the movement)
        p.setPen(QPen(rgb(170, 140, 70), 1.2, Qt.DotLine))
        for dx in (-7, 7):
            p.drawLine(QPointF(x + dx, DOOR.top() - 40), QPointF(x + dx, top - 12))
        p.setPen(Qt.NoPen)
        # spoked pulley wheel
        c = QPointF(x, top - 12)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(BRASS, 2.2))
        p.drawEllipse(c, 9, 9)
        p.setPen(QPen(BRASS, 1.2))
        for k in range(4):
            a = k * math.pi / 4
            p.drawLine(QPointF(c.x() - math.cos(a) * 8, c.y() - math.sin(a) * 8), QPointF(c.x() + math.cos(a) * 8, c.y() + math.sin(a) * 8))
        p.setPen(Qt.NoPen)
        p.setBrush(BRASS_DARK)
        p.drawRect(QRectF(x - 1.5, top - 6, 3, 8))
        # the tube
        tube = QRectF(x - 13, top, 26, 70)
        p.setBrush(hgrad(tube.left(), tube.right(), (0, rgb(110, 80, 30)), (0.28, BRASS_LIGHT), (0.45, rgb(236, 206, 130)),
                         (0.75, BRASS), (1, rgb(100, 72, 28))))
        p.drawRect(tube)
        for y in (tube.top(), tube.bottom() - 4):
            p.setBrush(hgrad(tube.left(), tube.right(), BRASS_DARK, BRASS_LIGHT, BRASS_DARK))
            p.drawRect(QRectF(tube.left() - 1, y, tube.width() + 2, 4))


def _hand(p: QPainter, length: float, kind: str) -> None:
    """Pierced (openwork) blued-steel hands, pointing up (towards -y)."""
    steel = QColor(18, 18, 26)
    p.setBrush(steel)
    p.setPen(Qt.NoPen)
    if kind == "hour":
        p.drawRect(QRectF(-1.8, -length * 0.55, 3.6, length * 0.55 + 14))
        # an open heart-shaped boss two-thirds out
        boss = QPointF(0, -length * 0.62)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(steel, 2.6))
        p.drawEllipse(QPointF(-5, boss.y()), 5.5, 6.5)
        p.drawEllipse(QPointF(5, boss.y()), 5.5, 6.5)
        p.setPen(Qt.NoPen)
        p.setBrush(steel)
        tip = QPainterPath()
        tip.moveTo(-6, -length * 0.7)
        tip.quadTo(-4, -length * 0.9, 0, -length)
        tip.quadTo(4, -length * 0.9, 6, -length * 0.7)
        tip.closeSubpath()
        p.drawPath(tip)
    else:
        # a long serpentine minute hand with a small pierced loop
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(steel, 2.4, Qt.SolidLine, Qt.RoundCap))
        snake = QPainterPath(QPointF(0, 14))
        snake.lineTo(0, -length * 0.25)
        snake.cubicTo(5, -length * 0.4, -5, -length * 0.55, 0, -length * 0.68)
        snake.lineTo(0, -length * 0.8)
        p.drawPath(snake)
        p.setPen(QPen(steel, 2.0))
        p.drawEllipse(QPointF(0, -length * 0.27), 4, 5)
        p.setPen(Qt.NoPen)
        p.setBrush(steel)
        tip = QPainterPath()
        tip.moveTo(-3.2, -length * 0.8)
        tip.lineTo(0, -length)
        tip.lineTo(3.2, -length * 0.8)
        tip.closeSubpath()
        p.drawPath(tip)


def _paint_hands(p: QPainter, now: datetime) -> None:
    hours = (now.hour % 12) + now.minute / 60 + now.second / 3600
    minutes = now.minute + now.second / 60

    # seconds (jumps once a second, like the real thing)
    p.save()
    p.translate(SECONDS)
    p.rotate(now.second * 6)
    p.setPen(Qt.NoPen)
    p.setBrush(rgb(18, 18, 26))
    p.drawRect(QRectF(-0.7, -15, 1.4, 19))
    p.restore()
    p.setBrush(rgb(18, 18, 26))
    p.drawEllipse(SECONDS, 1.8, 1.8)

    for value, length, kind in ((hours / 12, 56, "hour"), (minutes / 60, 84, "minute")):
        p.save()
        p.translate(DIAL + QPointF(2, 2.5))
        p.rotate(value * 360)
        p.setOpacity(0.25)
        _hand(p, length, kind)  # its shadow on the dial
        p.restore()
        p.save()
        p.translate(DIAL)
        p.rotate(value * 360)
        _hand(p, length, kind)
        p.restore()
    p.setBrush(radial(DIAL.x() - 1.5, DIAL.y() - 1.5, 7, BRASS_LIGHT, BRASS_DARK))
    p.drawEllipse(DIAL, 4.5, 4.5)
