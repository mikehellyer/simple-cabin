"""The painting above the mantel: two people paddling a red canoe down a
river through spruce forest, mountains and a golden evening sky behind.

Painted once into an image (with brush-stroke and canvas texture on top)
and then hung in the room like any other picture.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from simple_cabin.gui import textures as tx
from simple_cabin.gui.paint import alpha, mix, poly, radial, rgb, scaled, vgrad

PW, PH = 600, 450  # the painting's own canvas


@lru_cache(maxsize=1)
def canoe_painting() -> QImage:
    img = QImage(PW, PH, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    _sky(p)
    _mountains(p)
    _far_forest(p)
    _river(p)
    _banks(p)
    p.save()  # the canoe, a little larger than life, as painters do
    p.translate(318, 376)
    p.scale(1.35, 1.35)
    p.translate(-318, -372)
    _canoe(p)
    p.restore()
    p.end()
    return _painterly(img)


# --- the landscape


def _sky(p: QPainter) -> None:
    p.fillRect(QRectF(0, 0, PW, 260), vgrad(0, 230, (0, rgb(66, 84, 140)), (0.45, rgb(196, 140, 132)),
                                            (0.8, rgb(246, 186, 118)), (1, rgb(252, 214, 150))))
    sun = QPointF(432, 178)
    p.setBrush(radial(sun.x(), sun.y(), 170, (0, rgb(255, 236, 180, 230)), (0.2, rgb(255, 210, 140, 120)), (1, rgb(255, 190, 120, 0))))
    p.drawEllipse(sun, 170, 170)
    p.setBrush(rgb(255, 244, 210))
    p.drawEllipse(sun, 15, 15)
    # long streaks of evening cloud
    rng = random.Random(3)
    for i in range(9):
        y = rng.uniform(30, 150)
        x = rng.uniform(-60, PW - 100)
        w = rng.uniform(120, 300)
        lit = mix(rgb(250, 190, 170), rgb(150, 110, 140), y / 150)
        p.setBrush(alpha(lit, rng.uniform(90, 160)))
        p.drawEllipse(QRectF(x, y, w, rng.uniform(6, 14)))


def _ridge(p: QPainter, base: float, amp: float, seed: int, colour: QColor, spiky: bool = False) -> None:
    rng = random.Random(seed)
    path = QPainterPath()
    path.moveTo(-10, PH)
    x = -10.0
    phases = [rng.uniform(0, 6) for _ in range(3)]
    while x <= PW + 10:
        y = base - amp * (0.6 * math.sin(x * 0.011 + phases[0]) + 0.3 * math.sin(x * 0.027 + phases[1]) + 0.1 * math.sin(x * 0.07 + phases[2]))
        path.lineTo(x, y)
        if spiky:  # treetops
            path.lineTo(x + 3, y - rng.uniform(6, 14))
            x += 6
        else:
            x += 8
    path.lineTo(PW + 10, PH)
    path.closeSubpath()
    p.setBrush(colour)
    p.drawPath(path)


def _mountains(p: QPainter) -> None:
    _ridge(p, 182, 46, 11, rgb(150, 130, 160))
    # snow on the far peaks, catching the sun
    p.save()
    p.setClipRect(QRectF(0, 0, PW, 160))
    _ridge(p, 182, 46, 11, rgb(250, 222, 200))
    p.restore()
    _ridge(p, 206, 30, 13, rgb(112, 104, 136))


def _far_forest(p: QPainter) -> None:
    _ridge(p, 236, 14, 17, rgb(52, 70, 70), spiky=True)
    _ridge(p, 250, 8, 19, rgb(34, 50, 46), spiky=True)


def _river_path() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(318, 246)
    path.cubicTo(250, 268, 300, 300, 200, 330)
    path.cubicTo(110, 356, 60, 400, -10, PH)
    path.lineTo(PW + 10, PH)
    path.lineTo(PW + 10, 330)
    path.cubicTo(520, 300, 430, 280, 470, 262)
    path.cubicTo(500, 252, 440, 244, 400, 244)
    path.closeSubpath()
    return path


def _river(p: QPainter) -> None:
    river = _river_path()
    p.fillRect(QRectF(0, 240, PW, PH - 240), rgb(40, 56, 52))
    p.save()
    p.setClipPath(river)
    # the sky mirrored, darkening towards us
    p.fillRect(QRectF(0, 240, PW, PH - 240), vgrad(244, PH, (0, rgb(250, 206, 146)), (0.35, rgb(214, 150, 122)),
                                                   (0.75, rgb(92, 102, 132)), (1, rgb(52, 64, 96))))
    # the sun's path on the water: a soft, tall glow
    p.save()
    p.translate(432, 300)
    p.scale(0.45, 1.0)
    p.setBrush(radial(0, 0, 150, (0, rgb(255, 232, 176, 190)), (0.5, rgb(255, 214, 150, 70)), (1, rgb(255, 210, 140, 0))))
    p.drawEllipse(QPointF(0, 0), 150, 150)
    p.restore()
    # dark reflections of the forest along both banks
    p.setBrush(alpha(rgb(30, 44, 40), 170))
    p.drawRect(QRectF(0, 244, PW, 16))
    rng = random.Random(23)
    for _ in range(220):  # glints and ripples
        y = rng.uniform(250, PH)
        depth = (y - 250) / (PH - 250)
        x = rng.uniform(0, PW)
        length = rng.uniform(4, 22) * (0.4 + depth * 1.6)
        light = rng.random() < 0.5
        near_sun = abs(x - 432) < 60
        a = rng.uniform(30, 80) + (60 if near_sun and light else 0)
        p.setPen(QPen(alpha(rgb(255, 232, 190) if light else rgb(30, 40, 60), a), 1 + depth * 1.2))
        p.drawLine(QPointF(x, y), QPointF(x + length, y))
    p.setPen(Qt.NoPen)
    p.restore()


def _spruce(p: QPainter, x: float, base: float, h: float, w: float, colour: QColor, rng: random.Random) -> None:
    """A narrow northern spruce, as a ragged spire."""
    path = QPainterPath()
    path.moveTo(x, base - h)
    steps = max(6, int(h / 9))
    for side in (1, -1):
        pts = []
        for i in range(1, steps + 1):
            t = i / steps
            reach = w / 2 * t * rng.uniform(0.75, 1.15)
            y = base - h + h * 0.92 * t
            pts.append(QPointF(x + side * reach, y))
            pts.append(QPointF(x + side * reach * 0.35, y + h / steps * 0.25))
        if side == -1:
            pts.reverse()
        for pt in pts:
            path.lineTo(pt)
        if side == 1:
            path.lineTo(x + w * 0.05, base)
            path.lineTo(x - w * 0.05, base)
    path.closeSubpath()
    p.setBrush(colour)
    p.drawPath(path)


def _banks(p: QPainter) -> None:
    rng = random.Random(31)
    # right bank: rocks and a stand of spruce, catching the low sun
    right = QPainterPath()
    right.moveTo(PW + 10, 330)
    right.cubicTo(520, 300, 430, 280, 470, 262)
    right.cubicTo(500, 252, 440, 244, 400, 244)
    right.lineTo(PW + 10, 236)
    right.closeSubpath()
    p.setBrush(vgrad(240, 330, rgb(88, 92, 60), rgb(52, 56, 40)))
    p.drawPath(right)
    for i in range(12):
        x = 430 + i * 15 + rng.uniform(-5, 5)
        h = rng.uniform(70, 150) * (0.7 + i / 20)
        _spruce(p, x, 262 + i * 5, h, h * 0.28, mix(rgb(30, 50, 40), rgb(70, 76, 50), rng.random() * 0.4), rng)
    # left bank, nearer: a rocky point with tall spruce
    left = QPainterPath()
    left.moveTo(-10, 238)
    left.lineTo(318, 246)
    left.cubicTo(250, 268, 300, 300, 200, 330)
    left.cubicTo(110, 356, 60, 400, -10, PH)
    left.closeSubpath()
    p.setBrush(vgrad(238, PH, rgb(70, 74, 50), rgb(36, 40, 30)))
    p.drawPath(left)
    for i in range(16):
        x = -10 + i * 20 + rng.uniform(-6, 6)
        base = 250 + max(0, (140 - x)) * 0.9 + rng.uniform(0, 10)
        h = rng.uniform(90, 200) * (1.3 if x < 90 else 0.9)
        _spruce(p, x, base, h, h * 0.27, mix(rgb(26, 44, 34), rgb(60, 70, 46), rng.random() * 0.35), rng)
    # boulders at the water's edge, warm on top
    for x, y, r in ((214, 330, 14), (186, 340, 10), (120, 368, 18), (82, 392, 12), (470, 266, 9), (500, 280, 11), (548, 300, 13)):
        p.setBrush(radial(x - r * 0.4, y - r * 0.6, r * 1.6, (0, rgb(214, 180, 150)), (0.5, rgb(130, 116, 104)), (1, rgb(60, 54, 50))))
        p.drawEllipse(QPointF(x, y), r, r * 0.62)


# --- the canoe and its paddlers


def _canoe(p: QPainter) -> None:
    cx, cy = 318.0, 372.0  # waterline centre of the canoe
    length = 196.0
    hull_red, hull_dark = rgb(196, 52, 38), rgb(110, 26, 22)

    def hull_path(flip: float = 1.0) -> QPainterPath:
        """The hull seen side-on: a long, shallow crescent with raised ends."""
        l, r = cx - length / 2, cx + length / 2
        path = QPainterPath()
        path.moveTo(l, cy - 22 * flip)  # bow tip (heading left)
        path.cubicTo(l + 20, cy - 6 * flip, l + 60, cy - 8 * flip, cx, cy - 8 * flip)  # gunwale
        path.cubicTo(r - 60, cy - 8 * flip, r - 20, cy - 6 * flip, r, cy - 20 * flip)
        path.cubicTo(r - 6, cy + 2 * flip, r - 40, cy + 9 * flip, cx, cy + 10 * flip)  # keel line
        path.cubicTo(l + 40, cy + 9 * flip, l + 6, cy + 2 * flip, l, cy - 22 * flip)
        path.closeSubpath()
        return path

    # reflection first, broken up by ripples
    p.save()
    p.setOpacity(0.45)
    p.setBrush(scaled(hull_red, 0.7))
    p.drawPath(hull_path(-1).translated(0, 18))
    p.restore()
    p.setPen(QPen(rgb(255, 230, 190, 120), 1.2))
    for k in range(6):
        y = cy + 14 + k * 5
        p.drawLine(QPointF(cx - length * 0.4 + k * 6, y), QPointF(cx + length * 0.4 - k * 4, y))
    # the wake: a gentle V opening out behind the stern, fading as it goes
    p.setBrush(Qt.NoBrush)
    stern = QPointF(cx + length / 2 - 8, cy + 3)
    for spread, a in ((1.0, 120), (1.6, 60)):
        for sign in (-1, 1):
            arm = QPainterPath(stern)
            arm.quadTo(stern.x() + 70, stern.y() + sign * 4 * spread, stern.x() + 150, stern.y() + sign * 16 * spread)
            p.setPen(QPen(rgb(255, 236, 200, a), 1.3))
            p.drawPath(arm)
    p.setPen(Qt.NoPen)

    # the hull
    hull = hull_path()
    p.setBrush(vgrad(cy - 22, cy + 10, (0, rgb(236, 92, 66)), (0.5, hull_red), (1, hull_dark)))
    p.drawPath(hull)
    # cedar gunwale and the inside of the far side, just visible
    gunwale = QPainterPath(QPointF(cx - length / 2, cy - 22))
    gunwale.cubicTo(cx - length / 2 + 20, cy - 6, cx - length / 2 + 60, cy - 8, cx, cy - 8)
    gunwale.cubicTo(cx + length / 2 - 60, cy - 8, cx + length / 2 - 20, cy - 6, cx + length / 2, cy - 20)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(rgb(214, 160, 96), 2.6))
    p.drawPath(gunwale)
    p.setPen(QPen(rgb(255, 210, 170, 140), 1))
    p.drawPath(gunwale.translated(0, 3))
    p.setPen(Qt.NoPen)
    # waterline shadow
    p.setBrush(alpha(rgb(20, 20, 30), 90))
    p.drawEllipse(QRectF(cx - length * 0.42, cy + 4, length * 0.84, 7))

    # the paddlers: the bow paddler on the left, the stern paddler on the right
    _paddler(p, cx - 56, cy - 9, 0.9, rgb(46, 74, 110), rgb(150, 40, 34), stern=False)
    _paddler(p, cx + 52, cy - 9, 1.0, rgb(166, 46, 36), rgb(70, 54, 36), stern=True)


def _paddler(p: QPainter, x: float, seat_y: float, s: float, shirt: QColor, hat: QColor, stern: bool) -> None:
    """A seated paddler facing left, mid-stroke on the near side."""
    skin = rgb(226, 170, 130)
    # torso, leaning into the stroke
    torso = QPainterPath()
    torso.moveTo(x - 9 * s, seat_y)
    torso.cubicTo(x - 12 * s, seat_y - 14 * s, x - 10 * s, seat_y - 24 * s, x - 3 * s, seat_y - 27 * s)
    torso.lineTo(x + 7 * s, seat_y - 25 * s)
    torso.cubicTo(x + 11 * s, seat_y - 16 * s, x + 10 * s, seat_y - 6 * s, x + 9 * s, seat_y)
    torso.closeSubpath()
    p.setBrush(vgrad(seat_y - 27 * s, seat_y, scaled(shirt, 1.25), scaled(shirt, 0.75)))
    p.drawPath(torso)
    if stern:  # a plaid shirt: a few dark checks
        p.save()
        p.setClipPath(torso)
        p.setPen(QPen(rgb(40, 20, 20, 140), 1.4))
        for k in range(5):
            y = seat_y - 26 * s + k * 6 * s
            p.drawLine(QPointF(x - 14 * s, y), QPointF(x + 12 * s, y))
            xx = x - 10 * s + k * 5 * s
            p.drawLine(QPointF(xx, seat_y - 30 * s), QPointF(xx, seat_y))
        p.restore()
    # head and hat
    head = QPointF(x - 1 * s, seat_y - 33 * s)
    p.setPen(Qt.NoPen)
    p.setBrush(skin)
    p.drawEllipse(head, 5.2 * s, 6 * s)
    p.setBrush(hat)
    if stern:  # a felt bush hat
        p.drawEllipse(QRectF(head.x() - 9 * s, head.y() - 6 * s, 18 * s, 4 * s))
        p.drawRoundedRect(QRectF(head.x() - 5 * s, head.y() - 11 * s, 10 * s, 7 * s), 3 * s, 3 * s)
    else:  # a knitted toque
        p.drawChord(QRectF(head.x() - 6 * s, head.y() - 10 * s, 12 * s, 12 * s), 0, 180 * 16)
        p.setBrush(rgb(240, 230, 210))
        p.drawEllipse(QPointF(head.x(), head.y() - 10 * s), 2 * s, 2 * s)
    # the paddle: top hand up by the shoulder, blade in the water ahead and below
    top = QPointF(x + 2 * s, seat_y - 34 * s)
    blade_tip = QPointF(x - 30 * s, seat_y + 18 * s)
    p.setPen(QPen(rgb(200, 150, 90), 2.2 * s, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(top, blade_tip)
    p.setPen(Qt.NoPen)
    # the blade, half under the water
    dx, dy = blade_tip.x() - top.x(), blade_tip.y() - top.y()
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    mid = QPointF(blade_tip.x() - ux * 9 * s, blade_tip.y() - uy * 9 * s)
    blade = QPainterPath()
    blade.addEllipse(mid, 3.5 * s, 10 * s)
    p.save()
    p.translate(mid)
    p.rotate(math.degrees(math.atan2(uy, ux)) - 90)
    p.translate(-mid)
    p.setBrush(rgb(206, 156, 96))
    p.drawEllipse(mid, 3.5 * s, 10 * s)
    p.restore()
    p.setBrush(alpha(rgb(60, 80, 110), 150))  # water over the lower blade
    p.drawRect(QRectF(mid.x() - 8 * s, seat_y + 12 * s, 16 * s, 14 * s))
    # splash and ripples where it enters
    p.setPen(QPen(rgb(255, 240, 210, 200), 1.2))
    p.drawArc(QRectF(mid.x() - 10 * s, seat_y + 9 * s, 20 * s, 6 * s), 0, 180 * 16)
    p.drawArc(QRectF(mid.x() - 16 * s, seat_y + 10 * s, 32 * s, 9 * s), 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    # arms: one to the top of the shaft, one down the shaft
    p.setPen(QPen(scaled(shirt, 0.9), 4 * s, Qt.SolidLine, Qt.RoundCap))
    shoulder = QPointF(x - 2 * s, seat_y - 22 * s)
    lower = QPointF(top.x() + ux * n * 0.42, top.y() + uy * n * 0.42)
    p.drawLine(shoulder, top + QPointF(0, 2 * s))
    p.drawLine(shoulder, lower)
    p.setPen(Qt.NoPen)
    p.setBrush(skin)
    p.drawEllipse(top + QPointF(0, 1.5 * s), 2.2 * s, 2.2 * s)
    p.drawEllipse(lower, 2.2 * s, 2.2 * s)


# --- making it look painted


def _painterly(img: QImage) -> QImage:
    """Brush strokes, canvas weave and a little varnish warmth."""
    arr = tx.from_qimage(img)[..., :3]
    h, w = arr.shape[:2]
    strokes = tx.fbm(h, w, 3, 14, 7, 3)  # short horizontal dabs
    dabs = tx.fbm(h, w, 9, 9, 8, 2)
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    weave = np.sin(xs * 1.9) * np.sin(ys * 1.9)
    shade = 0.9 + 0.16 * (strokes - 0.5) * 2 * 0.6 + 0.08 * (dabs - 0.5) + 0.025 * weave
    arr = arr * shade[..., None]
    # soften slightly, as paint would (a small box blur)
    soft = (arr + np.roll(arr, 1, 0) + np.roll(arr, -1, 0) + np.roll(arr, 1, 1) + np.roll(arr, -1, 1)) / 5
    arr = arr * 0.55 + soft * 0.45
    # aged varnish: warm the whole thing a touch and darken the corners
    arr[..., 0] *= 1.03
    arr[..., 2] *= 0.94
    d = np.sqrt(((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2)
    arr *= (1 - 0.22 * np.clip(d - 0.55, 0, 1))[..., None]
    return tx.to_qimage(arr)
