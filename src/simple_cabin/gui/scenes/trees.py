"""Tall lakeside pines, boulders and ferns for the outside view."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from simple_cabin.gui import textures as tx
from simple_cabin.gui.paint import hgrad, radial, rgb, scaled


def tint(p: QPainter, shape, colour: QColor) -> None:
    """Multiply an already-drawn area by a light colour (for textures,
    which are drawn in daylight colours)."""
    p.save()
    p.setCompositionMode(QPainter.CompositionMode_Multiply)
    if isinstance(shape, QRectF):
        p.fillRect(shape, colour)
    else:
        p.fillPath(shape, colour)
    p.restore()


def draw_ponderosa(p: QPainter, x: float, base: float, height: float, trunk_w: float, seed: int,
                   crown: QColor, light: QColor, detail: bool = True, crown_frac: float = 0.5,
                   spread: float = 1.0, snow: bool = False, trunk_colour: QColor | None = None) -> None:
    """A tall pine: a long straight trunk, bare below, with clumps of
    needles on short branches in its upper part. light is the colour the
    scene's light multiplies daylight colours by (see tint)."""
    rng = random.Random(seed)
    top = base - height
    p.setPen(Qt.NoPen)

    # trunk, tapering
    trunk = QPainterPath()
    trunk.moveTo(x - trunk_w / 2, base + 4)
    trunk.lineTo(x - trunk_w * 0.18, top + 10)
    trunk.lineTo(x + trunk_w * 0.18, top + 10)
    trunk.lineTo(x + trunk_w / 2, base + 4)
    trunk.closeSubpath()
    if detail:
        tex = tx.bark(max(8, int(trunk_w) + 4), int(height) + 8, 5 + seed % 3)
        tx.draw_textured(p, trunk, tex)
        tint(p, trunk, light)
        r = trunk.boundingRect()
        p.save()
        p.setClipPath(trunk)
        p.fillRect(r, hgrad(r.left(), r.right(), (0, rgb(0, 0, 0, 120)), (0.35, rgb(0, 0, 0, 0)), (0.7, rgb(0, 0, 0, 40)), (1, rgb(0, 0, 0, 150))))
        p.restore()
    else:
        p.setBrush(trunk_colour or scaled(crown, 0.8))
        p.drawPath(trunk)

    # branches and clumps of needles, denser and wider lower down the crown
    crown_len = height * crown_frac
    n = max(4, int(crown_len / (22 if detail else 26)))
    dark, mid = scaled(crown, 0.7), crown
    hi = QColor(min(255, int(crown.red() * 1.45 + 6)), min(255, int(crown.green() * 1.35 + 8)), min(255, int(crown.blue() * 1.2 + 4)))
    # one brush for every clump, in the clump's own unit space (see _tuft)
    shaded = QBrush(radial(-0.2, -0.6, 1.3, (0, hi), (0.5, mid), (1, dark)))
    clusters = []
    for i in range(n + 1):
        f = i / n  # 0 at the top
        y = top + f * crown_len + rng.uniform(-8, 8)
        reach = (10 + 80 * f ** 0.8) * spread * rng.uniform(0.6, 1.1)
        for side in ((-1, 1) if rng.random() < 0.55 else (rng.choice((-1, 1)),)):
            cx = x + side * reach
            cy = y + reach * 0.12
            clusters.append((cx, cy, (18 + 26 * f ** 0.6) * spread * rng.uniform(0.75, 1.15), side, y))
            if rng.random() < 0.6:  # a second clump part-way along the branch
                clusters.append((x + side * reach * 0.5, cy - 4, (14 + 18 * f ** 0.6) * spread, side, y))
        if rng.random() < 0.7:
            clusters.append((x + rng.uniform(-6, 6), y, (14 + 18 * f) * spread, 0, y))
    # branches first (behind the needles)
    if detail:
        p.setPen(QPen(scaled(trunk_colour or rgb(60, 40, 28), 1.0), 2.2))
        for cx, cy, size, side, y in clusters:
            if side:
                p.drawLine(QPointF(x, y), QPointF(cx - side * size * 0.3, cy))
        p.setPen(Qt.NoPen)
    for cx, cy, size, side, _ in clusters:
        tufts = 5 if detail else 3
        for k in range(tufts):
            tx_ = cx + rng.uniform(-size * 0.7, size * 0.7)
            ty_ = cy + rng.uniform(-size * 0.35, size * 0.25)
            rx, ry = size * rng.uniform(0.5, 0.8), size * rng.uniform(0.28, 0.42)
            _tuft(p, tx_, ty_, rx, ry, rng.randrange(len(_TUFTS)), shaded if detail else (mid if k else dark))
            if snow and rng.random() < 0.45:
                p.setBrush(QColor(light.red() * 236 // 255, light.green() * 240 // 255, light.blue() * 246 // 255, 190))
                p.drawEllipse(QPointF(tx_ + rx * 0.1, ty_ - ry * 0.55), rx * 0.55, ry * 0.28)


def _make_tufts(count: int = 16) -> list[QPainterPath]:
    """A few ragged clumps of needles (ellipses with spiky edges) in unit
    size, made once: the forest has thousands of clumps, and building each
    outline afresh in Python was most of the time it took to draw."""
    shapes = []
    for k in range(count):
        rng = random.Random(900 + k)
        path = QPainterPath()
        spikes = 14
        for i in range(spikes * 2):
            a = i / (spikes * 2) * 2 * math.pi
            r = 1.0 if i % 2 == 0 else rng.uniform(0.7, 0.85)
            pt = QPointF(math.cos(a) * r, math.sin(a) * r * (1.15 if math.sin(a) > 0 else 1.0))
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        path.closeSubpath()
        shapes.append(path)
    return shapes


_TUFTS = _make_tufts()


def _tuft(p: QPainter, cx: float, cy: float, rx: float, ry: float, variant: int, brush) -> None:
    """One clump of needles, centred on (cx, cy) with radii rx, ry."""
    p.save()
    p.translate(cx, cy)
    p.scale(rx, ry)
    p.setBrush(brush)
    p.drawPath(_TUFTS[variant])
    p.restore()


def draw_boulder(p: QPainter, cx: float, cy: float, rx: float, ry: float, seed: int, light: QColor, mossy: bool = False) -> None:
    """A rounded granite boulder, lit from above."""
    rng = random.Random(seed)
    path = QPainterPath()
    pts = []
    for k in range(12):
        a = k / 12 * 2 * math.pi
        r = rng.uniform(0.86, 1.0)
        flat = 0.7 if math.sin(a) > 0.3 else 1.0  # flatter underneath
        pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r * flat))
    path.moveTo((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    for i in range(1, 13):
        x1, y1 = pts[i % 12]
        x2, y2 = pts[(i + 1) % 12]
        path.quadTo(x1, y1, (x1 + x2) / 2, (y1 + y2) / 2)
    path.closeSubpath()
    base = rng.uniform(118, 150)
    stone = QColor(int(base), int(base * 0.98), int(base * 0.94))
    p.setPen(Qt.NoPen)
    p.setBrush(rgb(0, 0, 0, 70))
    p.drawEllipse(QPointF(cx + rx * 0.1, cy + ry * 0.55), rx * 1.05, ry * 0.3)
    p.setBrush(radial(cx - rx * 0.35, cy - ry * 0.5, max(rx, ry) * 1.5, (0, stone.lighter(130)), (0.45, stone), (1, stone.darker(220))))
    p.drawPath(path)
    p.save()
    p.setClipPath(path)
    # speckles of feldspar and lichen
    for _ in range(int(rx * ry / 40)):
        sx, sy = cx + rng.uniform(-rx, rx), cy + rng.uniform(-ry, ry)
        p.setBrush(rgb(255, 255, 255, 30) if rng.random() < 0.5 else rgb(20, 20, 20, 40))
        p.drawEllipse(QPointF(sx, sy), rng.uniform(0.8, 2.2), rng.uniform(0.8, 1.8))
    if mossy:
        p.setBrush(radial(cx - rx * 0.2, cy - ry * 0.7, rx, (0, rgb(110, 130, 60, 170)), (1, rgb(110, 130, 60, 0))))
        p.drawEllipse(QPointF(cx - rx * 0.2, cy - ry * 0.7), rx * 0.9, ry * 0.5)
    p.restore()
    tint(p, path, light)


def draw_fern(p: QPainter, x: float, y: float, size: float, seed: int, colour: QColor) -> None:
    """A clump of fern fronds arching out from a point."""
    rng = random.Random(seed)
    for _ in range(rng.randint(5, 8)):
        a = math.radians(rng.uniform(-80, 80))
        length = size * rng.uniform(0.6, 1.0)
        curl = rng.uniform(0.25, 0.5) * (1 if a > 0 else -1)
        shade = scaled(colour, rng.uniform(0.75, 1.25))
        pts = []
        for k in range(9):
            t = k / 8
            ang = a + curl * t * 1.6
            pts.append(QPointF(x + math.sin(ang) * length * t, y - math.cos(ang) * length * t + length * 0.35 * t * t))
        p.setPen(QPen(scaled(shade, 0.7), 1.2))
        for k in range(1, 9):
            p.drawLine(pts[k - 1], pts[k])
        p.setPen(QPen(shade, 2.2, Qt.SolidLine, Qt.RoundCap))
        for k in range(1, 8):
            leaf = size * 0.18 * (1 - k / 9)
            dx, dy = pts[k].x() - pts[k - 1].x(), pts[k].y() - pts[k - 1].y()
            n = math.hypot(dx, dy) or 1
            nx, ny = -dy / n, dx / n
            p.drawLine(pts[k], pts[k] + QPointF(nx * leaf + dx * 0.3, ny * leaf + dy * 0.3))
            p.drawLine(pts[k], pts[k] - QPointF(nx * leaf - dx * 0.3, ny * leaf - dy * 0.3))
    p.setPen(Qt.NoPen)


def draw_shrub(p: QPainter, x: float, y: float, w: float, h: float, seed: int, colour: QColor) -> None:
    """A low, leafy shrub: lots of small overlapping leaf blobs."""
    rng = random.Random(seed)
    p.setPen(Qt.NoPen)
    for i in range(int(w * h / 50)):
        lx = x + rng.uniform(-w / 2, w / 2)
        ly = y - rng.uniform(0, h) * (1 - (2 * (lx - x) / w) ** 2 * 0.6)
        p.setBrush(scaled(colour, rng.uniform(0.65, 1.3)))
        p.drawEllipse(QPointF(lx, ly), rng.uniform(2.5, 5), rng.uniform(1.8, 3.5))
