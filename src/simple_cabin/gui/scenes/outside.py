"""The view outside: the cabin on the shore of a forest lake, under
whatever the sky is really doing.

Drawn on the 1600×900 virtual canvas. The slow-changing parts (sky, hills,
lake, cabin) are cached as images and only redrawn when the light or the
weather changes; clouds, rain, snow, smoke, swaying trees and the lit
windows are drawn fresh every frame.
"""
from __future__ import annotations

import math
import random
from dataclasses import astuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from simple_cabin.core.sky import Light
from simple_cabin.core.weather import SceneWeather
from simple_cabin.gui.paint import (
    H,
    W,
    alpha,
    draw_pine,
    hgrad,
    mix,
    poly,
    radial,
    rgb,
    scaled,
    soft_blob,
    vgrad,
    wobble,
)

HORIZON = 525.0
FULL = QRectF(0, 0, W, H)
# The part of the scene seen through the cabin's own window: the lake.
WINDOW_VIEW = QRectF(10, 175, 820, 720)

CHIMNEY_TOP = QPointF(1382, 330)


class OutsideScene:
    def __init__(self):
        self.weather = SceneWeather()
        self.light = Light(1.0, 0.0, 0.5, -1.0, False)
        self.moon_phase = 0.3
        self.fire_glow = 1.0  # set by the inside scene's fire, for the windows
        self.t = 0.0
        self._rng = random.Random(1)
        self._caches: dict = {}
        self._cloud_sprites: list[QImage] = []
        self._cloud_key = None
        self._clouds: list[list[float]] = []
        self._rain: list[list[float]] = []
        self._snow: list[list[float]] = []
        self._ripples: list[list[float]] = []
        self._smoke: list[list[float]] = []
        self._smoke_timer = 0.0
        self._smoke_sprite = soft_blob(64, rgb(255, 255, 255, 200))
        self._fog_sprite = soft_blob(256, rgb(255, 255, 255, 255))
        self._flash = 0.0  # seconds left of the current lightning flash
        self._bolt: list[tuple[float, float]] = []
        self._next_flash = 6.0
        self.thunder_pending = False  # set when lightning strikes; the stage plays the rumble
        self._stars = [(self._rng.uniform(0, W), self._rng.uniform(0, HORIZON - 120), self._rng.uniform(0.6, 2.0)) for _ in range(160)]

    # --- state

    def set_conditions(self, weather: SceneWeather, light: Light, moon_phase: float) -> None:
        self.weather, self.light, self.moon_phase = weather, light, moon_phase

    def _static_key(self):
        l = self.light
        return (
            round(l.daylight, 2), round(l.golden, 2), round(l.sun_progress, 3), round(l.night_progress, 3),
            l.morning, astuple(self.weather), round(self.moon_phase, 2),
        )

    @property
    def lightning(self) -> float:
        """0..1 brightness of a lightning flash right now."""
        if self._flash <= 0:
            return 0.0
        k = 1 - self._flash / 0.45
        return max(0.0, math.sin(k * math.pi * 3) * (1 - k)) if k < 1 else 0.0

    # --- colour

    def lit(self, c: QColor, strength: float = 1.0) -> QColor:
        """A daylight colour as it looks in the current light."""
        l, w = self.light, self.weather
        night = rgb(c.red() * 0.13 + 6, c.green() * 0.15 + 10, c.blue() * 0.22 + 24, c.alpha())
        out = mix(night, c, l.daylight)
        if l.golden > 0:
            warm = rgb(min(255, out.red() * 1.12 + 10), out.green() * 0.88, out.blue() * 0.72, c.alpha())
            out = mix(out, warm, l.golden * 0.6 * (1 - w.clouds * 0.5) * l.daylight * strength + l.golden * 0.15)
        if w.clouds > 0.6:
            grey = (out.red() + out.green() + out.blue()) / 3
            out = mix(out, rgb(grey, grey, grey * 1.04, c.alpha()), (w.clouds - 0.6) * 0.8)
            out = scaled(out, 1 - (w.clouds - 0.6) * 0.35 - w.rain * 0.12)
        return out

    def sky_colours(self) -> tuple[QColor, QColor]:
        l, w = self.light, self.weather
        top = mix(rgb(6, 10, 28), rgb(64, 128, 204), l.daylight)
        bottom = mix(rgb(22, 32, 62), rgb(176, 210, 238), l.daylight)
        if l.golden > 0:
            g = l.golden * (1 - w.clouds * 0.55)
            top = mix(top, rgb(70, 72, 140), g * 0.5)
            bottom = mix(bottom, rgb(250, 150, 92) if not l.morning else rgb(252, 176, 120), g * 0.85)
        if w.clouds > 0.5:
            k = (w.clouds - 0.5) * 2
            dull = mix(rgb(20, 22, 30), rgb(150, 158, 170), l.daylight)
            top = mix(top, scaled(dull, 0.85 - w.rain * 0.25), k * 0.85)
            bottom = mix(bottom, scaled(dull, 1.1 - w.rain * 0.2), k * 0.75)
        return top, bottom

    # --- animation

    def step(self, dt: float) -> None:
        self.t += dt
        w = self.weather
        drift = 1 if w.wind_from_west else -1
        rng = self._rng

        # Clouds
        want = int(2 + w.clouds * 13)
        while len(self._clouds) < want:
            self._clouds.append(self._new_cloud(anywhere=True))
        del self._clouds[want:]
        speed = 6 + w.wind * 45
        for c in self._clouds:
            c[0] += drift * speed * c[3] * dt
            if (drift > 0 and c[0] > W + 250) or (drift < 0 and c[0] < -650):
                c[:] = self._new_cloud(anywhere=False)

        # Rain
        want = int(w.rain * 520)
        while len(self._rain) < want:
            self._rain.append(self._new_drop(anywhere=True))
        del self._rain[want:]
        lean = drift * (60 + w.wind * 420)
        for d in self._rain:
            d[0] += lean * dt
            d[1] += d[2] * dt
            if d[1] > d[4]:
                if d[4] > HORIZON + 10 and self._over_lake(d[0], d[4]) and rng.random() < 0.35:
                    self._ripples.append([d[0], d[4], 0.0])
                d[:] = self._new_drop(anywhere=False)
            elif d[0] < -50 or d[0] > W + 50:
                d[:] = self._new_drop(anywhere=False)

        for r in self._ripples:
            r[2] += dt
        self._ripples = [r for r in self._ripples if r[2] < 0.9][-160:]

        # Snow
        want = int(w.snow * 420)
        while len(self._snow) < want:
            self._snow.append(self._new_flake(anywhere=True))
        del self._snow[want:]
        for f in self._snow:
            f[0] += (drift * (12 + w.wind * 140) + math.sin(self.t * 1.3 + f[4]) * 18) * dt
            f[1] += f[2] * dt
            if f[1] > f[5] or f[0] < -30 or f[0] > W + 30:
                f[:] = self._new_flake(anywhere=False)

        # Chimney smoke
        self._smoke_timer -= dt
        if self._smoke_timer <= 0:
            self._smoke_timer = 0.22
            self._smoke.append([CHIMNEY_TOP.x() + rng.uniform(-6, 6), CHIMNEY_TOP.y(), 0.0, rng.uniform(0.8, 1.2)])
        for s in self._smoke:
            s[2] += dt
            s[1] -= (26 - w.wind * 14) * dt
            s[0] += drift * (6 + w.wind * 70) * dt * (0.5 + s[2] * 0.25) + math.sin(self.t + s[3] * 5) * 4 * dt
        self._smoke = [s for s in self._smoke if s[2] < 7.0]

        # Lightning
        if self._flash > 0:
            self._flash -= dt
        if w.thunder:
            self._next_flash -= dt
            if self._next_flash <= 0:
                self._next_flash = rng.uniform(7, 22)
                self._flash = 0.45
                self._bolt = self._make_bolt()
                self.thunder_pending = True

    def _new_cloud(self, anywhere: bool) -> list[float]:
        rng = self._rng
        drift = 1 if self.weather.wind_from_west else -1
        x = rng.uniform(-400, W) if anywhere else (-600 if drift > 0 else W + 200)
        # x, y, scale, speed factor, sprite index
        return [x, rng.uniform(-30, 300), rng.uniform(0.7, 1.6), rng.uniform(0.6, 1.3), rng.randrange(4)]

    def _new_drop(self, anywhere: bool) -> list[float]:
        rng = self._rng
        x = rng.uniform(-200, W + 200)
        y = rng.uniform(-50, H) if anywhere else rng.uniform(-80, -10)
        # x, y, speed, length, where it lands
        return [x, y, rng.uniform(800, 1150), rng.uniform(14, 28), rng.uniform(HORIZON - 40, H + 20)]

    def _new_flake(self, anywhere: bool) -> list[float]:
        rng = self._rng
        x = rng.uniform(-60, W + 60)
        y = rng.uniform(-20, H) if anywhere else rng.uniform(-40, -5)
        size = rng.uniform(1.4, 4.2)
        # x, y, speed (bigger = nearer = faster), size, phase, where it lands
        return [x, y, 22 + size * 14, size, rng.uniform(0, 6.3), rng.uniform(HORIZON, H + 10)]

    def _over_lake(self, x: float, y: float) -> bool:
        if x > 1600 or x < 0:
            return False
        shore = 880 + (y - 760) * -0.4 if y < 760 else 880 - (y - 760) * 0.45
        bank = 380 - (900 - y) * 2.6
        return x < shore and x > bank and not self.weather.frozen_lake

    def _make_bolt(self) -> list[tuple[float, float]]:
        rng = self._rng
        x, y = rng.uniform(150, 1450), 40.0
        pts = [(x, y)]
        while y < 420:
            y += rng.uniform(25, 55)
            x += rng.uniform(-40, 40)
            pts.append((x, y))
        return pts

    # --- painting

    def paint(self, p: QPainter, target: QRectF, source: QRectF = FULL, cabin: bool = True) -> None:
        """Draw the source part of the virtual canvas into target (in the
        painter's current device coordinates, which should be unscaled)."""
        scale = max(target.width() / source.width(), target.height() / source.height())
        dpr = p.device().devicePixelRatioF() if p.device() else 1.0
        key = (int(target.width()), int(target.height()), dpr, source.getRect(), cabin, self._static_key())
        layers = self._caches.get(key)
        if layers is None:
            layers = (self._render_layer(target, source, scale, dpr, sky=True, cabin=cabin),
                      self._render_layer(target, source, scale, dpr, sky=False, cabin=cabin))
            if len(self._caches) > 3:
                self._caches.clear()
            self._caches[key] = layers
        sky_img, land_img = layers

        p.save()
        p.setClipRect(target)
        p.drawImage(target.topLeft(), sky_img)

        def to_scene() -> None:
            p.translate(target.x() + target.width() / 2, target.y() + target.height() / 2)
            p.scale(scale, scale)
            p.translate(-source.center().x(), -source.center().y())

        p.save()
        to_scene()
        self._paint_clouds(p)
        if self.lightning > 0 and self._bolt:
            self._paint_bolt(p)
        p.restore()

        p.drawImage(target.topLeft(), land_img)

        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_lake_life(p)
        if cabin:
            self._paint_windows(p)
            self._paint_smoke(p)
        self._paint_foreground_trees(p, cabin)
        self._paint_fog(p)
        self._paint_precipitation(p)
        p.restore()

        if self.lightning > 0:
            p.fillRect(target, rgb(225, 230, 255, 150 * self.lightning))
        p.restore()

    def _render_layer(self, target: QRectF, source: QRectF, scale: float, dpr: float, sky: bool, cabin: bool) -> QImage:
        img = QImage(int(target.width() * dpr), int(target.height() * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(target.width() / 2, target.height() / 2)
        p.scale(scale, scale)
        p.translate(-source.center().x(), -source.center().y())
        if sky:
            self._paint_sky(p)
        else:
            self._paint_land(p, cabin)
        p.end()
        return img

    def _paint_sky(self, p: QPainter) -> None:
        l, w = self.light, self.weather
        top, bottom = self.sky_colours()
        p.fillRect(QRectF(-200, -200, W + 400, HORIZON + 260), vgrad(0, HORIZON, top, bottom))

        visible = 1 - w.clouds
        if l.daylight < 0.6 and visible > 0.05:
            p.setPen(Qt.NoPen)
            k = (0.6 - l.daylight) / 0.6 * visible
            for x, y, s in self._stars:
                p.setBrush(rgb(255, 255, 240, 220 * k * (0.5 + 0.5 * math.sin(x * 3.1))))
                p.drawEllipse(QPointF(x, y), s * 0.8, s * 0.8)

        def arc(progress: float) -> QPointF:
            return QPointF(120 + progress * 1360, 560 - math.sin(progress * math.pi) * 460)

        if 0 <= l.sun_progress <= 1 and w.clouds < 0.9:
            c = arc(l.sun_progress)
            glare = (1 - w.clouds * 0.9) ** 1.2
            sun = mix(rgb(255, 246, 200), rgb(255, 160, 80), l.golden)
            p.setPen(Qt.NoPen)
            p.setBrush(radial(c.x(), c.y(), 260, (0, alpha(sun, 210 * glare)), (0.18, alpha(sun, 90 * glare)), (1, alpha(sun, 0))))
            p.drawEllipse(c, 260, 260)
            p.setBrush(alpha(mix(sun, rgb(255, 255, 245), 0.6), 255 * max(0.3, glare)))
            p.drawEllipse(c, 30, 30)
        if 0 <= l.night_progress <= 1 and l.daylight < 0.7:
            self._paint_moon(p, arc(l.night_progress), (1 - w.clouds * 0.85) * (1 - l.daylight))

    def _paint_moon(self, p: QPainter, c: QPointF, visibility: float) -> None:
        if visibility <= 0.03:
            return
        r = 26
        p.setPen(Qt.NoPen)
        p.setBrush(radial(c.x(), c.y(), 140, (0, rgb(220, 225, 255, 70 * visibility)), (1, rgb(220, 225, 255, 0))))
        p.drawEllipse(c, 140, 140)
        lit_path = moon_shape(c.x(), c.y(), r, self.moon_phase)
        p.setBrush(rgb(60, 66, 90, 120 * visibility))
        p.drawEllipse(c, r, r)
        p.setBrush(rgb(244, 242, 226, 255 * visibility))
        p.drawPath(lit_path)

    def _paint_land(self, p: QPainter, cabin: bool) -> None:
        l, w = self.light, self.weather
        _, sky_bottom = self.sky_colours()
        rng = random.Random(42)

        # Hills, far then near
        far = mix(self.lit(rgb(110, 130, 160)), sky_bottom, 0.45 + w.fog * 0.4)
        near = mix(self.lit(rgb(60, 88, 92)), sky_bottom, 0.25 + w.fog * 0.5)
        far_pts = hill_points(330, 90, 3)
        near_pts = hill_points(420, 60, 9)
        hill_paths = []
        for pts, colour in ((far_pts, far), (near_pts, near)):
            path = QPainterPath()
            path.moveTo(-200, HORIZON + 5)
            for x, y in pts:
                path.lineTo(x, y)
            path.lineTo(W + 200, HORIZON + 5)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(colour)
            p.drawPath(path)
            hill_paths.append((path, colour))
        if w.snow_on_ground or w.snow > 0:
            # Snow on the tops of the far hills
            p.save()
            p.setClipPath(hill_paths[0][0])
            snowcap = mix(self.lit(rgb(235, 240, 248)), sky_bottom, 0.35)
            p.fillRect(QRectF(-200, 150, W + 400, 160), vgrad(150, 310, (0, snowcap), (0.6, alpha(snowcap, 220)), (1, alpha(snowcap, 0))))
            p.restore()
            p.setBrush(near)
            p.drawPath(hill_paths[1][0])

        # The far shore's forest, and its reflection
        forest = mix(self.lit(rgb(34, 70, 46)), sky_bottom, 0.3 + w.fog * 0.5)
        trees = []
        x = -20.0
        while x < W + 20:
            h = rng.uniform(26, 70)
            trees.append((x, h, rng.uniform(9, 14)))
            x += rng.uniform(7, 15)

        def far_forest(colour: QColor) -> None:
            p.setBrush(colour)
            p.drawRect(QRectF(-200, HORIZON - 14, W + 400, 16))
            for tx, th, tw in trees:
                p.drawPolygon(poly((tx - tw, HORIZON), (tx, HORIZON - th), (tx + tw, HORIZON)))
            if w.snow_on_ground:
                p.setBrush(alpha(self.lit(rgb(230, 236, 244)), 150))
                for tx, th, tw in trees[::2]:
                    p.drawPolygon(poly((tx - tw * 0.35, HORIZON - th * 0.65), (tx, HORIZON - th), (tx + tw * 0.35, HORIZON - th * 0.65)))

        far_forest(forest)

        # The lake
        if w.frozen_lake:
            water_top = mix(self.lit(rgb(196, 214, 226)), sky_bottom, 0.3)
            water_bottom = self.lit(rgb(150, 176, 196))
        else:
            water_top = mix(sky_bottom, self.lit(rgb(40, 70, 90)), 0.35)
            water_bottom = mix(self.lit(rgb(18, 40, 58)), sky_bottom, 0.12)
        p.fillRect(QRectF(-200, HORIZON, W + 400, H - HORIZON + 200), vgrad(HORIZON, H, water_top, water_bottom))
        p.save()
        p.setOpacity(0.18 if w.frozen_lake else 0.42 * (1 - w.rain * 0.5))
        p.translate(0, 2 * HORIZON)
        p.scale(1, -1)
        for path, colour in hill_paths:
            p.setBrush(colour)
            p.drawPath(path)
        far_forest(forest)
        p.restore()
        if w.frozen_lake:
            p.setPen(QPen(alpha(self.lit(rgb(240, 248, 255)), 120), 1.2))
            for _ in range(14):
                x0, y0 = rng.uniform(100, 800), rng.uniform(HORIZON + 30, H - 20)
                p.drawLine(QPointF(x0, y0), QPointF(x0 + rng.uniform(-90, 90), y0 + rng.uniform(-8, 8)))
            p.setPen(Qt.NoPen)
        # Soften the reflection into the water, nearer = darker.
        p.fillRect(QRectF(-200, HORIZON, W + 400, H - HORIZON + 200),
                   vgrad(HORIZON, H, (0, alpha(water_top, 0)), (0.6, alpha(water_bottom, 120)), (1, alpha(water_bottom, 200))))

        ground = self.lit(rgb(232, 238, 246)) if w.snow_on_ground else self.lit(rgb(70, 98, 50))
        ground_dark = scaled(ground, 0.8)

        # The near shore on the right
        shore = QPainterPath()
        shore.moveTo(W + 200, 612)
        shore.lineTo(1100, 616)
        shore.cubicTo(990, 622, 905, 680, 885, 760)
        shore.cubicTo(872, 820, 845, 880, 820, H + 50)
        shore.lineTo(W + 200, H + 50)
        shore.closeSubpath()
        p.setBrush(vgrad(610, H, ground, ground_dark))
        p.drawPath(shore)
        # stones at the water's edge
        for i in range(26):
            t = i / 25
            sx = 1100 - t * 230 + rng.uniform(-6, 6)
            sy = 618 + t * 270 + rng.uniform(-4, 4)
            if t > 0.25:
                sx = 905 - (t - 0.25) * 110 + rng.uniform(-6, 6)
            p.setBrush(self.lit(rgb(120 + rng.randint(-15, 15), 116, 108)))
            p.drawEllipse(QPointF(sx, sy), rng.uniform(5, 11), rng.uniform(3, 6))

        # Trees behind the cabin
        back_tree = self.lit(rgb(30, 74, 44))
        for i, (tx, th, tw) in enumerate(((960, 330, 120), (1040, 420, 150), (1180, 470, 160), (1300, 380, 140),
                                          (1430, 450, 160), (1520, 360, 130), (1600, 420, 150))):
            draw_pine(p, tx, 640, th, tw, scaled(back_tree, 0.85 + 0.05 * (i % 3)), seed=100 + i, snow=w.snow_on_ground)

        if cabin:
            self._paint_cabin(p)
            self._paint_jetty(p)

        # The grassy bank in the near left corner
        bank = QPainterPath()
        bank.moveTo(-200, 770)
        bank.cubicTo(120, 748, 270, 790, 390, H + 50)
        bank.lineTo(-200, H + 50)
        bank.closeSubpath()
        p.setBrush(vgrad(760, H, scaled(ground, 0.9), scaled(ground, 0.65)))
        p.drawPath(bank)
        if not w.snow_on_ground:
            p.setPen(QPen(scaled(ground, 1.25), 1.6))
            for _ in range(70):
                gx = rng.uniform(0, 340)
                gy = 770 + (gx / 340) ** 1.6 * 110 + rng.uniform(0, 20)
                p.drawLine(QPointF(gx, gy), QPointF(gx + rng.uniform(-4, 4), gy - rng.uniform(8, 18)))
            p.setPen(Qt.NoPen)

    def _paint_cabin(self, p: QPainter) -> None:
        w = self.weather
        wood = self.lit(rgb(142, 92, 52))
        wood_dark = self.lit(rgb(98, 62, 36))
        roof = self.lit(rgb(70, 52, 44))
        snow = self.lit(rgb(240, 244, 250))
        p.setPen(Qt.NoPen)

        # Side wall, receding to the right
        side = poly((1240, 540), (1440, 556), (1440, 690), (1240, 706))
        p.setBrush(scaled(wood, 0.78))
        p.drawPolygon(side)
        p.setPen(QPen(scaled(wood_dark, 0.8), 2))
        for i in range(1, 10):
            k = i / 10
            p.drawLine(QPointF(1240, 540 + 166 * k), QPointF(1440, 556 + 134 * k))
        p.setPen(Qt.NoPen)

        # Chimney (stone), on the far side
        stone = self.lit(rgb(128, 122, 114))
        p.setBrush(stone)
        p.drawRect(QRectF(1360, 330, 46, 160))
        p.setBrush(scaled(stone, 0.7))
        p.drawRect(QRectF(1355, 326, 56, 10))
        p.setPen(QPen(scaled(stone, 0.72), 1.5))
        for row in range(8):
            y = 338 + row * 19
            p.drawLine(QPointF(1360, y), QPointF(1406, y))
            off = 12 if row % 2 else 26
            p.drawLine(QPointF(1360 + off, y), QPointF(1360 + off, y + 19))
        p.setPen(Qt.NoPen)

        # Roof: the side slope, then the gable's barge boards
        slope = poly((1120, 398), (1330, 414), (1468, 566), (1262, 552))
        p.setBrush(vgrad(398, 566, scaled(roof, 1.1), scaled(roof, 0.8)))
        p.drawPolygon(slope)
        p.setPen(QPen(scaled(roof, 0.65), 1.4))
        for i in range(1, 9):
            k = i / 9
            p.drawLine(QPointF(1120 + 142 * k, 398 + 154 * k), QPointF(1330 + 138 * k, 414 + 152 * k))
        p.setPen(Qt.NoPen)
        if w.snow_on_ground or w.snow > 0.3:
            p.setBrush(snow)
            p.drawPolygon(poly((1120, 396), (1330, 412), (1462, 560), (1440, 566), (1264, 548)))
            # icicles
            p.setBrush(alpha(self.lit(rgb(220, 235, 250)), 220))
            for i in range(9):
                x = 1272 + i * 22
                p.drawPolygon(poly((x, 556 + i), (x + 6, 556 + i), (x + 3, 572 + i + (i * 7) % 10)))

        # Front: log wall with the round log ends at the corners
        front = QRectF(1000, 540, 240, 166)
        p.setBrush(wood)
        p.drawRect(front)
        gable = poly((1000, 541), (1120, 418), (1240, 541))
        p.setBrush(scaled(wood, 0.9))
        p.drawPolygon(gable)
        p.setPen(QPen(scaled(wood_dark, 0.9), 1.2))
        for i in range(1, 12):
            x = 1000 + i * 20
            top = 541 - (120 - abs(x - 1120)) * (123 / 120)
            p.drawLine(QPointF(x, max(top, 420)), QPointF(x, 541))
        p.setPen(Qt.NoPen)
        log_h = 166 / 10
        for i in range(10):
            y = 540 + i * log_h
            p.setBrush(vgrad(y, y + log_h, scaled(wood, 1.15), wood, scaled(wood_dark, 0.9)))
            p.drawRect(QRectF(992, y, 256, log_h - 1.5))
            for cx in (992, 1248):
                p.setBrush(self.lit(rgb(186, 140, 92)))
                p.drawEllipse(QPointF(cx, y + log_h / 2), log_h / 2, log_h / 2 - 0.5)
                p.setBrush(self.lit(rgb(150, 106, 64)))
                p.drawEllipse(QPointF(cx, y + log_h / 2), log_h / 4, log_h / 4)
        # little round attic window
        p.setBrush(wood_dark)
        p.drawEllipse(QPointF(1120, 488), 17, 17)

        # Barge boards on the gable
        p.setBrush(scaled(roof, 0.9))
        p.drawPolygon(poly((978, 556), (1120, 396), (1262, 556), (1250, 562), (1120, 414), (990, 562)))
        if w.snow_on_ground or w.snow > 0.3:
            p.setBrush(snow)
            p.drawPolygon(poly((976, 552), (1120, 390), (1264, 552), (1258, 556), (1120, 400), (982, 556)))

        # Door and step
        p.setBrush(wood_dark)
        p.drawRect(QRectF(1094, 612, 52, 94))
        p.setBrush(scaled(wood_dark, 1.25))
        p.drawRect(QRectF(1099, 617, 42, 89))
        p.setBrush(self.lit(rgb(200, 170, 80)))
        p.drawEllipse(QPointF(1133, 662), 3, 3)
        p.setBrush(self.lit(rgb(120, 116, 108)))
        p.drawRect(QRectF(1084, 704, 72, 9))

        # Window frames (the glass is drawn per frame, for the fire's flicker)
        for rect in CABIN_WINDOWS:
            p.setBrush(wood_dark)
            p.drawRect(rect.adjusted(-5, -5, 5, 5))
            p.setBrush(snow if w.snow_on_ground else scaled(wood_dark, 1.3))
            p.drawRect(QRectF(rect.left() - 8, rect.bottom() + 4, rect.width() + 16, 5))
        # A woodpile against the side wall
        for row in range(3):
            for i in range(6 - row):
                cx = 1452 + i * 12 + row * 6
                cy = 696 - row * 11
                p.setBrush(self.lit(rgb(170, 124, 80)))
                p.drawEllipse(QPointF(cx, cy), 6, 6)
                p.setBrush(self.lit(rgb(130, 90, 56)))
                p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)

    def _paint_jetty(self, p: QPainter) -> None:
        plank = self.lit(rgb(122, 92, 62))
        post = self.lit(rgb(84, 62, 42))
        p.setPen(Qt.NoPen)
        for x in range(640, 961, 64):
            p.setBrush(post)
            p.drawRect(QRectF(x, 720, 9, 46))
            p.setBrush(alpha(post, 70))
            p.drawRect(QRectF(x, 766, 9, 28))
        p.setBrush(vgrad(708, 724, scaled(plank, 1.15), scaled(plank, 0.8)))
        p.drawRect(QRectF(620, 708, 360, 15))
        if self.weather.snow_on_ground:
            p.setBrush(self.lit(rgb(238, 242, 248)))
            p.drawRect(QRectF(620, 704, 360, 6))
        # a rowing boat tied up alongside
        hull = QPainterPath()
        hull.moveTo(650, 742)
        hull.lineTo(790, 742)
        hull.quadTo(780, 768, 740, 770)
        hull.lineTo(690, 770)
        hull.quadTo(658, 766, 650, 742)
        p.setBrush(self.lit(rgb(150, 44, 36)))
        p.drawPath(hull)
        p.setBrush(self.lit(rgb(230, 222, 200)))
        p.drawRect(QRectF(650, 740, 140, 4))
        p.setPen(QPen(self.lit(rgb(200, 190, 160)), 1.2))
        p.drawLine(QPointF(660, 742), QPointF(652, 722))
        p.setPen(Qt.NoPen)

    # --- per-frame layers

    def _paint_clouds(self, p: QPainter) -> None:
        key = (round(self.light.daylight, 1), round(self.light.golden, 1), round(self.weather.clouds, 1), round(self.weather.rain, 1))
        if key != self._cloud_key:
            self._cloud_key = key
            self._cloud_sprites = [self._make_cloud_sprite(i) for i in range(4)]
        for x, y, s, _, i in self._clouds:
            img = self._cloud_sprites[int(i)]
            p.drawImage(QRectF(x, y, img.width() * s, img.height() * s), img)

    def _make_cloud_sprite(self, seed: int) -> QImage:
        l, w = self.light, self.weather
        rng = random.Random(seed)
        heavy = max(0.0, (w.clouds - 0.55) * 2.2) + w.rain * 0.6
        day = mix(rgb(250, 250, 252), rgb(128, 134, 146), min(1, heavy))
        colour = mix(rgb(34, 38, 54), day, l.daylight)
        if l.golden > 0:
            colour = mix(colour, rgb(250, 176, 150), l.golden * 0.5 * (1 - heavy * 0.6))
        img = QImage(520, 260, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        blob = soft_blob(160, alpha(colour, 230 if heavy < 0.5 else 245))
        shade = soft_blob(160, alpha(scaled(colour, 0.78), 200))
        for _ in range(9):
            # Every blob stays wholly inside the sprite, so no hard edges.
            r = rng.uniform(60, 110)
            cx = rng.uniform(r, 520 - r)
            cy = rng.uniform(r * 0.7, 260 - r * 0.6 - 16)
            p.drawImage(QRectF(cx - r, cy - r * 0.7 + 14, r * 2, r * 1.3), shade)
            p.drawImage(QRectF(cx - r, cy - r * 0.7, r * 2, r * 1.3), blob)
        p.end()
        return img

    def _paint_bolt(self, p: QPainter) -> None:
        k = self.lightning
        path = QPainterPath()
        path.moveTo(*self._bolt[0])
        for pt in self._bolt[1:]:
            path.lineTo(*pt)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgb(200, 210, 255, 90 * k), 10))
        p.drawPath(path)
        p.setPen(QPen(rgb(255, 255, 255, 255 * k), 2.5))
        p.drawPath(path)

    def _paint_lake_life(self, p: QPainter) -> None:
        l, w = self.light, self.weather
        if w.frozen_lake:
            return
        # Glints on the water, gathered into a glade under the sun or moon.
        rng = random.Random(9)
        glow_x = None
        if 0 <= l.sun_progress <= 1:
            glow_x, glow_c = 120 + l.sun_progress * 1360, mix(rgb(255, 250, 230), rgb(255, 180, 110), l.golden)
        elif 0 <= l.night_progress <= 1:
            glow_x, glow_c = 120 + l.night_progress * 1360, rgb(230, 232, 255)
        strength = (1 - w.clouds * 0.8) * (1 - w.fog)
        for i in range(70):
            y = HORIZON + 6 + (rng.random() ** 1.6) * (H - HORIZON)
            depth = (y - HORIZON) / (H - HORIZON)
            if glow_x is not None and i % 2 == 0:
                x = glow_x + rng.gauss(0, 30 + depth * 90)
                c = glow_c
                a = 200 * strength * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(self.t * 2.2 + i)))
                if l.daylight < 0.3 and 0 <= l.night_progress <= 1:
                    a *= 0.4 + 0.6 * self.moon_phase_brightness()
            else:
                x = rng.uniform(0, 900)
                c = mix(self.sky_colours()[1], rgb(255, 255, 255), 0.4)
                a = 70 * (0.3 + 0.7 * l.daylight) * (0.5 + 0.5 * math.sin(self.t * 1.4 + i * 2))
            if not self._over_lake(x, y):
                continue
            length = 6 + depth * 30
            x += math.sin(self.t * 0.6 + i) * 6
            p.setPen(QPen(alpha(c, a), 1 + depth * 1.5))
            p.drawLine(QPointF(x - length / 2, y), QPointF(x + length / 2, y))
        # Rain rings
        p.setBrush(Qt.NoBrush)
        ring = mix(self.sky_colours()[1], rgb(255, 255, 255), 0.3)
        for x, y, age in self._ripples:
            depth = (y - HORIZON) / (H - HORIZON)
            r = (3 + age * 22) * (0.4 + depth)
            p.setPen(QPen(alpha(ring, 150 * (1 - age / 0.9)), 1))
            p.drawEllipse(QPointF(x, y), r, r * 0.3)
        p.setPen(Qt.NoPen)

    def moon_phase_brightness(self) -> float:
        return (1 - math.cos(2 * math.pi * self.moon_phase)) / 2

    def _paint_windows(self, p: QPainter) -> None:
        l = self.light
        glow = max(0.0, 1 - l.daylight * 0.75) * self.fire_glow
        glass_day = self.lit(rgb(110, 130, 150))
        warm = rgb(255, 186, 92)
        p.setPen(Qt.NoPen)
        for rect in CABIN_WINDOWS:
            if l.daylight < 0.6:
                c = rect.center()
                p.setBrush(radial(c.x(), c.y(), 95, (0, alpha(warm, 100 * glow)), (0.4, alpha(warm, 40 * glow)), (1, alpha(warm, 0))))
                p.drawEllipse(c, 95, 95)
            p.setBrush(mix(glass_day, warm, glow))
            p.drawRect(rect)
            p.setBrush(self.lit(rgb(84, 58, 36)))
            p.drawRect(QRectF(rect.center().x() - 1.5, rect.top(), 3, rect.height()))
            p.drawRect(QRectF(rect.left(), rect.center().y() - 1.5, rect.width(), 3))

    def _paint_smoke(self, p: QPainter) -> None:
        l = self.light
        colour = mix(rgb(60, 62, 70), rgb(225, 225, 228), l.daylight)
        for x, y, age, s in self._smoke:
            k = age / 7.0
            size = (14 + age * 22) * s
            p.setOpacity(max(0.0, 0.5 * (1 - k) * min(1, age * 3)))
            p.drawImage(QRectF(x - size / 2, y - size / 2, size, size), self._tinted_smoke(colour))
        p.setOpacity(1.0)

    def _tinted_smoke(self, colour: QColor) -> QImage:
        key = (colour.red() // 8, colour.green() // 8, colour.blue() // 8)
        if getattr(self, "_smoke_key", None) != key:
            self._smoke_key = key
            self._smoke_img = soft_blob(64, alpha(colour, 210))
        return self._smoke_img

    def _paint_foreground_trees(self, p: QPainter, cabin: bool) -> None:
        w = self.weather
        colour = self.lit(rgb(26, 64, 38))
        trees = [(70, 940, 760, 300, 1), (250, 960, 560, 220, 2)]
        if cabin:
            trees.append((1590, 950, 720, 270, 3))
        for x, base, h, width, seed in trees:
            sway = (0.4 + w.wind * 2.6) * wobble(self.t * (0.5 + w.wind * 0.7) + seed, 1.0, 1.7, 0.37)
            p.save()
            p.translate(x, base)
            p.rotate(sway)
            p.translate(-x, -base)
            draw_pine(p, x, base, h, width, colour, seed=seed, snow=w.snow_on_ground)
            p.restore()

    def _paint_fog(self, p: QPainter) -> None:
        w, l = self.weather, self.light
        if w.fog <= 0:
            return
        colour = mix(rgb(70, 76, 90), rgb(214, 218, 222), l.daylight)
        p.fillRect(QRectF(-200, 0, W + 400, H), vgrad(0, H, (0, alpha(colour, 70 * w.fog)), (0.55, alpha(colour, 150 * w.fog)), (1, alpha(colour, 110 * w.fog))))
        p.setOpacity(0.55 * w.fog)
        for i in range(6):
            x = ((self.t * (8 + i * 3) + i * 420) % (W + 1200)) - 700
            y = 360 + i * 70
            p.drawImage(QRectF(x, y - 90, 900, 180), self._fog_sprite)
        p.setOpacity(1.0)

    def _paint_precipitation(self, p: QPainter) -> None:
        w, l = self.weather, self.light
        if self._rain:
            drift = 1 if w.wind_from_west else -1
            lean = drift * (60 + w.wind * 420) / 1000
            colour = mix(rgb(120, 130, 150), rgb(200, 210, 225), l.daylight)
            p.setPen(QPen(alpha(colour, 120), 1.3))
            for x, y, _, length, _ in self._rain:
                p.drawLine(QPointF(x, y), QPointF(x - lean * length, y - length))
        if self._snow:
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(mix(rgb(170, 176, 196), rgb(255, 255, 255), l.daylight), 225))
            for x, y, _, size, _, _ in self._snow:
                p.drawEllipse(QPointF(x, y), size, size)


CABIN_WINDOWS = [QRectF(1022, 592, 50, 46), QRectF(1168, 592, 50, 46)]


def hill_points(base_y: float, amplitude: float, seed: int) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    phases = [rng.uniform(0, 6.3) for _ in range(4)]
    pts = []
    for i in range(0, 91):
        x = -200 + i * 22
        y = base_y
        for k, (f, a) in enumerate(((0.004, 1.0), (0.009, 0.5), (0.021, 0.25), (0.05, 0.08))):
            y -= amplitude * a * math.sin(x * f + phases[k])
        pts.append((x, y))
    return pts


def moon_shape(cx: float, cy: float, r: float, phase: float) -> QPainterPath:
    """The lit part of the moon for a phase (0 new .. 0.5 full .. 1 new),
    waxing lit on the right as seen from the northern hemisphere."""
    path = QPainterPath()
    waxing = phase < 0.5
    # The terminator is an ellipse whose half-width runs r..-r across each half.
    k = math.cos(2 * math.pi * phase)  # 1 new, -1 full
    steps = 40
    path.moveTo(cx, cy - r)
    side = 1 if waxing else -1
    for i in range(steps + 1):  # the bright limb
        a = -math.pi / 2 + math.pi * i / steps
        path.lineTo(cx + side * r * math.cos(a), cy + r * math.sin(a))
    for i in range(steps + 1):  # back up along the terminator
        a = math.pi / 2 - math.pi * i / steps
        path.lineTo(cx + side * r * k * math.cos(a), cy + r * math.sin(a))
    path.closeSubpath()
    return path
