"""Seasonal decorations for the cabin, inside and out: Halloween, Christmas,
Easter and New Year (with fireworks over the lake on New Year's Eve).

Like the rest of the scenes, each has a static part (painted into the
cached room or land layer) and a part drawn every frame (glowing
jack-o'-lanterns, twinkling lights, a bobbing spider, bats, fireworks).
"""
from __future__ import annotations

import math
import random
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from simple_cabin.core.seasons import CHRISTMAS, EASTER, HALLOWEEN, NEW_YEAR
from simple_cabin.gui.paint import alpha, draw_pine, hgrad, mix, poly, radial, rgb, scaled, vgrad, wobble

# Where things go in the room (see inside.py for the furniture)
MANTEL_LEFT, MANTEL_RIGHT, MANTEL_TOP, MANTEL_BOTTOM = 450.0, 1020.0, 366.0, 408.0
HEARTH_TOP = 650.0
TREE = QPointF(1214, 776)  # foot of the Christmas tree (it stands where the armchair was)
TREE_H, TREE_W = 480.0, 280.0
WEB = QPointF(1062, 116)  # the corner between the post and the tie beam

PUMPKINS_INSIDE = ((QPointF(510, HEARTH_TOP), 1.5, True), (QPointF(580, HEARTH_TOP), 0.9, False), (QPointF(964, MANTEL_TOP), 1.0, True))
PUMPKINS_OUTSIDE = ((QPointF(212, 586), 1.2), (QPointF(440, 586), 1.0), (QPointF(1100, 586), 1.1), (QPointF(1052, 590), 0.7))

ORANGE = rgb(236, 120, 30)
GLOW = rgb(255, 170, 60)

_rng_cache: dict = {}


def _points(key: str, maker):
    """Positions that should stay the same from frame to frame."""
    if key not in _rng_cache:
        _rng_cache[key] = maker()
    return _rng_cache[key]


def _sag(x0: float, x1: float, y: float, sag: float, t: float) -> QPointF:
    """A point at fraction t along a rope hung between (x0, y) and (x1, y)."""
    return QPointF(x0 + (x1 - x0) * t, y + sag * 4 * t * (1 - t))


# ======================================================================
# inside


def inside_static(p: QPainter, kind: Optional[str], layer: str) -> None:
    """layer: "mantel" (after the fireplace), "back" (after the lamp, before
    the rug and furniture in front) or "table" (after the coffee table)."""
    if kind is None:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    {
        HALLOWEEN: _halloween_inside,
        CHRISTMAS: _christmas_inside,
        EASTER: _easter_inside,
        NEW_YEAR: _new_year_inside,
    }[kind](p, layer)
    p.restore()


def hides_armchair(kind: Optional[str]) -> bool:
    return kind == CHRISTMAS


def inside_dynamic(p: QPainter, kind: Optional[str], t: float) -> None:
    if kind is None:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    if kind == HALLOWEEN:
        for c, s, carved in PUMPKINS_INSIDE:
            if carved:
                _pumpkin_glow(p, c, s, t)
        _spider(p, t)
    elif kind == CHRISTMAS:
        _tree_lights(p, t)
        _mantel_lights(p, t)
    elif kind == NEW_YEAR:
        _balloons(p, t)
    p.restore()


def inside_lights(kind: Optional[str]) -> list[tuple[float, float, float, float]]:
    """Extra light sources for the room's lighting: (x, y, radius, strength)."""
    if kind == HALLOWEEN:
        return [(c.x(), c.y() - 30 * s, 170 * s, 0.5) for c, s, carved in PUMPKINS_INSIDE if carved]
    if kind == CHRISTMAS:
        return [(TREE.x(), TREE.y() - TREE_H * 0.45, 330, 0.55), ((MANTEL_LEFT + MANTEL_RIGHT) / 2, MANTEL_BOTTOM, 320, 0.3)]
    return []


# --- Halloween


def _halloween_inside(p: QPainter, layer: str) -> None:
    if layer == "mantel":
        # orange and black bunting along the mantel
        _bunting(p, MANTEL_LEFT + 6, MANTEL_RIGHT - 6, MANTEL_BOTTOM - 4, 18, 22, [ORANGE, rgb(30, 26, 28)], triangles=True)
        # paper bats stuck on the chimney stones
        for x, y, s in ((524, 92, 1.0), (612, 140, 0.75), (880, 100, 0.95), (948, 160, 0.7), (836, 46, 0.8), (520, 220, 0.7)):
            _bat_shape(p, x, y, 56 * s, 0.6, rgb(24, 20, 22))
        # pumpkins on the hearth and the mantel
        for c, s, carved in PUMPKINS_INSIDE:
            _pumpkin(p, c, s, carved)
    elif layer == "back":
        _cobweb(p, WEB, 96)


def _pumpkin(p: QPainter, base: QPointF, s: float, carved: bool) -> None:
    w, h = 46 * s, 36 * s
    c = QPointF(base.x(), base.y() - h / 2)
    p.setBrush(radial(c.x(), base.y(), w, (0, rgb(0, 0, 0, 90)), (1, rgb(0, 0, 0, 0))))
    p.drawEllipse(QPointF(c.x(), base.y()), w * 0.9, h * 0.15)
    for k, dx in enumerate((-0.42, 0.42, -0.2, 0.2, 0.0)):  # lobes, outer first
        p.setBrush(radial(c.x() + dx * w - w * 0.1, c.y() - h * 0.2, w * 0.7, (0, rgb(250, 160, 60)), (0.6, ORANGE), (1, rgb(150, 60, 14))))
        p.drawEllipse(QPointF(c.x() + dx * w, c.y()), w * 0.34, h / 2)
    p.setBrush(rgb(90, 80, 40))
    p.drawRoundedRect(QRectF(c.x() - 3 * s, c.y() - h / 2 - 9 * s, 6 * s, 11 * s), 2, 2)
    if carved:  # the face, dark until lit (the glow is drawn per frame)
        p.setBrush(rgb(40, 18, 8))
        for path in _face(c, w, h):
            p.drawPath(path)


def _face(c: QPointF, w: float, h: float) -> list[QPainterPath]:
    paths = []
    for side in (-1, 1):
        eye = QPainterPath()
        eye.addPolygon(poly((c.x() + side * w * 0.16, c.y() - h * 0.02), (c.x() + side * w * 0.34, c.y() - h * 0.02),
                            (c.x() + side * w * 0.25, c.y() - h * 0.24)))
        paths.append(eye)
    mouth = QPainterPath()
    pts = [(c.x() - w * 0.34, c.y() + h * 0.08)]
    for k in range(7):
        x = c.x() - w * 0.34 + w * 0.68 * (k + 0.5) / 7
        pts.append((x, c.y() + h * (0.2 if k % 2 == 0 else 0.12)))
    pts += [(c.x() + w * 0.34, c.y() + h * 0.08), (c.x() + w * 0.2, c.y() + h * 0.3), (c.x() - w * 0.2, c.y() + h * 0.3)]
    mouth.addPolygon(poly(*pts))
    paths.append(mouth)
    return paths


def _pumpkin_glow(p: QPainter, base: QPointF, s: float, t: float) -> None:
    w, h = 46 * s, 36 * s
    c = QPointF(base.x(), base.y() - h / 2)
    f = 0.8 + 0.2 * wobble(t * 2 + base.x(), 7.1, 11.3, 3.3)
    p.setBrush(radial(c.x(), c.y(), w * 1.8, (0, alpha(GLOW, 90 * f)), (1, alpha(GLOW, 0))))
    p.drawEllipse(c, w * 1.8, w * 1.8)
    p.setBrush(rgb(255, 210 * f, 90 * f))
    for path in _face(c, w, h):
        p.drawPath(path)


def _bat_shape(p: QPainter, x: float, y: float, span: float, flap: float, colour: QColor) -> None:
    """A bat silhouette; flap 0..1 raises the wings."""
    lift = (flap - 0.5) * span * 0.5
    path = QPainterPath()
    path.moveTo(x, y)
    for side in (1, -1):
        path.lineTo(x + side * span * 0.15, y - span * 0.1)
        path.quadTo(x + side * span * 0.35, y - span * 0.25 - lift, x + side * span * 0.5, y - span * 0.12 - lift)
        path.lineTo(x + side * span * 0.42, y + span * 0.02 - lift * 0.4)
        path.lineTo(x + side * span * 0.34, y - span * 0.04 - lift * 0.3)
        path.lineTo(x + side * span * 0.26, y + span * 0.06 - lift * 0.2)
        path.lineTo(x + side * span * 0.18, y)
        path.lineTo(x, y + span * 0.06)
        if side == 1:
            path.moveTo(x, y)
    p.setBrush(colour)
    p.drawPath(path)
    p.drawEllipse(QPointF(x, y - span * 0.04), span * 0.06, span * 0.09)


def _cobweb(p: QPainter, corner: QPointF, size: float) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(rgb(235, 235, 240, 120), 0.8))
    angles = [math.radians(a) for a in (2, 22, 45, 68, 88)]
    for a in angles:
        p.drawLine(corner, QPointF(corner.x() + math.cos(a) * size, corner.y() + math.sin(a) * size))
    for k in range(1, 6):
        r = size * k / 6
        path = QPainterPath()
        for i, a in enumerate(angles):
            pt = QPointF(corner.x() + math.cos(a) * r, corner.y() + math.sin(a) * r)
            if i == 0:
                path.moveTo(pt)
            else:
                prev = angles[i - 1]
                mid = (a + prev) / 2
                path.quadTo(QPointF(corner.x() + math.cos(mid) * r * 0.88, corner.y() + math.sin(mid) * r * 0.88), pt)
        p.drawPath(path)
    p.setPen(Qt.NoPen)


def _spider(p: QPainter, t: float) -> None:
    """A spider bobbing on its thread below the web."""
    x = WEB.x() + 40
    y = WEB.y() + 150 + 30 * math.sin(t * 0.9) + 6 * math.sin(t * 2.3)
    p.save()
    p.translate(x, y)
    p.scale(1.7, 1.7)
    p.translate(-x, -y)
    p.setPen(QPen(rgb(230, 230, 236, 140), 0.7))
    p.drawLine(QPointF(x, WEB.y() + 30), QPointF(x, y - 10))
    p.setPen(QPen(rgb(20, 18, 20), 1.4))
    for side in (-1, 1):
        for k in range(4):
            a = math.radians(-50 + k * 32)
            wig = 2 * math.sin(t * 6 + k)
            knee = QPointF(x + side * 8 * math.cos(a), y + 8 * math.sin(a) - 3)
            p.drawLine(QPointF(x, y), knee)
            p.drawLine(knee, QPointF(knee.x() + side * 5, knee.y() + 6 + wig))
    p.setPen(Qt.NoPen)
    p.setBrush(rgb(24, 20, 24))
    p.drawEllipse(QPointF(x, y + 3), 5.5, 6.5)
    p.drawEllipse(QPointF(x, y - 4), 3.5, 3.5)
    p.restore()


# --- Christmas


def _christmas_inside(p: QPainter, layer: str) -> None:
    if layer == "mantel":
        # a wreath on the chimney, above the painting
        _wreath(p, QPointF(688, 100), 44)
        # an evergreen garland along the mantel, with stockings below
        _garland(p, MANTEL_LEFT - 6, MANTEL_RIGHT + 6, MANTEL_TOP + 4, 30)
        for x, colour in ((588, rgb(176, 30, 36)), (718, rgb(30, 100, 60)), (848, rgb(176, 30, 36))):
            _stocking(p, x, MANTEL_BOTTOM + 2, colour)
    elif layer == "back":
        _tree(p)
        _presents(p)


def _wreath(p: QPainter, c: QPointF, r: float) -> None:
    rng = random.Random(5)
    p.setBrush(rgb(0, 0, 0, 80))
    p.drawEllipse(c + QPointF(4, 5), r + 6, r + 6)
    for i in range(90):
        a = rng.uniform(0, 2 * math.pi)
        rr = r + rng.uniform(-9, 9)
        pt = QPointF(c.x() + math.cos(a) * rr, c.y() + math.sin(a) * rr)
        p.setBrush(rgb(rng.randint(20, 50), rng.randint(70, 110), rng.randint(36, 56)))
        p.drawEllipse(pt, 7, 4)
    for i in range(10):  # berries
        a = i / 10 * 2 * math.pi + 0.3
        p.setBrush(rgb(200, 24, 30))
        p.drawEllipse(QPointF(c.x() + math.cos(a) * r, c.y() + math.sin(a) * r), 3.2, 3.2)
    _bow(p, QPointF(c.x(), c.y() + r + 2), 1.0)


def _bow(p: QPainter, c: QPointF, s: float) -> None:
    red, dark = rgb(206, 30, 40), rgb(130, 14, 20)
    for side in (-1, 1):
        loop = QPainterPath()
        loop.moveTo(c)
        loop.cubicTo(c.x() + side * 22 * s, c.y() - 16 * s, c.x() + side * 24 * s, c.y() + 10 * s, c.x(), c.y())
        p.setBrush(vgrad(c.y() - 14 * s, c.y() + 10 * s, red, dark))
        p.drawPath(loop)
        tail = poly((c.x(), c.y()), (c.x() + side * 8 * s, c.y() + 26 * s), (c.x() + side * 14 * s, c.y() + 22 * s))
        p.drawPolygon(tail)
    p.setBrush(dark)
    p.drawEllipse(c, 4.5 * s, 4.5 * s)


def _garland(p: QPainter, x0: float, x1: float, y: float, sag: float) -> None:
    rng = random.Random(8)
    for k in range(240):
        t = k / 239
        for loop in range(2):  # two shallow swags
            lt = (t * 2) - loop
            if not 0 <= lt <= 1:
                continue
            mid = x0 + (x1 - x0) * (loop + lt) / 2
            pt = QPointF(mid, y + sag * 4 * lt * (1 - lt))
            p.setBrush(rgb(rng.randint(16, 46), rng.randint(64, 104), rng.randint(32, 52)))
            p.drawEllipse(pt + QPointF(rng.uniform(-6, 6), rng.uniform(-5, 5)), 7, 3.5)
    for x in (x0 + 4, (x0 + x1) / 2, x1 - 4):  # pine cones and bows where it's hung
        p.setBrush(rgb(110, 70, 36))
        p.drawEllipse(QPointF(x, y + 8), 6, 9)
        _bow(p, QPointF(x, y - 2), 0.6)


def _garland_bulbs() -> list[tuple[QPointF, QColor, float]]:
    rng = random.Random(9)
    bulbs = []
    for k in range(36):
        t = (k + 0.5) / 36
        loop = 0 if t < 0.5 else 1
        lt = t * 2 - loop
        x = MANTEL_LEFT - 6 + (MANTEL_RIGHT - MANTEL_LEFT + 12) * t
        y = MANTEL_TOP + 4 + 30 * 4 * lt * (1 - lt) + rng.uniform(-3, 3)
        bulbs.append((QPointF(x, y), rgb(255, 214, 140), rng.uniform(0, 6.3)))
    return bulbs


def _mantel_lights(p: QPainter, t: float) -> None:
    for pt, colour, phase in _points("garland", _garland_bulbs):
        k = 0.65 + 0.35 * math.sin(t * 1.7 + phase)
        p.setBrush(radial(pt.x(), pt.y(), 10, (0, alpha(colour, 160 * k)), (1, alpha(colour, 0))))
        p.drawEllipse(pt, 10, 10)
        p.setBrush(alpha(mix(colour, rgb(255, 255, 255), 0.5), 255 * k))
        p.drawEllipse(pt, 2.2, 2.2)


def _stocking(p: QPainter, x: float, top: float, colour: QColor) -> None:
    sock = QPainterPath()
    sock.moveTo(x - 14, top + 10)
    sock.lineTo(x + 14, top + 10)
    sock.lineTo(x + 14, top + 56)
    sock.cubicTo(x + 14, top + 70, x + 4, top + 78, x - 14, top + 78)
    sock.cubicTo(x - 30, top + 78, x - 34, top + 64, x - 22, top + 58)
    sock.lineTo(x - 14, top + 52)
    sock.closeSubpath()
    p.setBrush(rgb(0, 0, 0, 70))
    p.drawPath(sock.translated(3, 3))
    p.setBrush(hgrad(x - 34, x + 14, scaled(colour, 0.7), colour, scaled(colour, 0.75)))
    p.drawPath(sock)
    p.setBrush(vgrad(top, top + 16, rgb(250, 248, 244), rgb(210, 206, 200)))
    p.drawRoundedRect(QRectF(x - 17, top, 34, 15), 5, 5)
    p.setPen(QPen(rgb(60, 50, 40), 1))
    p.drawLine(QPointF(x, top - 6), QPointF(x, top))
    p.setPen(Qt.NoPen)


def _tree(p: QPainter) -> None:
    x, base = TREE.x(), TREE.y()
    p.setBrush(radial(x, base, 200, (0, rgb(0, 0, 0, 90)), (1, rgb(0, 0, 0, 0))))
    p.drawEllipse(QPointF(x, base), 190, 24)
    draw_pine(p, x, base, TREE_H, TREE_W, rgb(30, 86, 50), seed=77)
    rng = random.Random(41)
    # gold tinsel, spiralling down
    p.setBrush(Qt.NoBrush)
    for k in range(4):
        y0 = base - TREE_H * (0.82 - k * 0.19)
        half = TREE_W / 2 * (0.25 + k * 0.19)
        path = QPainterPath(QPointF(x - half, y0))
        path.quadTo(QPointF(x, y0 + 34), QPointF(x + half * 1.05, y0 + 22))
        p.setPen(QPen(rgb(230, 190, 90, 220), 3.2, Qt.DotLine, Qt.RoundCap))
        p.drawPath(path)
    p.setPen(Qt.NoPen)
    # baubles
    colours = (rgb(200, 30, 40), rgb(220, 180, 70), rgb(40, 90, 170), rgb(230, 230, 236), rgb(150, 40, 120))
    for i in range(30):
        fy = rng.uniform(0.12, 0.86)
        y = base - TREE_H * (1 - fy) + 10
        half = TREE_W / 2 * fy * 0.85
        bx = x + rng.uniform(-half, half)
        c = rng.choice(colours)
        r = rng.uniform(5, 8)
        p.setBrush(radial(bx - r * 0.4, y - r * 0.4, r * 1.6, (0, mix(c, rgb(255, 255, 255), 0.7)), (0.4, c), (1, scaled(c, 0.5))))
        p.drawEllipse(QPointF(bx, y), r, r)
    # the star on top
    top = QPointF(x, base - TREE_H - 4)
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = 20 if k % 2 == 0 else 8
        pts.append((top.x() + math.cos(a) * rr, top.y() + math.sin(a) * rr))
    p.setBrush(radial(top.x() - 4, top.y() - 4, 22, rgb(255, 246, 190), rgb(232, 180, 60)))
    p.drawPolygon(poly(*pts))


def _tree_bulbs() -> list[tuple[QPointF, QColor, float]]:
    rng = random.Random(42)
    colours = (rgb(255, 214, 140), rgb(255, 90, 80), rgb(110, 200, 255), rgb(130, 255, 140), rgb(255, 230, 110))
    bulbs = []
    for i in range(70):
        fy = rng.uniform(0.08, 0.9)
        y = TREE.y() - TREE_H * (1 - fy) + 8
        half = TREE_W / 2 * fy * 0.9
        bulbs.append((QPointF(TREE.x() + rng.uniform(-half, half), y), rng.choice(colours), rng.uniform(0, 6.3)))
    return bulbs


def _tree_lights(p: QPainter, t: float) -> None:
    for pt, colour, phase in _points("tree", _tree_bulbs):
        k = max(0.0, 0.55 + 0.45 * math.sin(t * 1.3 + phase))
        p.setBrush(radial(pt.x(), pt.y(), 12, (0, alpha(colour, 170 * k)), (1, alpha(colour, 0))))
        p.drawEllipse(pt, 12, 12)
        p.setBrush(alpha(mix(colour, rgb(255, 255, 255), 0.55), 120 + 135 * k))
        p.drawEllipse(pt, 2.4, 2.4)
    top = QPointF(TREE.x(), TREE.y() - TREE_H - 4)
    g = 0.8 + 0.2 * math.sin(t * 0.8)
    p.setBrush(radial(top.x(), top.y(), 50, (0, rgb(255, 240, 170, 150 * g)), (1, rgb(255, 220, 120, 0))))
    p.drawEllipse(top, 50, 50)


def _presents(p: QPainter) -> None:
    for x, w, h, box, ribbon in ((1088, 46, 34, rgb(176, 30, 36), rgb(236, 200, 90)),
                                 (1128, 34, 26, rgb(30, 90, 150), rgb(236, 236, 240)),
                                 (1098, 30, 22, rgb(40, 110, 60), rgb(200, 30, 40))):
        y = TREE.y() - 4 - h + (12 if w < 40 else 0)
        r = QRectF(x - w / 2, y, w, h)
        p.setBrush(vgrad(r.top(), r.bottom(), scaled(box, 1.2), scaled(box, 0.75)))
        p.drawRect(r)
        p.setBrush(ribbon)
        p.drawRect(QRectF(r.center().x() - 3, r.top(), 6, h))
        p.drawRect(QRectF(r.left(), r.center().y() - 3, w, 6))
        _bow(p, QPointF(r.center().x(), r.top()), 0.4)


# --- Easter


EASTER_COLOURS = (rgb(246, 180, 196), rgb(250, 226, 120), rgb(160, 206, 240), rgb(170, 220, 160), rgb(206, 180, 236))


def _egg(p: QPainter, c: QPointF, r: float, colour: QColor, seed: int, angle: float = 0.0) -> None:
    p.save()
    p.translate(c)
    p.rotate(angle)
    egg = QPainterPath()
    egg.addEllipse(QPointF(0, 0), r * 0.78, r)
    p.setBrush(radial(-r * 0.3, -r * 0.4, r * 1.6, (0, mix(colour, rgb(255, 255, 255), 0.6)), (0.5, colour), (1, scaled(colour, 0.7))))
    p.drawPath(egg)
    p.save()
    p.setClipPath(egg)
    stripe = scaled(EASTER_COLOURS[(seed + 2) % len(EASTER_COLOURS)], 0.9)
    p.setPen(QPen(stripe, r * 0.22))
    p.drawLine(QPointF(-r, -r * 0.15), QPointF(r, -r * 0.15))
    p.setPen(QPen(rgb(255, 255, 255, 200), r * 0.12, Qt.DotLine))
    p.drawLine(QPointF(-r, r * 0.25), QPointF(r, r * 0.25))
    p.restore()
    p.setPen(Qt.NoPen)
    p.restore()


def _easter_inside(p: QPainter, layer: str) -> None:
    if layer == "mantel":
        # pastel egg bunting along the mantel
        n = 14
        p.setPen(QPen(rgb(240, 236, 220), 1.2))
        p.drawLine(QPointF(MANTEL_LEFT + 6, MANTEL_BOTTOM - 2), QPointF(MANTEL_RIGHT - 6, MANTEL_BOTTOM - 2))
        p.setPen(Qt.NoPen)
        for i in range(n):
            pt = _sag(MANTEL_LEFT + 20, MANTEL_RIGHT - 20, MANTEL_BOTTOM + 8, 12, i / (n - 1))
            _egg(p, pt + QPointF(0, 8), 10, EASTER_COLOURS[i % len(EASTER_COLOURS)], i)
        # daffodils in the iron pot on the mantel
        rng = random.Random(4)
        for i in range(7):
            base = QPointF(511 + rng.uniform(-12, 12), 318)
            head = QPointF(base.x() + rng.uniform(-40, 40), base.y() - rng.uniform(60, 100))
            p.setPen(QPen(rgb(90, 130, 60), 2))
            p.drawLine(base, head)
            p.setPen(Qt.NoPen)
            _daffodil(p, head, 1.0, rng.uniform(-30, 30))
        # a bunny on the hearth
        _bunny(p, QPointF(512, HEARTH_TOP), 1.0)
    elif layer == "table":
        # a basket of painted eggs on the coffee table
        c = QPointF(790, 652)
        p.setBrush(vgrad(c.y() - 10, c.y() + 20, rgb(190, 150, 96), rgb(120, 84, 48)))
        p.drawChord(QRectF(c.x() - 48, c.y() - 26, 96, 52), 180 * 16, 180 * 16)
        rng = random.Random(6)
        for i in range(9):
            _egg(p, QPointF(c.x() - 36 + i * 9, c.y() - 4 - (i % 2) * 6), 9, EASTER_COLOURS[i % 5], i, rng.uniform(-30, 30))
        p.setBrush(vgrad(c.y(), c.y() + 26, rgb(176, 136, 84), rgb(110, 76, 42)))
        p.drawChord(QRectF(c.x() - 48, c.y() - 26, 96, 52), 180 * 16, 180 * 16)
        p.setPen(QPen(rgb(150, 110, 64), 3))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(c.x() - 40, c.y() - 60, 80, 76), 0, 180 * 16)
        p.setPen(Qt.NoPen)
        # tulips in the jug
        for i, dx in enumerate((-12, -2, 8, 16)):
            head = QPointF(886 + dx, 588 - (i % 2) * 12)
            p.setPen(QPen(rgb(80, 120, 56), 2))
            p.drawLine(QPointF(886, 628), head)
            p.setPen(Qt.NoPen)
            p.setBrush(radial(head.x() - 2, head.y() - 2, 9, rgb(250, 140, 170), rgb(200, 50, 90)))
            p.drawEllipse(head, 5.5, 8)


def _daffodil(p: QPainter, c: QPointF, s: float, angle: float) -> None:
    p.save()
    p.translate(c)
    p.rotate(angle)
    p.setBrush(rgb(250, 236, 140))
    for k in range(6):
        p.save()
        p.rotate(k * 60)
        p.drawEllipse(QPointF(0, -7 * s), 3.6 * s, 7 * s)
        p.restore()
    p.setBrush(radial(0, 0, 6 * s, rgb(255, 210, 60), rgb(240, 150, 30)))
    p.drawEllipse(QPointF(0, 0), 4.5 * s, 4.5 * s)
    p.restore()


def _bunny(p: QPainter, base: QPointF, s: float) -> None:
    fur, shade = rgb(236, 232, 226), rgb(190, 184, 176)
    c = QPointF(base.x(), base.y() - 18 * s)
    p.setBrush(rgb(0, 0, 0, 70))
    p.drawEllipse(QPointF(base.x() + 2, base.y()), 26 * s, 5 * s)
    p.setBrush(radial(c.x() - 6 * s, c.y() - 8 * s, 30 * s, fur, shade))
    p.drawEllipse(c, 20 * s, 18 * s)  # body
    p.drawEllipse(QPointF(c.x() + 14 * s, c.y() - 16 * s), 11 * s, 10 * s)  # head
    for dx, a in ((10, -12), (18, 10)):  # ears
        p.save()
        p.translate(c.x() + dx * s, c.y() - 26 * s)
        p.rotate(a)
        p.setBrush(fur)
        p.drawEllipse(QPointF(0, -12 * s), 4 * s, 13 * s)
        p.setBrush(rgb(240, 190, 196))
        p.drawEllipse(QPointF(0, -12 * s), 2 * s, 9 * s)
        p.restore()
    p.setBrush(rgb(255, 255, 255))
    p.drawEllipse(QPointF(c.x() - 20 * s, c.y() + 2 * s), 6 * s, 6 * s)  # tail
    p.setBrush(rgb(40, 30, 30))
    p.drawEllipse(QPointF(c.x() + 18 * s, c.y() - 18 * s), 1.6 * s, 1.6 * s)
    p.setBrush(rgb(230, 140, 150))
    p.drawEllipse(QPointF(c.x() + 24 * s, c.y() - 15 * s), 1.8 * s, 1.4 * s)


# --- New Year


def _new_year_inside(p: QPainter, layer: str) -> None:
    if layer == "mantel":
        # "HAPPY NEW YEAR" on gold-lettered pennants across the chimney
        text = "HAPPY NEW YEAR"
        x0, x1, y = 482.0, 990.0, 122.0
        p.setPen(QPen(rgb(230, 200, 120), 1.2))
        path = QPainterPath(QPointF(x0, y))
        path.quadTo(QPointF((x0 + x1) / 2, y + 40), QPointF(x1, y))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        font = QFont("serif")
        font.setPixelSize(17)
        font.setBold(True)
        p.setFont(font)
        n = len(text)
        for i, ch in enumerate(text):
            t = (i + 0.5) / n
            pt = QPointF(x0 + (x1 - x0) * t, y + 80 * t * (1 - t))  # on the string's curve
            if ch == " ":
                continue
            flag = poly((pt.x() - 15, pt.y()), (pt.x() + 15, pt.y()), (pt.x() + 15, pt.y() + 30), (pt.x(), pt.y() + 40), (pt.x() - 15, pt.y() + 30))
            p.setBrush(vgrad(pt.y(), pt.y() + 40, rgb(30, 34, 60), rgb(16, 18, 34)))
            p.drawPolygon(flag)
            p.setPen(QPen(rgb(220, 180, 80), 1))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(flag)
            p.setPen(rgb(244, 206, 110))
            p.drawText(QRectF(pt.x() - 15, pt.y() + 3, 30, 26), Qt.AlignCenter, ch)
            p.setPen(Qt.NoPen)
        # streamers hanging from the tie beam
        rng = random.Random(3)
        for i in range(9):
            x = 430 + i * 130 + rng.uniform(-20, 20)
            colour = rng.choice((rgb(230, 190, 80), rgb(200, 200, 210), rgb(40, 50, 90)))
            path = QPainterPath(QPointF(x, 112))
            length = rng.uniform(80, 160)
            for k in range(1, 9):
                path.lineTo(x + (6 if k % 2 else -6), 112 + length * k / 8)
            p.setPen(QPen(colour, 3))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.setPen(Qt.NoPen)
    elif layer == "table":
        # champagne and two flutes on the coffee table
        b = QPointF(808, 664)
        bottle = QPainterPath()
        bottle.moveTo(b.x() - 13, b.y())
        bottle.lineTo(b.x() - 13, b.y() - 50)
        bottle.cubicTo(b.x() - 13, b.y() - 64, b.x() - 5, b.y() - 66, b.x() - 5, b.y() - 78)
        bottle.lineTo(b.x() - 5, b.y() - 96)
        bottle.lineTo(b.x() + 5, b.y() - 96)
        bottle.lineTo(b.x() + 5, b.y() - 78)
        bottle.cubicTo(b.x() + 5, b.y() - 66, b.x() + 13, b.y() - 64, b.x() + 13, b.y() - 50)
        bottle.lineTo(b.x() + 13, b.y())
        bottle.closeSubpath()
        p.setBrush(hgrad(b.x() - 13, b.x() + 13, rgb(20, 50, 30), rgb(60, 110, 70), rgb(16, 40, 24)))
        p.drawPath(bottle)
        p.setBrush(vgrad(b.y() - 96, b.y() - 72, rgb(240, 210, 120), rgb(170, 130, 50)))
        p.drawRect(QRectF(b.x() - 6, b.y() - 98, 12, 26))
        p.setBrush(rgb(236, 230, 210))
        p.drawRect(QRectF(b.x() - 13, b.y() - 40, 26, 18))
        for gx in (744, 764):
            p.setPen(QPen(rgb(230, 236, 240, 200), 1.4))
            p.drawLine(QPointF(gx, b.y()), QPointF(gx, b.y() - 18))
            p.drawLine(QPointF(gx - 7, b.y()), QPointF(gx + 7, b.y()))
            p.setPen(Qt.NoPen)
            p.setBrush(vgrad(b.y() - 46, b.y() - 18, rgb(250, 226, 150, 220), rgb(230, 190, 90, 220)))
            p.drawPolygon(poly((gx - 6, b.y() - 46), (gx + 6, b.y() - 46), (gx + 3, b.y() - 18), (gx - 3, b.y() - 18)))
        # confetti on the table and rug
        rng = random.Random(12)
        for _ in range(140):
            x, y = rng.uniform(560, 1200), rng.uniform(644, 880)
            p.setBrush(rng.choice((rgb(240, 200, 80), rgb(220, 220, 230), rgb(220, 80, 90), rgb(90, 140, 220))))
            p.drawRect(QRectF(x, y, rng.uniform(2, 5), rng.uniform(2, 4)))


def _balloons(p: QPainter, t: float) -> None:
    colours = (rgb(232, 196, 90), rgb(214, 216, 224), rgb(30, 34, 50), rgb(232, 196, 90), rgb(214, 216, 224))
    anchor = QPointF(1036, 470)
    for i, (dx, dy) in enumerate(((-30, -260), (8, -290), (40, -250), (-6, -228), (26, -210))):
        bob = 5 * math.sin(t * 0.7 + i * 1.3)
        c = QPointF(anchor.x() + dx + 3 * math.sin(t * 0.5 + i), anchor.y() + dy + bob)
        p.setPen(QPen(rgb(230, 230, 230, 150), 0.8))
        p.drawLine(QPointF(c.x(), c.y() + 26), anchor)
        p.setPen(Qt.NoPen)
        col = colours[i]
        p.setBrush(radial(c.x() - 8, c.y() - 10, 34, (0, mix(col, rgb(255, 255, 255), 0.6)), (0.45, col), (1, scaled(col, 0.6))))
        p.drawEllipse(c, 20, 25)
        p.drawPolygon(poly((c.x() - 3, c.y() + 26), (c.x() + 3, c.y() + 26), (c.x(), c.y() + 22)))


# --- shared


def _bunting(p: QPainter, x0: float, x1: float, y: float, sag: float, size: float, colours: list, triangles: bool) -> None:
    p.setPen(QPen(rgb(60, 50, 40), 1))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(x0, y))
    path.quadTo(QPointF((x0 + x1) / 2, y + sag * 2), QPointF(x1, y))
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    n = int((x1 - x0) / (size * 1.25))
    for i in range(n):
        t = (i + 0.5) / n
        pt = _sag(x0, x1, y, sag, t)
        p.setBrush(colours[i % len(colours)])
        p.drawPolygon(poly((pt.x() - size / 2, pt.y()), (pt.x() + size / 2, pt.y()), (pt.x(), pt.y() + size * 1.1)))


# ======================================================================
# outside (the lodge's coordinates: see lodge.py)


def outside_static(p: QPainter, kind: Optional[str], lit) -> None:
    if kind is None:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    if kind == HALLOWEEN:
        for c, s in PUMPKINS_OUTSIDE:
            _pumpkin(p, c, s, carved=s > 0.6)
    elif kind == CHRISTMAS:
        _wreath(p, QPointF(304, 462), 22)
    elif kind == EASTER:
        rng = random.Random(14)
        for i in range(16):
            _egg(p, QPointF(rng.uniform(40, 1360), rng.uniform(640, 700)), 7, EASTER_COLOURS[i % 5], i, rng.uniform(-40, 40))
        for i in range(14):
            x = 120 + i * 76 + rng.uniform(-14, 14)
            for k in range(3):
                head = QPointF(x + k * 8 - 8, 600 - rng.uniform(10, 26))
                p.setPen(QPen(rgb(90, 130, 60), 1.6))
                p.drawLine(QPointF(x, 612), head)
                p.setPen(Qt.NoPen)
                _daffodil(p, head, 0.7, rng.uniform(-30, 30))
    p.restore()


def _roof_bulbs() -> list[tuple[QPointF, QColor, float]]:
    from simple_cabin.gui.scenes import lodge

    rng = random.Random(21)
    colours = (rgb(255, 80, 70), rgb(80, 220, 110), rgb(90, 160, 255), rgb(255, 210, 90), rgb(255, 140, 220))
    runs = [(lodge.EAVE_L, lodge.APEX), (lodge.APEX, lodge.EAVE_R), (lodge.WING_L, lodge.WING_APEX), (lodge.WING_APEX, lodge.WING_R),
            (QPointF(92, lodge.PORCH_FASCIA_Y + 10), QPointF(556, lodge.PORCH_FASCIA_Y + 10)),
            (QPointF(1012, 426), QPointF(1174, 426))]
    bulbs = []
    for a, b in runs:
        n = int(math.hypot(b.x() - a.x(), b.y() - a.y()) / 16)
        for k in range(n + 1):
            t = k / max(1, n)
            pt = QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t + 3 + 3 * math.sin(t * math.pi * n / 2))
            bulbs.append((pt, colours[(k + len(bulbs)) % len(colours)], rng.uniform(0, 6.3)))
    return bulbs


def outside_dynamic(p: QPainter, kind: Optional[str], t: float, glow: float) -> None:
    """glow: how dark it is (0 by day .. 1 at night), for how much lights show."""
    if kind is None:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    if kind == HALLOWEEN:
        for c, s in PUMPKINS_OUTSIDE:
            if s > 0.6:
                _pumpkin_glow(p, c, s, t)
        for i in range(5):  # bats
            a = t * (0.35 + i * 0.07) + i * 1.9
            x = 700 + math.sin(a) * (420 + i * 60) + math.sin(a * 2.3) * 60
            y = 160 + i * 34 + math.sin(a * 1.7) * 50
            _bat_shape(p, x, y, 30 - i * 3, 0.5 + 0.5 * math.sin(t * (14 + i)), rgb(18, 14, 18))
    elif kind == CHRISTMAS:
        strength = 0.35 + 0.65 * glow
        for pt, colour, phase in _points("roof", _roof_bulbs):
            k = max(0.2, 0.6 + 0.4 * math.sin(t * 1.5 + phase))
            p.setBrush(radial(pt.x(), pt.y(), 11, (0, alpha(colour, 170 * k * strength)), (1, alpha(colour, 0))))
            p.drawEllipse(pt, 11, 11)
            p.setBrush(alpha(mix(colour, rgb(255, 255, 255), 0.4), 255 * (0.4 + 0.6 * k)))
            p.drawEllipse(pt, 2.2, 2.2)
    p.restore()


# ======================================================================
# fireworks


class Fireworks:
    """Rockets rising from the far shore and bursting over the lake."""

    COLOURS = (rgb(255, 90, 80), rgb(255, 210, 90), rgb(120, 200, 255), rgb(150, 255, 140), rgb(255, 140, 230), rgb(255, 255, 255))

    def __init__(self):
        self._rng = random.Random(77)
        self._rockets: list[list] = []  # x, y, vx, vy, colour, burst height
        self._sparks: list[list] = []  # x, y, vx, vy, age, life, colour
        self._next = 0.5
        self._flashes: list[list] = []  # x, y, age, colour

    def step(self, dt: float, active: bool) -> int:
        """Returns how many rockets burst this step (for a bang)."""
        rng = self._rng
        bursts = 0
        if active:
            self._next -= dt
            if self._next <= 0:
                self._next = rng.uniform(0.5, 2.2)
                # far across the lake, low over the far shore: the one stretch
                # of open sky between the pines and the hills
                x = rng.uniform(1320, 1530)
                self._rockets.append([x, 600.0, rng.uniform(-8, 8), rng.uniform(-260, -200), rng.choice(self.COLOURS), rng.uniform(410, 470)])
        for r in self._rockets:
            r[0] += r[2] * dt
            r[1] += r[3] * dt
            r[3] += 120 * dt
        still = []
        for r in self._rockets:
            if r[1] <= r[5] or r[3] > -40:
                bursts += 1
                self._flashes.append([r[0], r[1], 0.0, r[4]])
                n = rng.randint(70, 110)
                speed = rng.uniform(55, 85)
                second = rng.choice(self.COLOURS) if rng.random() < 0.4 else r[4]
                for k in range(n):
                    a = k / n * 2 * math.pi + rng.uniform(-0.05, 0.05)
                    v = speed * rng.uniform(0.75, 1.0)
                    self._sparks.append([r[0], r[1], math.cos(a) * v, math.sin(a) * v, 0.0, rng.uniform(1.2, 2.0), r[4] if k % 3 else second])
            else:
                still.append(r)
        self._rockets = still
        for s in self._sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[2] *= 1 - 1.4 * dt
            s[3] = s[3] * (1 - 1.4 * dt) + 30 * dt
            s[4] += dt
        self._sparks = [s for s in self._sparks if s[4] < s[5]]
        for f in self._flashes:
            f[2] += dt
        self._flashes = [f for f in self._flashes if f[2] < 0.35]
        return bursts

    @property
    def visible(self) -> bool:
        return bool(self._rockets or self._sparks)

    def paint(self, p: QPainter, reflection_line: Optional[float] = None) -> None:
        """Draw in the sky; with reflection_line, draw the mirror image below it, dimmer."""
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if reflection_line is not None:
            p.translate(0, reflection_line)
            p.scale(1, -0.55)
            p.translate(0, -reflection_line)
            p.setOpacity(0.4)
        p.setPen(Qt.NoPen)
        for x, y, vx, vy, colour, _ in self._rockets:
            p.setPen(QPen(rgb(255, 220, 160, 200), 1.6))
            p.drawLine(QPointF(x, y), QPointF(x - vx * 0.04, y - vy * 0.04))
            p.setPen(Qt.NoPen)
        for burst in self._flashes:  # a flash of light as each one bursts
            x, y, age, colour = burst
            k = max(0.0, 1 - age / 0.35)
            p.setBrush(radial(x, y, 70, (0, alpha(mix(colour, rgb(255, 255, 255), 0.5), 150 * k)), (1, alpha(colour, 0))))
            p.drawEllipse(QPointF(x, y), 70, 70)
        for x, y, vx, vy, age, life, colour in self._sparks:
            k = 1 - age / life
            flicker = 0.7 + 0.3 * math.sin(age * 40 + x)
            p.setPen(QPen(alpha(colour, 230 * k * flicker), 2.2))
            p.drawLine(QPointF(x, y), QPointF(x - vx * 0.08, y - vy * 0.08))
            p.setPen(QPen(alpha(mix(colour, rgb(255, 255, 255), 0.6), 255 * k * flicker), 2.6, Qt.SolidLine, Qt.RoundCap))
            p.drawPoint(QPointF(x, y))
        p.setPen(Qt.NoPen)
        p.restore()
