"""Small painting helpers shared by the scenes."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF, QRadialGradient

# Every scene is drawn on this virtual canvas and scaled to the window.
W, H = 1600.0, 900.0


def rgb(r, g, b, a=255) -> QColor:
    return QColor(int(r), int(g), int(b), int(a))


def mix(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
        int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


def scaled(c: QColor, f: float) -> QColor:
    return QColor(
        min(255, int(c.red() * f)), min(255, int(c.green() * f)), min(255, int(c.blue() * f)), c.alpha()
    )


def alpha(c: QColor, a: float) -> QColor:
    out = QColor(c)
    out.setAlpha(max(0, min(255, int(a))))
    return out


def vgrad(y0: float, y1: float, *stops) -> QLinearGradient:
    """A vertical gradient; stops are (position, QColor) or just colours."""
    g = QLinearGradient(0, y0, 0, y1)
    _stops(g, stops)
    return g


def hgrad(x0: float, x1: float, *stops) -> QLinearGradient:
    g = QLinearGradient(x0, 0, x1, 0)
    _stops(g, stops)
    return g


def _stops(g, stops) -> None:
    if stops and isinstance(stops[0], QColor):
        n = len(stops)
        for i, c in enumerate(stops):
            g.setColorAt(i / (n - 1), c)
    else:
        for pos, c in stops:
            g.setColorAt(pos, c)


def radial(cx: float, cy: float, r: float, *stops) -> QRadialGradient:
    g = QRadialGradient(cx, cy, r)
    _stops(g, stops)
    return g


def poly(*points) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points])


def soft_blob(size: int, color: QColor) -> QImage:
    """A round, soft-edged sprite (clouds, smoke, fog)."""
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r = size / 2
    p.setPen(Qt.NoPen)
    p.setBrush(radial(r, r, r, (0.0, color), (0.55, alpha(color, color.alpha() * 0.6)), (1.0, alpha(color, 0))))
    p.drawEllipse(QRectF(0, 0, size, size))
    p.end()
    return img


def pine_path(x: float, base: float, height: float, width: float, rng: random.Random, tiers: int = 0) -> list[QPainterPath]:
    """A conifer as a stack of ragged tiers, bottom first, with the trunk
    foot at (x, base). Returns one path per tier."""
    tiers = tiers or max(4, min(9, int(height / 40)))
    crown = height * 0.88
    paths = []
    for i in range(tiers):
        f = i / tiers  # 0 for the bottom tier
        bottom = base - height * 0.12 - crown * 0.82 * f
        top = base - height if i == tiers - 1 else bottom - crown * 0.36
        half = width / 2 * (1 - 0.8 * f) * rng.uniform(0.92, 1.05)
        jag = 4

        def edge(side: int) -> list[tuple[float, float]]:
            pts = []
            for j in range(1, jag + 1):
                t = j / jag
                if j > 1:
                    tn = t - 0.5 / jag
                    pts.append((x + side * half * tn * 0.72, top + (bottom - top) * tn + rng.uniform(0, 3)))
                pts.append((x + side * half * t * rng.uniform(0.94, 1.04), top + (bottom - top) * t))
            return pts

        path = QPainterPath()
        path.moveTo(x, top)
        for px, py in edge(1):
            path.lineTo(px, py)
        left = edge(-1)
        path.quadTo(x, bottom + height * 0.035, left[-1][0], left[-1][1])
        for px, py in reversed(left[:-1]):
            path.lineTo(px, py)
        path.closeSubpath()
        paths.append(path)
    return paths


def draw_pine(p: QPainter, x, base, height, width, color: QColor, seed: int, snow: bool = False, trunk: QColor | None = None):
    rng = random.Random(seed)
    trunk = trunk or scaled(color, 0.55)
    p.setPen(Qt.NoPen)
    p.setBrush(trunk)
    tw = max(2.0, width * 0.08)
    p.drawRect(QRectF(x - tw / 2, base - height * 0.2, tw, height * 0.2))
    tiers = pine_path(x, base, height, width, rng)
    for i, path in enumerate(tiers):
        r = path.boundingRect()
        light = scaled(color, 1.25)
        dark = scaled(color, 0.78)
        g = hgrad(r.left(), r.right(), (0.0, light), (0.45, color), (1.0, dark))
        p.setBrush(g)
        p.drawPath(path)
        if snow:
            p.setBrush(rgb(240, 244, 250, 225))
            cap = QPainterPath()
            cx, top = r.center().x(), r.top()
            hw = r.width() / 2
            cap.moveTo(cx, top)
            cap.lineTo(cx + hw * 0.55, top + r.height() * 0.5)
            for k in range(5, -6, -1):
                cap.lineTo(cx + hw * 0.55 * k / 5, top + r.height() * (0.42 + 0.1 * (k % 2)))
            cap.closeSubpath()
            p.drawPath(cap)


def wobble(t: float, *freqs: float) -> float:
    """A smooth pseudo-random wiggle in -1..1 from a few sines."""
    return sum(math.sin(t * f + i * 1.7) for i, f in enumerate(freqs)) / max(1, len(freqs))
