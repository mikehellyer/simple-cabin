"""The view outside: the lodge among tall pines on the rocky shore of a
forest lake, under whatever the sky is really doing.

Drawn on the 1600×900 virtual canvas. The slow-changing parts (sky, hills,
lake, cabin) are cached as images and only redrawn when the light or the
weather changes; clouds, rain, snow, smoke, swaying trees and the lit
windows are drawn fresh every frame.
"""
from __future__ import annotations

import math
import random
import threading
from dataclasses import astuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from simple_cabin.core.sky import Light
from simple_cabin.core.weather import SceneWeather
from simple_cabin.gui.paint import H, W, alpha, mix, poly, radial, rgb, scaled, soft_blob, vgrad, wobble
from simple_cabin.gui.scenes import lodge
from simple_cabin.gui import textures as tx
from simple_cabin.gui.scenes.trees import draw_boulder, draw_fern, draw_ponderosa, draw_shrub, tint

HORIZON = 600.0  # the far shore, across the lake to the right
WATERLINE = 716.0  # where the near shore meets the water
REFLECT_SQUASH = 0.62  # reflections are drawn a little foreshortened
FULL = QRectF(0, 0, W, H)
# The part of the scene seen through the cabin's own windows: across the lake.
WINDOW_VIEW = QRectF(1150, 190, 600, 536)

CHIMNEY_TOP = lodge.CHIMNEY_TOP
# The near shore's edge on the right, as (y, x) points: land to the left.
SHORE_END = ((600, 1250), (630, 1330), (690, 1384), (716, 1412))


class OutsideScene:
    def __init__(self):
        self.weather = SceneWeather()
        self.light = Light(1.0, 0.0, 0.5, -1.0, False)
        self.moon_phase = 0.3
        self.fire_glow = 1.0  # set by the inside scene's fire, for the windows
        self.t = 0.0
        self._rng = random.Random(1)
        self._caches: dict = {}
        self._latest: dict = {}  # the newest layers for each view, shown while newer ones render
        self._rendering: set = set()
        self._lock = threading.Lock()
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
            round(l.daylight * 40) / 40, round(l.golden * 20) / 20, round(l.sun_progress, 2), round(l.night_progress, 2),
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
        if self.weather.frozen_lake or x < -50 or x > W + 50 or y < HORIZON:
            return False
        if y >= WATERLINE:
            return True
        return x > _shore_x(y)

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
        sky_img, land_img = self._layers(target, source, cabin, dpr, wait=True)

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

        if cabin:  # the glass, seen through holes cut in the land layer
            p.save()
            to_scene()
            lodge.paint_glass(p, self.light.daylight, self.sky_colours()[1], self.window_glow(), self.t)
            p.restore()
        p.drawImage(target.topLeft(), land_img)

        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_lake_life(p, cabin)
        if cabin:
            self._paint_lanterns(p)
            self._paint_smoke(p)
        self._paint_foreground_trees(p, cabin)
        self._paint_fog(p)
        self._paint_precipitation(p)
        p.restore()

        if self.lightning > 0:
            p.fillRect(target, rgb(225, 230, 255, 150 * self.lightning))
        p.restore()

    def prepare(self, target: QRectF, dpr: float, source: QRectF = FULL, cabin: bool = True) -> None:
        """Start rendering a view in the background if it isn't ready, so
        switching to it later doesn't stall (used while indoors)."""
        self._layers(target, source, cabin, dpr, wait=False)

    def _layers(self, target: QRectF, source: QRectF, cabin: bool, dpr: float, wait: bool):
        """The cached (sky, land) images for a view. If the light or weather
        has moved on, the previous images are returned while the new ones
        render in the background (it can take most of a second); only if
        there's nothing at all to show, and wait is set, is it rendered now."""
        scale = max(target.width() / source.width(), target.height() / source.height())
        view = (int(target.width()), int(target.height()), dpr, source.getRect(), cabin)
        key = view + (self._static_key(),)
        with self._lock:
            layers = self._caches.get(key)
            stale = self._latest.get(view)
        if layers is not None:
            return layers
        if stale is None and wait:
            return self._render_layers(key, view, QRectF(target), QRectF(source), scale, dpr, cabin)
        with self._lock:
            start = key not in self._rendering
            self._rendering.add(key)
        if start:
            threading.Thread(target=self._render_layers, daemon=True,
                             args=(key, view, QRectF(target), QRectF(source), scale, dpr, cabin)).start()
        return stale

    def _render_layers(self, key, view, target: QRectF, source: QRectF, scale: float, dpr: float, cabin: bool):
        layers = (self._render_layer(target, source, scale, dpr, sky=True, cabin=cabin),
                  self._render_layer(target, source, scale, dpr, sky=False, cabin=cabin))
        with self._lock:
            if len(self._caches) > 4:
                self._caches.clear()
            self._caches[key] = layers
            self._latest[view] = layers
            self._rendering.discard(key)
        return layers

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
        w = self.weather
        _, sky_bottom = self.sky_colours()
        light = self.lit(rgb(255, 255, 255))
        self._paint_hills(p, sky_bottom)
        self._paint_water(p, sky_bottom, light, cabin)
        self._paint_upper(p, cabin, light, sky_bottom)
        if cabin:
            p.save()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            for pane in lodge.GLASS:
                p.fillPath(pane, Qt.transparent)
            p.restore()
        self._paint_shore(p, light)

    def _paint_hills(self, p: QPainter, sky_bottom: QColor) -> None:
        """Forested hills across the lake, far then near."""
        w = self.weather
        far = mix(self.lit(rgb(84, 108, 124)), sky_bottom, 0.5 + w.fog * 0.4)
        near = mix(self.lit(rgb(30, 58, 44)), sky_bottom, 0.28 + w.fog * 0.5)
        p.setPen(Qt.NoPen)
        far_pts = hill_points(500, 60, 3)
        far_path = _ridge_path(far_pts, HORIZON + 4)
        p.setBrush(far)
        p.drawPath(far_path)
        if w.snow_on_ground or w.snow > 0:
            p.save()
            p.setClipPath(far_path)
            cap = mix(self.lit(rgb(235, 240, 248)), sky_bottom, 0.35)
            p.fillRect(QRectF(-200, 400, W + 400, 120), vgrad(400, 520, (0, cap), (0.5, alpha(cap, 200)), (1, alpha(cap, 0))))
            p.restore()
        # the nearer hill is covered in trees: a ragged, spiky top edge
        rng = random.Random(44)
        near_pts = []
        for x, y in hill_points(548, 34, 9):
            near_pts.append((x, y))
            near_pts.append((x + 11, y - rng.uniform(6, 18)))
        p.setBrush(near)
        p.drawPath(_ridge_path(near_pts, HORIZON + 4))
        p.setBrush(scaled(near, 0.82))
        p.drawRect(QRectF(-200, HORIZON - 8, W + 400, 12))

    def _paint_water(self, p: QPainter, sky_bottom: QColor, light: QColor, cabin: bool) -> None:
        w = self.weather
        if w.frozen_lake:
            top, bottom = mix(self.lit(rgb(196, 214, 226)), sky_bottom, 0.3), self.lit(rgb(150, 176, 196))
        else:
            top = mix(sky_bottom, self.lit(rgb(40, 70, 90)), 0.3)
            bottom = mix(self.lit(rgb(14, 30, 44)), sky_bottom, 0.15)
        water = QRectF(-200, HORIZON, W + 400, H - HORIZON + 300)
        p.fillRect(water, vgrad(HORIZON, H, top, bottom))
        strength = 0.18 if w.frozen_lake else 0.55 * (1 - w.rain * 0.4)
        # the far hills mirrored in the open water
        p.save()
        p.setClipRect(water)
        p.setOpacity(strength * 0.9)
        p.translate(0, 2 * HORIZON)
        p.scale(1, -1)
        self._paint_hills(p, sky_bottom)
        p.restore()
        # the shore, trees and lodge mirrored in the near water
        p.save()
        p.setClipRect(QRectF(-200, WATERLINE, W + 400, H))
        p.setOpacity(strength)
        p.translate(0, WATERLINE)
        p.scale(1, -REFLECT_SQUASH)
        p.translate(0, -WATERLINE)
        self._paint_upper(p, cabin, light, sky_bottom, reflection=True)
        p.restore()
        # ripples breaking up the reflections
        rng = random.Random(12)
        sheen = mix(sky_bottom, rgb(255, 255, 255), 0.25)
        dark = scaled(bottom, 0.7)
        y = HORIZON + 2
        while y < H + 10:
            depth = (y - HORIZON) / (H - HORIZON)
            x = rng.uniform(-200, 0)
            while x < W + 100:
                length = rng.uniform(20, 120) * (0.4 + depth)
                c = sheen if rng.random() < 0.5 else dark
                p.setPen(QPen(alpha(c, rng.uniform(12, 40)), 1 + depth * 1.4))
                p.drawLine(QPointF(x, y), QPointF(x + length, y))
                x += length + rng.uniform(40, 220)
            y += 3 + depth * 7 + rng.uniform(0, 3)
        p.setPen(Qt.NoPen)
        if w.frozen_lake:
            p.setPen(QPen(alpha(self.lit(rgb(240, 248, 255)), 120), 1.2))
            for _ in range(18):
                x0, y0 = rng.uniform(0, W), rng.uniform(WATERLINE + 20, H - 10)
                p.drawLine(QPointF(x0, y0), QPointF(x0 + rng.uniform(-120, 120), y0 + rng.uniform(-8, 8)))
            p.setPen(Qt.NoPen)
        p.fillRect(water, vgrad(HORIZON, H, (0, alpha(bottom, 0)), (0.5, alpha(bottom, 70)), (1, alpha(bottom, 170))))

    def _paint_upper(self, p: QPainter, cabin: bool, light: QColor, sky_bottom: QColor, reflection: bool = False) -> None:
        """Everything standing above the waterline: the forest, the shore,
        the lodge and the big pines in front of it."""
        w = self.weather
        snow = w.snow_on_ground
        haze = 0.14 + w.fog * 0.5
        dusk = (1 - self.light.daylight) * 0.5  # silhouettes as the light goes
        far_crown = mix(mix(self.lit(rgb(24, 48, 32)), sky_bottom, haze), rgb(8, 14, 12), dusk)
        far_trunk = mix(mix(self.lit(rgb(48, 36, 28)), sky_bottom, haze), rgb(8, 10, 10), dusk)
        # the forest behind the lodge
        rng = random.Random(61)
        x = -120.0
        while x < 1330:
            h = rng.uniform(520, 760)
            draw_ponderosa(p, x, 606, h, rng.uniform(9, 15), int(x) + 1000, far_crown, light, detail=False,
                           crown_frac=0.62, spread=1.1, snow=snow, trunk_colour=far_trunk)
            x += rng.uniform(38, 70)
        # a band of younger firs filling in at the bottom
        p.setBrush(scaled(far_crown, 0.9))
        x = -200.0
        while x < 1300:
            hgt = rng.uniform(60, 150)
            p.drawPolygon(poly((x - 24, 610), (x, 610 - hgt), (x + 24, 610)))
            x += rng.uniform(18, 34)

        # the near shore: a low rise of forest floor
        land = QPainterPath()
        land.moveTo(-200, 598)
        land.lineTo(1250, 600)
        for y, sx in SHORE_END:
            land.lineTo(sx, y)
        land.lineTo(-200, WATERLINE + 4)
        land.closeSubpath()
        if snow:
            ground = self.lit(rgb(232, 238, 246))
            p.setBrush(vgrad(598, WATERLINE, scaled(ground, 1.05), scaled(ground, 0.85)))
            p.drawPath(land)
        else:
            tx.draw_textured(p, land, tx.forest_floor(1620, 124), QPointF(0, 0))
            tint(p, land, light)
            p.setBrush(vgrad(598, WATERLINE, rgb(0, 0, 0, 90), rgb(0, 0, 0, 0)))
            p.drawPath(land)

        if cabin:
            lodge.paint_lodge(p, self.lit, light, snow)

        # big pines in front of the lodge
        crown = self.lit(rgb(34, 66, 40))
        trunk = self.lit(rgb(80, 56, 40))
        for x, base, h, tw, seed in ((376, 652, 920, 30, 7), (1196, 664, 860, 28, 9)):
            draw_ponderosa(p, x, base, h, tw, seed, crown, light, detail=not reflection, crown_frac=0.42,
                           spread=1.15, snow=snow, trunk_colour=trunk)

    def _paint_shore(self, p: QPainter, light: QColor) -> None:
        """Granite boulders along the water's edge, and ferns and shrubs."""
        snow = self.weather.snow_on_ground
        fern = self.lit(rgb(78, 112, 52)) if not snow else self.lit(rgb(200, 210, 200))
        shrub = self.lit(rgb(60, 92, 46)) if not snow else self.lit(rgb(220, 226, 232))
        rng = random.Random(71)
        # shrubs and ferns along the foundation and through the woods
        for i in range(64):
            x = rng.uniform(-40, 1380)
            y = rng.uniform(616, 696)
            if rng.random() < 0.55:
                draw_fern(p, x, y, rng.uniform(26, 48), 300 + i, fern)
            else:
                draw_shrub(p, x, y, rng.uniform(40, 80), rng.uniform(18, 34), 400 + i, shrub)
        # a line of boulders at the waterline, bigger ones nearer
        x = -40.0
        while x < 1400:
            rx = rng.uniform(16, 42)
            y = WATERLINE - rng.uniform(4, 12)
            if x > 1250:
                y = _shore_y(x) - 4
            draw_boulder(p, x, y, rx, rx * rng.uniform(0.45, 0.65), int(x) + 500, light, mossy=rng.random() < 0.3)
            if snow:
                p.setBrush(self.lit(rgb(240, 244, 250)))
                p.drawEllipse(QPointF(x - rx * 0.1, y - rx * 0.45), rx * 0.7, rx * 0.18)
            x += rx * rng.uniform(1.1, 1.7)
        for bx, by, rx, ry, seed in ((300, 712, 92, 42, 81), (968, 718, 70, 34, 83), (40, 722, 60, 30, 85)):
            draw_boulder(p, bx, by, rx, ry, seed, light, mossy=True)
            if snow:
                p.setBrush(self.lit(rgb(240, 244, 250)))
                p.drawEllipse(QPointF(bx - rx * 0.1, by - ry * 0.7), rx * 0.7, ry * 0.25)

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

    def window_glow(self) -> float:
        """0..1: how brightly the lodge's windows glow."""
        return max(0.0, min(1.0, (1 - self.light.daylight * 0.85))) * self.fire_glow

    def _paint_lake_life(self, p: QPainter, cabin: bool = True) -> None:
        l, w = self.light, self.weather
        if w.frozen_lake:
            return
        if cabin:
            self._paint_window_reflections(p)
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
                x = rng.uniform(0, W)
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

    def _paint_lanterns(self, p: QPainter) -> None:
        glow = self.window_glow()
        if glow < 0.15:
            return
        p.setPen(Qt.NoPen)
        for i, c in enumerate(lodge.LANTERNS):
            f = 0.9 + 0.1 * wobble(self.t * 3 + i, 1.7, 2.9)
            p.setBrush(radial(c.x(), c.y(), 70, (0, rgb(255, 200, 120, 150 * glow * f)), (0.3, rgb(255, 170, 80, 50 * glow)), (1, rgb(255, 160, 60, 0))))
            p.drawEllipse(c, 70, 70)
            p.setBrush(rgb(255, 226, 160, 255 * glow))
            p.drawRect(QRectF(c.x() - 4, c.y() - 8, 8, 14))

    def _paint_window_reflections(self, p: QPainter) -> None:
        """Columns of warm, shimmering light on the water under lit windows."""
        glow = self.window_glow()
        if glow < 0.1:
            return
        warm = rgb(255, 180, 90)
        p.save()
        p.setClipRect(QRectF(-200, WATERLINE + 2, W + 400, H))
        for pane in lodge.GLASS:
            r = pane.boundingRect()
            y0 = WATERLINE + (WATERLINE - r.bottom()) * REFLECT_SQUASH
            y1 = WATERLINE + (WATERLINE - r.top()) * REFLECT_SQUASH
            y = y0
            row = 0
            while y < min(y1, H):
                row += 1
                phase = (row * 7.3 + r.left() * 0.37) % 6.28
                shimmer = max(0.0, math.sin(self.t * 1.8 + phase) * 0.6 + math.sin(self.t * 3.1 + phase * 2) * 0.4)
                drift = 8 * math.sin(self.t * 1.3 + phase)
                inset = r.width() * (0.08 + 0.3 * ((row * 13) % 7) / 7)
                p.setPen(QPen(alpha(warm, 130 * glow * shimmer), 1.8))
                p.drawLine(QPointF(r.left() + inset + drift, y), QPointF(r.right() - inset * 0.6 + drift, y))
                y += 3 + (row % 3)
        for c in lodge.LANTERNS:
            y = WATERLINE + (WATERLINE - c.y()) * REFLECT_SQUASH
            for k in range(6):
                yy = y + k * 5
                wob = 6 * math.sin(self.t * 2.6 + k)
                p.setPen(QPen(alpha(warm, 120 * glow * (1 - k / 6)), 2))
                p.drawLine(QPointF(c.x() - 8 + wob, yy), QPointF(c.x() + 8 + wob, yy))
        p.restore()
        p.setPen(Qt.NoPen)

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

    FRAMING_TREES = ((1562, 940, 1080, 44, 13), (34, 930, 1120, 48, 11))  # x, base, height, trunk, seed

    def _paint_foreground_trees(self, p: QPainter, cabin: bool) -> None:
        """Tall pines framing the view, swaying in the wind. Each is drawn
        once into a sprite (they're detailed) and the sprite is rotated."""
        w = self.weather
        scale = p.transform().m22() * (p.device().devicePixelRatioF() if p.device() else 1.0)
        trees = self.FRAMING_TREES if cabin else ()  # (none in the view from indoors)
        for x, base, h, tw, seed in trees:
            sprite, box = self._tree_sprite(seed, h, tw, scale)
            sway = (0.15 + w.wind * 1.2) * wobble(self.t * (0.4 + w.wind * 0.6) + seed, 1.0, 1.7, 0.37)
            p.save()
            p.translate(x, base)
            p.rotate(sway)
            p.drawImage(box, sprite)
            p.restore()

    def _tree_sprite(self, seed: int, h: float, tw: float, scale: float):
        key = (seed, round(scale, 3), self._static_key())
        cache = getattr(self, "_sprites", {})
        if key not in cache:
            if len(cache) > 6:
                cache.clear()
            box = QRectF(-220, -h - 10, 440, h + 30)  # around the tree's foot at (0, 0)
            img = QImage(max(1, int(box.width() * scale)), max(1, int(box.height() * scale)), QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            sp = QPainter(img)
            sp.setRenderHint(QPainter.Antialiasing)
            sp.scale(scale, scale)
            sp.translate(-box.left(), -box.top())
            draw_ponderosa(sp, 0, 0, h, tw, seed, self.lit(rgb(30, 60, 36)), self.lit(rgb(255, 255, 255)), crown_frac=0.5,
                           spread=1.3, snow=self.weather.snow_on_ground, trunk_colour=self.lit(rgb(80, 56, 40)))
            sp.end()
            cache[key] = (img, box)
            self._sprites = cache
        return cache[key]

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


def _shore_x(y: float) -> float:
    """x of the near shore's right-hand edge at height y."""
    ys = [pt[0] for pt in SHORE_END]
    xs = [pt[1] for pt in SHORE_END]
    if y <= ys[0]:
        return xs[0]
    for (y0, x0), (y1, x1) in zip(SHORE_END, SHORE_END[1:]):
        if y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
    return xs[-1]


def _shore_y(x: float) -> float:
    for (y0, x0), (y1, x1) in zip(SHORE_END, SHORE_END[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * max(0.0, (x - x0)) / (x1 - x0)
    return WATERLINE


def _ridge_path(pts: list[tuple[float, float]], bottom: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(-200, bottom)
    for x, y in pts:
        path.lineTo(x, y)
    path.lineTo(W + 200, bottom)
    path.closeSubpath()
    return path


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
