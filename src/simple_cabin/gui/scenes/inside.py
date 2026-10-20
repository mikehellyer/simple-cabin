"""Inside the cabin: log walls, the grandfather clock, a roaring stone
fireplace, an armchair, and a window looking out over the lake.

Everything is lit by an overlay: daylight from the window during the
day, then firelight, an oil lamp and candles as it gets dark.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from simple_cabin.gui.paint import H, W, alpha, hgrad, mix, poly, radial, rgb, scaled, vgrad, wobble
from simple_cabin.gui.scenes import clock
from simple_cabin.gui.scenes.fire import Fire
from simple_cabin.gui.scenes.outside import WINDOW_VIEW, OutsideScene

GLASS = QRectF(590, 160, 340, 310)
FIREBOX_LEFT, FIREBOX_RIGHT, FIREBOX_TOP, FIREBOX_BOTTOM = 1120.0, 1380.0, 470.0, 690.0
LAMP_FLAME = QPointF(535, 596)
CANDLES = (QPointF(1062, 352), QPointF(1440, 352))
FLOOR_Y = 700.0


def fit_scale(target: QRectF, width: float = W, height: float = H) -> float:
    """Fill the target, but never crop away more than an eighth of the
    scene's width (on squarer windows the top and bottom extend instead)."""
    s = max(target.width() / width, target.height() / height)
    return min(s, target.width() / (width * 0.875))


def firebox_path() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(FIREBOX_LEFT, FIREBOX_BOTTOM)
    path.lineTo(FIREBOX_LEFT, 530)
    path.quadTo((FIREBOX_LEFT + FIREBOX_RIGHT) / 2, FIREBOX_TOP - 22, FIREBOX_RIGHT, 530)
    path.lineTo(FIREBOX_RIGHT, FIREBOX_BOTTOM)
    path.closeSubpath()
    return path


class InsideScene:
    def __init__(self, outside: OutsideScene):
        self.outside = outside
        self.fire = Fire((FIREBOX_LEFT + FIREBOX_RIGHT) / 2, FIREBOX_BOTTOM - 22, 230)
        self.t = 0.0
        self._cache_key = None
        self._cache: QImage | None = None
        self._drops: list[list[float]] = []
        self._rng = random.Random(4)

    def step(self, dt: float) -> None:
        self.t += dt
        self.fire.step(dt)
        self.outside.fire_glow = self.fire.flicker()
        self._step_drops(dt)

    def _step_drops(self, dt: float) -> None:
        rain = self.outside.weather.rain
        want = int(rain * 70)
        rng = self._rng
        while len(self._drops) < want:
            # x, y, radius, speed (0 = clinging), age
            self._drops.append([rng.uniform(GLASS.left(), GLASS.right()), rng.uniform(GLASS.top(), GLASS.bottom()),
                                rng.uniform(1.5, 4), 0.0, 0.0])
        del self._drops[want:]
        for d in self._drops:
            d[4] += dt
            if d[3] == 0 and d[2] > 3.2 and rng.random() < dt * 0.4:
                d[3] = rng.uniform(25, 70)  # heavy enough to run
            d[1] += d[3] * dt
            if d[1] > GLASS.bottom() + 5 or d[4] > 25:
                d[:] = [rng.uniform(GLASS.left(), GLASS.right()), rng.uniform(GLASS.top(), GLASS.bottom()), rng.uniform(1.5, 4), 0.0, 0.0]

    # --- painting

    def paint(self, p: QPainter, target: QRectF, now: datetime, now_seconds: float) -> None:
        s = fit_scale(target)
        ox = target.x() + (target.width() - W * s) / 2
        oy = target.y() + (target.height() - H * s) / 2

        def to_scene() -> None:
            p.translate(ox, oy)
            p.scale(s, s)

        p.save()
        p.setClipRect(target)
        # 1. the view through the window
        glass_device = QRectF(ox + GLASS.x() * s, oy + GLASS.y() * s, GLASS.width() * s, GLASS.height() * s)
        p.fillRect(glass_device, rgb(0, 0, 0))
        self.outside.paint(p, glass_device, WINDOW_VIEW, cabin=False)

        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_glass(p)
        p.restore()

        # 2. the room (cached), with a hole where the glass is
        dpr = p.device().devicePixelRatioF() if p.device() else 1.0
        key = (int(target.width()), int(target.height()), dpr, round(self.outside.moon_phase, 3),
               self.outside.weather.snow_on_ground)
        if key != self._cache_key:
            self._cache_key = key
            self._cache = self._render_room(target, s, ox - target.x(), oy - target.y(), dpr)
        p.drawImage(target.topLeft(), self._cache)

        # 3. things that move
        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        p.save()
        p.setClipPath(firebox_path())
        self.fire.paint(p)
        p.restore()
        self._paint_small_flames(p)
        clock.paint_moving(p, now, now_seconds, glow=self.fire.flicker() * (1 - self.outside.light.daylight * 0.8))
        p.restore()

        # 4. light and shade
        self._paint_lighting(p, target, s, ox, oy)
        p.restore()

    def _render_room(self, target: QRectF, s: float, ox: float, oy: float, dpr: float) -> QImage:
        img = QImage(int(target.width() * dpr), int(target.height() * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(ox, oy)
        p.scale(s, s)
        self._paint_walls(p)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(GLASS, Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_window_frame(p)
        self._paint_fireplace(p)
        self._paint_rug(p)
        self._paint_chair(p)
        self._paint_lamp_table(p)
        self._paint_log_basket(p)
        clock.paint_case(p, self.outside.moon_phase)
        p.end()
        return img

    def _paint_walls(self, p: QPainter) -> None:
        rng = random.Random(21)
        p.setPen(Qt.NoPen)
        # Log wall (extended well past the canvas for squarer windows)
        p.fillRect(QRectF(-200, -400, W + 400, FLOOR_Y + 400), rgb(206, 186, 146))
        y = 40.0
        while y < FLOOR_Y:
            h = 46.0
            r = QRectF(-200, y + 2, W + 400, h - 4)
            p.setBrush(vgrad(r.top(), r.bottom(), (0, rgb(176, 116, 66)), (0.3, rgb(160, 102, 56)), (0.75, rgb(130, 80, 44)), (1, rgb(92, 56, 30))))
            p.drawRect(r)
            p.setPen(QPen(rgb(120, 76, 42, 120), 1))
            for _ in range(5):
                gx = rng.uniform(-100, W + 100)
                gy = rng.uniform(r.top() + 8, r.bottom() - 8)
                p.drawLine(QPointF(gx, gy), QPointF(gx + rng.uniform(80, 260), gy + rng.uniform(-1, 1)))
            p.setPen(Qt.NoPen)
            for _ in range(3):
                kx = rng.uniform(0, W)
                p.setBrush(rgb(96, 58, 30, 200))
                p.drawEllipse(QPointF(kx, r.center().y() + rng.uniform(-8, 8)), rng.uniform(4, 8), rng.uniform(3, 5))
            y += h
        # Ceiling beam
        p.fillRect(QRectF(-200, -400, W + 400, 440), vgrad(-400, 40, rgb(60, 38, 24), rgb(84, 52, 32)))
        p.fillRect(QRectF(-200, 34, W + 400, 8), rgb(50, 30, 18))
        # Antlers above the window
        p.setPen(QPen(rgb(226, 210, 180), 4, Qt.SolidLine, Qt.RoundCap))
        for side in (-1, 1):
            base = QPointF(760 + side * 10, 112)
            path = QPainterPath(base)
            path.cubicTo(760 + side * 40, 100, 760 + side * 70, 80, 760 + side * 80, 50)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            for k, (tx, ty) in enumerate(((36, 92), (56, 76), (68, 62))):
                p.drawLine(QPointF(760 + side * tx, ty), QPointF(760 + side * (tx - 6 + k * 3), ty - 22))
        p.setPen(Qt.NoPen)
        p.setBrush(vgrad(100, 130, rgb(120, 76, 42), rgb(80, 48, 26)))
        p.drawEllipse(QPointF(760, 118), 24, 16)

        # Floor in perspective
        p.fillRect(QRectF(-200, FLOOR_Y, W + 400, 700), vgrad(FLOOR_Y, H, rgb(96, 60, 34), rgb(140, 92, 54)))
        vx, vy = 800.0, 420.0
        p.setPen(QPen(rgb(70, 42, 24), 1.6))
        bottom = H + 400
        k = (bottom - vy) / (FLOOR_Y - vy)
        for i in range(-30, 31):
            x = vx + i * 46
            p.drawLine(QPointF(x, FLOOR_Y), QPointF(vx + (x - vx) * k, bottom))
        # Board ends, staggered row by row
        p.setPen(QPen(rgb(70, 42, 24, 110), 1))
        for j, yy in enumerate((716, 738, 768, 806, 852, 910)):
            k2 = (yy - vy) / (FLOOR_Y - vy)
            for i in range(-30 + j % 3, 30, 3):
                p.drawLine(QPointF(vx + i * 46 * k2, yy), QPointF(vx + (i + 1) * 46 * k2, yy))
        p.setPen(Qt.NoPen)
        # Skirting board
        p.fillRect(QRectF(-200, FLOOR_Y - 12, W + 400, 14), vgrad(FLOOR_Y - 12, FLOOR_Y + 2, rgb(100, 62, 34), rgb(60, 36, 20)))

    def _paint_window_frame(self, p: QPainter) -> None:
        wood = rgb(112, 70, 40)
        p.setPen(Qt.NoPen)
        frame = QPainterPath()
        frame.addRect(GLASS.adjusted(-16, -16, 16, 16))
        frame.addRect(GLASS)
        p.setBrush(vgrad(GLASS.top() - 16, GLASS.bottom() + 16, scaled(wood, 1.2), wood, scaled(wood, 0.8)))
        p.drawPath(frame)
        # glazing bars
        p.setBrush(scaled(wood, 0.95))
        p.drawRect(QRectF(GLASS.center().x() - 5, GLASS.top(), 10, GLASS.height()))
        p.drawRect(QRectF(GLASS.left(), GLASS.center().y() - 5, GLASS.width(), 10))
        # sill, with a little potted fern
        p.setBrush(vgrad(GLASS.bottom() + 8, GLASS.bottom() + 30, scaled(wood, 1.3), scaled(wood, 0.75)))
        p.drawRect(QRectF(GLASS.left() - 30, GLASS.bottom() + 10, GLASS.width() + 60, 20))
        p.setBrush(vgrad(440, 482, rgb(176, 90, 56), rgb(130, 60, 36)))
        p.drawPolygon(poly((618, 446), (662, 446), (656, 480), (624, 480)))
        p.setPen(QPen(rgb(60, 120, 60), 3, Qt.SolidLine, Qt.RoundCap))
        for a in range(-60, 61, 20):
            r = math.radians(a)
            p.drawLine(QPointF(640, 446), QPointF(640 + math.sin(r) * 34, 446 - math.cos(r) * 30))
        p.setPen(Qt.NoPen)

        # Curtains, on a brass rod
        p.setBrush(vgrad(132, 140, rgb(220, 180, 90), rgb(150, 110, 40)))
        p.drawRect(QRectF(530, 132, 460, 7))
        for x0, x1, tie in ((532, 616, 586), (904, 988, 934)):
            path = QPainterPath()
            path.moveTo(x0, 138)
            path.lineTo(x1, 138)
            path.cubicTo(x1 - 10, 300, tie + 4, 330, x1 - 6, 560)
            path.lineTo(x0, 560)
            path.closeSubpath()
            g = hgrad(x0, x1, *[(i / 8, rgb(150, 36, 32) if i % 2 else rgb(110, 24, 22)) for i in range(9)])
            p.setBrush(g)
            p.drawPath(path)
            # tartan stripes
            p.save()
            p.setClipPath(path)
            p.setPen(QPen(rgb(30, 70, 40, 120), 4))
            for y in range(150, 560, 38):
                p.drawLine(QPointF(x0, y), QPointF(x1, y))
            p.setPen(QPen(rgb(230, 200, 120, 90), 1))
            for y in range(160, 560, 38):
                p.drawLine(QPointF(x0, y), QPointF(x1, y))
            p.restore()
            p.setBrush(rgb(200, 160, 70))
            p.drawRoundedRect(QRectF(min(x0, x1) + 6, 318, x1 - x0 - 12, 9), 4, 4)

    def _paint_fireplace(self, p: QPainter) -> None:
        rng = random.Random(77)
        left, right = 1030.0, 1470.0
        p.setPen(Qt.NoPen)
        p.fillRect(QRectF(left, 40, right - left, FLOOR_Y - 40), rgb(64, 58, 54))
        y = 42.0
        while y < FLOOR_Y:
            h = rng.uniform(32, 44)
            x = left + rng.uniform(-30, 0)
            while x < right:
                w = rng.uniform(46, 90)
                base = rng.randint(118, 160)
                tint = rgb(base + rng.randint(-6, 14), base - rng.randint(0, 12), base - rng.randint(6, 24))
                r = QRectF(max(left, x) + 2, y + 2, min(right, x + w) - max(left, x) - 4, h - 4)
                if r.width() > 6:
                    p.setBrush(vgrad(r.top(), r.bottom(), scaled(tint, 1.12), tint, scaled(tint, 0.72)))
                    p.drawRoundedRect(r, 9, 9)
                x += w
            y += h
        # Firebox opening, with an arch of lighter stones
        p.setPen(QPen(rgb(150, 138, 122), 26))
        p.setBrush(Qt.NoBrush)
        p.drawPath(firebox_path())
        p.setPen(QPen(rgb(80, 72, 64), 2))
        for i in range(11):
            t = i / 10
            # points along the arch (the quad curve) and its sides
            ax = (1 - t) ** 2 * FIREBOX_LEFT + 2 * (1 - t) * t * 1250 + t ** 2 * FIREBOX_RIGHT
            ay = (1 - t) ** 2 * 530 + 2 * (1 - t) * t * (FIREBOX_TOP - 22) + t ** 2 * 530
            nx, ny = ax - 1250, ay - 620
            n = math.hypot(nx, ny)
            p.drawLine(QPointF(ax - nx / n * 13, ay - ny / n * 13), QPointF(ax + nx / n * 13, ay + ny / n * 13))
        p.setPen(Qt.NoPen)
        p.setBrush(vgrad(FIREBOX_TOP, FIREBOX_BOTTOM, rgb(18, 10, 8), rgb(36, 20, 12), rgb(60, 30, 16)))
        p.drawPath(firebox_path())
        # firebricks at the back
        p.save()
        p.setClipPath(firebox_path())
        p.setPen(QPen(rgb(10, 6, 4, 140), 1.2))
        for row, yy in enumerate(range(480, 690, 18)):
            p.drawLine(QPointF(FIREBOX_LEFT, yy), QPointF(FIREBOX_RIGHT, yy))
            for xx in range(int(FIREBOX_LEFT) + (20 if row % 2 else 0), int(FIREBOX_RIGHT), 40):
                p.drawLine(QPointF(xx, yy), QPointF(xx, yy + 18))
        p.restore()
        p.setPen(Qt.NoPen)

        # Hearth
        p.setBrush(vgrad(FIREBOX_BOTTOM - 4, FIREBOX_BOTTOM + 34, rgb(170, 158, 144), rgb(110, 100, 90)))
        p.drawRect(QRectF(990, FIREBOX_BOTTOM - 4, 520, 26))
        p.setBrush(rgb(80, 72, 64))
        p.drawRect(QRectF(990, FIREBOX_BOTTOM + 22, 520, 10))
        # Fire irons
        p.setBrush(rgb(40, 36, 34))
        p.drawRect(QRectF(1002, 560, 5, 128))
        p.drawEllipse(QPointF(1004.5, 556), 7, 7)
        p.drawRect(QRectF(994, 684, 22, 5))
        p.setPen(QPen(rgb(40, 36, 34), 3))
        p.drawLine(QPointF(1012, 600), QPointF(1014, 676))
        p.drawLine(QPointF(996, 590), QPointF(992, 670))
        p.setPen(Qt.NoPen)

        # Mantel beam with corbels
        wood = rgb(110, 66, 36)
        for x in (1012, 1462):
            p.setBrush(vgrad(430, 480, scaled(wood, 0.9), scaled(wood, 0.6)))
            p.drawPolygon(poly((x, 430), (x + 26, 430), (x + 26, 446), (x + 13, 482), (x, 482)))
        p.setBrush(vgrad(400, 438, scaled(wood, 1.3), wood, scaled(wood, 0.7)))
        p.drawRect(QRectF(996, 402, 508, 34))
        p.setPen(QPen(alpha(scaled(wood, 0.6), 160), 1))
        for yy in (410, 418, 427):
            p.drawLine(QPointF(1000, yy), QPointF(1500, yy + rng.uniform(-1, 1)))
        p.setPen(Qt.NoPen)

        # Painting of the lake above the mantel
        frame = QRectF(1158, 186, 184, 150)
        p.setBrush(vgrad(frame.top(), frame.bottom(), rgb(196, 150, 70), rgb(120, 84, 30)))
        p.drawRect(frame)
        pic = frame.adjusted(14, 14, -14, -14)
        p.setBrush(vgrad(pic.top(), pic.bottom(), rgb(250, 190, 120), rgb(240, 140, 90), rgb(110, 90, 120)))
        p.drawRect(pic)
        p.setBrush(rgb(255, 230, 160))
        p.drawEllipse(QPointF(pic.center().x() + 20, pic.top() + 52), 12, 12)
        p.setBrush(rgb(80, 70, 100))
        p.drawPolygon(poly((pic.left(), pic.top() + 78), (pic.left() + 50, pic.top() + 40), (pic.left() + 95, pic.top() + 70),
                           (pic.left() + 130, pic.top() + 46), (pic.right(), pic.top() + 74), (pic.right(), pic.top() + 80), (pic.left(), pic.top() + 80)))
        p.setBrush(vgrad(pic.top() + 80, pic.bottom(), rgb(200, 130, 100), rgb(60, 60, 90)))
        p.drawRect(QRectF(pic.left(), pic.top() + 80, pic.width(), pic.height() - 80))
        p.setBrush(rgb(30, 40, 36))
        for i in range(7):
            tx = pic.left() + 8 + i * 9
            p.drawPolygon(poly((tx - 5, pic.top() + 82), (tx, pic.top() + 58 - (i % 3) * 6), (tx + 5, pic.top() + 82)))

        # Things on the mantel: candlesticks, a stoneware jug, some books
        for c in CANDLES:
            p.setBrush(vgrad(c.y() + 30, c.y() + 50, rgb(220, 180, 90), rgb(140, 100, 40)))
            p.drawPolygon(poly((c.x() - 14, 402), (c.x() + 14, 402), (c.x() + 5, 392), (c.x() + 4, 376), (c.x() - 4, 376), (c.x() - 5, 392)))
            p.drawEllipse(QPointF(c.x(), 376), 9, 3)
            p.setBrush(hgrad(c.x() - 6, c.x() + 6, rgb(250, 244, 226), rgb(236, 226, 200), rgb(206, 194, 168)))
            p.drawRect(QRectF(c.x() - 5, c.y() + 6, 10, 370 - c.y() - 6 + 6))
            p.setPen(QPen(rgb(40, 30, 20), 1.2))
            p.drawLine(QPointF(c.x(), c.y() + 6), QPointF(c.x(), c.y() + 1))
            p.setPen(Qt.NoPen)
        p.setBrush(hgrad(1100, 1140, rgb(120, 100, 80), rgb(176, 150, 120), rgb(100, 82, 64)))
        jug = QPainterPath()
        jug.moveTo(1108, 402)
        jug.cubicTo(1096, 380, 1104, 364, 1112, 360)
        jug.lineTo(1128, 360)
        jug.cubicTo(1136, 364, 1144, 380, 1132, 402)
        jug.closeSubpath()
        p.drawPath(jug)
        p.setPen(QPen(rgb(110, 92, 72), 3))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(1128, 366, 16, 20), -90 * 16, 180 * 16)
        p.setPen(Qt.NoPen)
        for i, (colour, h) in enumerate(((rgb(110, 30, 30), 34), (rgb(30, 60, 90), 30), (rgb(50, 80, 50), 36), (rgb(120, 90, 40), 28))):
            p.setBrush(colour)
            p.drawRect(QRectF(1360 + i * 11, 402 - h, 10, h))
            p.setBrush(rgb(220, 190, 110, 160))
            p.drawRect(QRectF(1360 + i * 11, 402 - h + 6, 10, 2))

    def _paint_rug(self, p: QPainter) -> None:
        c = QPointF(1080, 812)
        colours = (rgb(120, 34, 30), rgb(200, 170, 120), rgb(60, 90, 60), rgb(150, 60, 40), rgb(210, 180, 130), rgb(110, 30, 28))
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 60))
        p.drawEllipse(c + QPointF(0, 8), 392, 70)
        for i, colour in enumerate(colours):
            k = 1 - i / len(colours)
            p.setBrush(colour)
            p.drawEllipse(c, 390 * k, 66 * k)
        p.setPen(QPen(rgb(0, 0, 0, 40), 1))
        p.setBrush(Qt.NoBrush)
        for i in range(1, 24):
            k = i / 24
            p.drawEllipse(c, 390 * k, 66 * k)
        p.setPen(Qt.NoPen)

    def _paint_chair(self, p: QPainter) -> None:
        leather = rgb(112, 40, 30)
        dark = scaled(leather, 0.6)
        p.setPen(Qt.NoPen)
        # shadow
        p.setBrush(rgb(0, 0, 0, 70))
        p.drawEllipse(QPointF(880, 836), 150, 18)
        # back legs and front legs
        p.setBrush(rgb(60, 36, 22))
        for x in (790, 960):
            p.drawRect(QRectF(x, 790, 12, 46))
        # back, seen from the side, with its wing
        back = QPainterPath()
        back.moveTo(770, 800)
        back.cubicTo(760, 700, 760, 560, 790, 500)
        back.cubicTo(808, 480, 846, 486, 850, 520)
        back.lineTo(846, 800)
        back.closeSubpath()
        p.setBrush(hgrad(760, 850, scaled(leather, 0.75), scaled(leather, 1.15), dark))
        p.drawPath(back)
        # seat and front
        p.setBrush(vgrad(690, 800, scaled(leather, 1.1), leather, dark))
        p.drawRoundedRect(QRectF(800, 690, 190, 110), 18, 18)
        # cushion
        p.setBrush(vgrad(668, 700, scaled(leather, 1.35), scaled(leather, 1.05)))
        p.drawRoundedRect(QRectF(830, 668, 160, 32), 14, 14)
        # arm with a rolled front
        p.setBrush(vgrad(626, 720, scaled(leather, 1.2), leather, dark))
        p.drawRoundedRect(QRectF(806, 632, 196, 64), 20, 20)
        p.setBrush(radial(992, 660, 34, scaled(leather, 1.3), dark))
        p.drawEllipse(QPointF(990, 662), 26, 32)
        # buttons
        p.setBrush(scaled(leather, 0.5))
        for y in range(540, 640, 26):
            p.drawEllipse(QPointF(806 + (y % 3) * 4, y), 2.5, 2.5)
        # a tartan blanket over the arm
        throw = QPainterPath()
        throw.moveTo(870, 630)
        throw.cubicTo(900, 622, 940, 624, 960, 632)
        throw.lineTo(966, 742)
        throw.cubicTo(940, 752, 900, 748, 878, 740)
        throw.closeSubpath()
        p.setBrush(rgb(40, 76, 60))
        p.drawPath(throw)
        p.save()
        p.setClipPath(throw)
        p.setPen(QPen(rgb(170, 40, 36, 200), 5))
        for x in range(870, 970, 22):
            p.drawLine(QPointF(x, 620), QPointF(x + 4, 760))
        for y in range(630, 760, 22):
            p.drawLine(QPointF(860, y), QPointF(980, y))
        p.setPen(QPen(rgb(230, 200, 120, 140), 1.5))
        for x in range(880, 970, 22):
            p.drawLine(QPointF(x, 620), QPointF(x + 4, 760))
        p.restore()
        p.setPen(QPen(rgb(230, 200, 120, 160), 1.5))
        for x in range(882, 964, 6):
            p.drawLine(QPointF(x, 744 + (x % 12) * 0.3), QPointF(x, 754))
        p.setPen(Qt.NoPen)

    def _paint_lamp_table(self, p: QPainter) -> None:
        wood = rgb(106, 64, 34)
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 60))
        p.drawEllipse(QPointF(536, 852), 70, 10)
        p.setBrush(hgrad(526, 546, scaled(wood, 0.7), scaled(wood, 1.2), scaled(wood, 0.7)))
        p.drawRect(QRectF(528, 672, 16, 160))
        p.setBrush(scaled(wood, 0.8))
        p.drawPolygon(poly((490, 852), (536, 820), (582, 852), (574, 856), (536, 830), (498, 856)))
        p.setBrush(vgrad(656, 680, scaled(wood, 1.3), scaled(wood, 0.75)))
        p.drawEllipse(QRectF(474, 652, 124, 26))
        p.drawRect(QRectF(474, 664, 124, 10))
        p.setBrush(scaled(wood, 1.4))
        p.drawEllipse(QRectF(474, 652, 124, 20))
        # a book
        p.setBrush(rgb(40, 60, 90))
        p.drawPolygon(poly((548, 662), (588, 660), (590, 668), (550, 670)))
        p.setBrush(rgb(230, 220, 196))
        p.drawPolygon(poly((548, 662), (588, 660), (588, 663), (549, 665)))
        # oil lamp: brass font, glass chimney
        p.setBrush(radial(528, 646, 30, rgb(250, 220, 140), rgb(200, 150, 60), rgb(120, 84, 30)))
        p.drawEllipse(QPointF(535, 648), 22, 14)
        p.drawRect(QRectF(523, 654, 24, 8))
        p.setBrush(rgb(150, 110, 40))
        p.drawRect(QRectF(526, 628, 18, 8))
        chimney = QPainterPath()
        chimney.moveTo(526, 628)
        chimney.cubicTo(512, 610, 516, 594, 527, 584)
        chimney.lineTo(529, 560)
        chimney.lineTo(541, 560)
        chimney.lineTo(543, 584)
        chimney.cubicTo(554, 594, 558, 610, 544, 628)
        chimney.closeSubpath()
        p.setBrush(rgb(255, 250, 240, 70))
        p.drawPath(chimney)
        p.setPen(QPen(rgb(255, 255, 255, 120), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(chimney)
        p.setPen(Qt.NoPen)

    def _paint_log_basket(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 60))
        p.drawEllipse(QPointF(1556, 722), 64, 9)
        for i in range(7):
            x = 1508 + (i % 4) * 26 + (8 if i >= 4 else 0)
            y = 650 - (14 if i >= 4 else 0)
            p.setBrush(rgb(150, 104, 64))
            p.drawEllipse(QPointF(x, y), 14, 13)
            p.setBrush(rgb(196, 152, 100))
            p.drawEllipse(QPointF(x, y), 10, 9)
            p.setPen(QPen(rgb(150, 104, 64), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(x, y), 5, 4.5)
            p.setPen(Qt.NoPen)
        basket = poly((1494, 650), (1618, 650), (1606, 720), (1506, 720))
        p.setBrush(vgrad(650, 720, rgb(176, 136, 80), rgb(120, 86, 46)))
        p.drawPolygon(basket)
        p.setPen(QPen(rgb(100, 70, 36), 1.4))
        for y in range(658, 720, 8):
            p.drawLine(QPointF(1496, y), QPointF(1616, y))
        p.setPen(Qt.NoPen)

    def _paint_glass(self, p: QPainter) -> None:
        w = self.outside.weather
        # Frost creeping in from the corners on a cold day
        if w.snow_on_ground or w.frozen_lake:
            k = 1.0 if w.frozen_lake else 0.6
            for cx, cy in ((GLASS.left(), GLASS.top()), (GLASS.right(), GLASS.top()), (GLASS.left(), GLASS.bottom()), (GLASS.right(), GLASS.bottom())):
                p.setPen(Qt.NoPen)
                p.setBrush(radial(cx, cy, 90, (0, rgb(235, 242, 250, 200 * k)), (0.5, rgb(225, 235, 245, 90 * k)), (1, rgb(220, 230, 240, 0))))
                p.drawEllipse(QPointF(cx, cy), 90, 90)
        # Raindrops on the glass
        if self._drops:
            light = mix(rgb(70, 80, 100), rgb(220, 230, 240), self.outside.light.daylight)
            p.setPen(Qt.NoPen)
            for x, y, r, speed, _ in self._drops:
                if speed > 0:
                    p.setBrush(alpha(light, 40))
                    p.drawRect(QRectF(x - r * 0.35, y - 30, r * 0.7, 30))
                p.setBrush(alpha(scaled(light, 0.6), 120))
                p.drawEllipse(QPointF(x, y), r, r * 1.15)
                p.setBrush(alpha(light, 200))
                p.drawEllipse(QPointF(x - r * 0.3, y - r * 0.35), r * 0.35, r * 0.35)

    def _paint_small_flames(self, p: QPainter) -> None:
        lamp_on = self.lamp_on()
        flames = [(c, 1.0) for c in CANDLES]
        if lamp_on:
            flames.append((LAMP_FLAME, 1.3))
        p.setPen(Qt.NoPen)
        for i, (c, size) in enumerate(flames):
            sway = 1.5 * wobble(self.t * 3 + i * 2, 1.0, 2.7)
            h = (14 + 2 * wobble(self.t * 5 + i, 1.3, 3.1)) * size
            p.setBrush(radial(c.x(), c.y(), 26 * size, (0, rgb(255, 200, 110, 120)), (1, rgb(255, 160, 60, 0))))
            p.drawEllipse(c, 26 * size, 26 * size)
            flame = QPainterPath()
            flame.moveTo(c.x() - 4 * size, c.y() + 2)
            flame.cubicTo(c.x() - 5 * size, c.y() - h * 0.5, c.x() + sway, c.y() - h * 0.8, c.x() + sway, c.y() - h)
            flame.cubicTo(c.x() + sway, c.y() - h * 0.8, c.x() + 5 * size, c.y() - h * 0.5, c.x() + 4 * size, c.y() + 2)
            flame.closeSubpath()
            p.setBrush(vgrad(c.y() - h, c.y() + 2, rgb(255, 240, 180), rgb(255, 170, 60), rgb(120, 140, 255)))
            p.drawPath(flame)

    def lamp_on(self) -> bool:
        l = self.outside.light
        return l.daylight < 0.55 or (l.daylight < 0.8 and self.outside.weather.clouds > 0.85)

    def _paint_lighting(self, p: QPainter, target: QRectF, s: float, ox: float, oy: float) -> None:
        l, w = self.outside.light, self.outside.weather
        f = self.fire.flicker()
        flash = self.outside.lightning
        ambient = 0.04 + 0.78 * l.daylight * (1 - 0.32 * w.clouds) + 0.5 * flash
        darkness = max(0.0, 1 - ambient)

        lm = QImage(320, 180, QImage.Format_ARGB32_Premultiplied)
        lm.fill(QColor(10, 5, 3, int(248 * darkness)))
        lp = QPainter(lm)
        lp.setRenderHint(QPainter.Antialiasing)
        # Same mapping as the scene, but onto the small light map
        lp.scale(320 / target.width(), 180 / target.height())
        lp.translate(ox - target.x(), oy - target.y())
        lp.scale(s, s)
        lp.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        lp.setPen(Qt.NoPen)

        def light(x: float, y: float, r: float, strength: float) -> None:
            lp.setBrush(radial(x, y, r, (0, rgb(0, 0, 0, 255 * min(1, strength))), (0.45, rgb(0, 0, 0, 150 * min(1, strength))), (1, rgb(0, 0, 0, 0))))
            lp.drawEllipse(QPointF(x, y), r, r)

        fx = (FIREBOX_LEFT + FIREBOX_RIGHT) / 2
        light(fx, 620, 760 * (0.95 + 0.05 * f), 0.62 * f)
        light(fx, 640, 300, 0.9)
        light(fx, 770, 380, 0.6 * f)
        if self.lamp_on():
            light(LAMP_FLAME.x(), LAMP_FLAME.y(), 430, 0.7)
            light(clock.CX, 330, 210, 0.55)  # the lamp catching the clock face
        for c in CANDLES:
            light(c.x(), c.y(), 150, 0.45)
        light(GLASS.center().x(), GLASS.center().y(), 560, 0.85 * l.daylight * (1 - 0.3 * w.clouds) + flash)
        lp.end()
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(target, lm)
        p.restore()

        # Warm firelight, added on top
        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.setPen(Qt.NoPen)
        warm = 0.45 + 0.55 * darkness
        p.setBrush(radial(fx, 600, 900, (0, rgb(255, 120, 40, 110 * f * warm)), (0.35, rgb(255, 100, 30, 45 * f * warm)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(QPointF(fx, 600), 900, 900)
        if self.lamp_on():
            p.setBrush(radial(LAMP_FLAME.x(), LAMP_FLAME.y(), 380, (0, rgb(255, 170, 80, 70)), (1, rgb(0, 0, 0, 0))))
            p.drawEllipse(LAMP_FLAME, 380, 380)
        p.restore()
