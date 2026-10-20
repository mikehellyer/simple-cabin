"""Inside the cabin, after a timber lodge's great room: honey-pine walls,
heavy beams, the grandfather clock, a tall stone fireplace with a raised
hearth, a wall of picture windows onto the lake, a leather armchair, a
linen sofa, a chunky coffee table on a jute rug, and the dog asleep by the
fire.

Everything is lit by an overlay: daylight from the windows during the day,
then the fire, a floor lamp and candles as it gets dark.
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF, QTransform

from simple_cabin.gui import textures as tx
from simple_cabin.gui.paint import H, W, alpha, hgrad, mix, poly, radial, rgb, scaled, vgrad, wobble
from simple_cabin.gui.scenes import clock, decorations
from simple_cabin.gui.scenes.fire import Fire
from simple_cabin.gui.scenes.outside import WINDOW_VIEW, OutsideScene
from simple_cabin.gui.scenes.painting import canoe_painting

FLOOR_Y = 690.0
BEAM_Y = 112.0  # bottom of the big tie beam under the vaulted ceiling

# The picture windows: one continuous view, cut into panes by the frame.
WINDOW = QRectF(1066, 104, 560, 500)
PANES = [
    QRectF(1080, 118, 160, 66), QRectF(1252, 118, 160, 66), QRectF(1424, 118, 200, 66),  # transoms
    QRectF(1080, 198, 246, 392), QRectF(1340, 198, 284, 392),  # the two big panes
]

CHIMNEY = QRectF(470, -400, 530, FLOOR_Y + 400)
FIREBOX = QRectF(592, 468, 286, 182)
HEARTH_TOP = 650.0
HEARTH_FRONT = 736.0

LAMP = QPointF(1032, 356)  # centre of the floor lamp's shade
CANDLES = (QPointF(824, 270), QPointF(862, 282))
TABLE_CANDLE = QPointF(986, 628)
DOG = QPointF(548, 748)  # roughly the middle of the sleeping dog


def fit_scale(target: QRectF, width: float = W, height: float = H) -> float:
    """Fill the target, but never crop away more than an eighth of the
    scene's width (on squarer windows the top and bottom extend instead)."""
    s = max(target.width() / width, target.height() / height)
    return min(s, target.width() / (width * 0.875))


def firebox_path() -> QPainterPath:
    path = QPainterPath()
    path.addRect(FIREBOX)
    return path


class InsideScene:
    def __init__(self, outside: OutsideScene):
        self.outside = outside
        self.fire = Fire(FIREBOX.center().x(), FIREBOX.bottom() - 16, 210)
        self.t = 0.0
        self.decoration: str | None = None  # seasonal decorations (see core.seasons)
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
        want = int(rain * 110)
        rng = self._rng
        g = WINDOW

        def fresh() -> list[float]:
            # x, y, radius, speed (0 = clinging), age
            return [rng.uniform(g.left(), g.right()), rng.uniform(g.top(), g.bottom()), rng.uniform(1.5, 4), 0.0, 0.0]

        while len(self._drops) < want:
            self._drops.append(fresh())
        del self._drops[want:]
        for d in self._drops:
            d[4] += dt
            if d[3] == 0 and d[2] > 3.2 and rng.random() < dt * 0.4:
                d[3] = rng.uniform(25, 70)  # heavy enough to run
            d[1] += d[3] * dt
            if d[1] > g.bottom() + 5 or d[4] > 25:
                d[:] = fresh()

    def lamp_on(self) -> bool:
        l = self.outside.light
        return l.daylight < 0.55 or (l.daylight < 0.8 and self.outside.weather.clouds > 0.85)

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
        # 1. the view through the windows
        view = QRectF(ox + WINDOW.x() * s, oy + WINDOW.y() * s, WINDOW.width() * s, WINDOW.height() * s)
        p.fillRect(view, rgb(0, 0, 0))
        self.outside.paint(p, view, WINDOW_VIEW, cabin=False)
        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_glass(p)
        p.restore()

        # 2. the room (cached), with holes where the glass is
        dpr = p.device().devicePixelRatioF() if p.device() else 1.0
        p.drawImage(target.topLeft(), self.prerender(target, dpr))

        # 3. things that move
        p.save()
        to_scene()
        p.setRenderHint(QPainter.Antialiasing)
        p.save()
        p.setClipPath(firebox_path())
        self.fire.paint(p)
        p.restore()
        self._paint_small_flames(p)
        decorations.inside_dynamic(p, self.decoration, self.t)
        self._paint_dog(p)
        clock.paint_moving(p, now, now_seconds, glow=self.fire.flicker() * (1 - self.outside.light.daylight * 0.8))
        p.restore()

        # 4. light and shade
        self._paint_lighting(p, target, s, ox, oy)
        p.restore()

    def prerender(self, target: QRectF, dpr: float) -> QImage:
        """The room's cached image for this size, rendering it if need be
        (safe to call from a background thread while nothing else paints)."""
        key = (int(target.width()), int(target.height()), dpr, round(self.outside.moon_phase, 3), self.decoration)
        if key != self._cache_key:
            s = fit_scale(target)
            ox = (target.width() - W * s) / 2
            oy = (target.height() - H * s) / 2
            self._cache = self._render_room(target, s, ox, oy, dpr)
            self._cache_key = key
        return self._cache

    def prepare_window_view(self, target: QRectF, dpr: float) -> None:
        """Render the view through the windows now (for the loading screen)."""
        s = fit_scale(target)
        view = QRectF(WINDOW.x() * s, WINDOW.y() * s, WINDOW.width() * s, WINDOW.height() * s)
        self.outside._layers(view, WINDOW_VIEW, False, dpr, wait=True)

    def _render_room(self, target: QRectF, s: float, ox: float, oy: float, dpr: float) -> QImage:
        img = QImage(int(target.width() * dpr), int(target.height() * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.translate(ox, oy)
        p.scale(s, s)
        self._paint_walls(p)
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        for pane in PANES:
            p.fillRect(pane, Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        self._paint_window_frame(p)
        self._paint_floor(p)
        self._paint_fireplace(p)
        decorations.inside_static(p, self.decoration, "mantel")
        self._paint_lamp(p)
        if not decorations.hides_armchair(self.decoration):
            self._paint_armchair(p)
        decorations.inside_static(p, self.decoration, "back")
        self._paint_rug(p)
        self._paint_log_bucket(p)
        self._paint_coffee_table(p)
        decorations.inside_static(p, self.decoration, "table")
        self._paint_sofa(p)
        clock.paint_case(p, self.outside.moon_phase)
        p.end()
        return img

    # --- the room

    def _paint_walls(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        # honey-pine plank walls (extended well past the canvas for squarer windows)
        wall = QRectF(-200, -400, W + 400, FLOOR_Y + 400)
        p.drawImage(wall.topLeft(), tx.wood(int(wall.width()), int(wall.height()), 40, True, "pine", 9))
        tx.shade_rect(p, QRectF(-200, BEAM_Y, W + 400, FLOOR_Y - BEAM_Y), top=0.35, bottom=0.2)

        # vaulted ceiling above the tie beam: darker boards and sloping rafters
        ceiling = QRectF(-200, -400, W + 400, 400 + BEAM_Y)
        p.drawImage(ceiling.topLeft(), tx.wood(int(ceiling.width()), int(ceiling.height()), 30, False, "cedar", 13))
        p.fillRect(ceiling, rgb(30, 14, 4, 110))
        # sloping rafters, rising away to the ridge
        for x0 in (-60, 260, 580, 900, 1220, 1540):
            lean = (x0 - W / 2) * 0.5
            pts = ((x0, BEAM_Y), (x0 + 50, BEAM_Y), (x0 + 50 + lean, -300), (x0 + lean, -300))
            p.setBrush(hgrad(x0, x0 + 50, rgb(96, 62, 36), rgb(150, 104, 64), rgb(120, 80, 46), rgb(70, 44, 24)))
            p.drawPolygon(poly(*pts))
            p.setBrush(rgb(0, 0, 0, 70))
            p.drawPolygon(poly((x0 + 50, BEAM_Y), (x0 + 58, BEAM_Y), (x0 + 58 + lean, -300), (x0 + 50 + lean, -300)))
        # the tie beam
        beam = QRectF(-200, BEAM_Y - 44, W + 400, 48)
        p.drawImage(beam.topLeft(), tx.wood(int(beam.width()), 48, 400, True, "weathered", 19, seams=False, rough=0.35))
        tx.shade_rect(p, beam, top=0.0, bottom=0.45)
        p.fillRect(QRectF(-200, BEAM_Y + 4, W + 400, 10), vgrad(BEAM_Y + 4, BEAM_Y + 14, rgb(0, 0, 0, 90), rgb(0, 0, 0, 0)))

        # heavy timber post between the fireplace and the windows, with knee braces
        post = QRectF(1010, BEAM_Y, 52, FLOOR_Y - BEAM_Y)
        p.drawImage(post.topLeft(), tx.wood(52, int(post.height()), 200, False, "weathered", 23, seams=False, rough=0.3))
        tx.shade_rect(p, post, left=0.25, right=0.5)
        for side in (-1, 1):
            brace = QPainterPath()
            bx = post.left() if side < 0 else post.right()
            brace.moveTo(bx, BEAM_Y + 70)
            brace.lineTo(bx, BEAM_Y + 96)
            brace.lineTo(bx + side * 96, BEAM_Y)
            brace.lineTo(bx + side * 70, BEAM_Y)
            brace.closeSubpath()
            p.setBrush(vgrad(BEAM_Y, BEAM_Y + 96, rgb(150, 104, 64), rgb(104, 68, 40)))
            p.drawPath(brace)
        # skirting
        p.fillRect(QRectF(-200, FLOOR_Y - 14, W + 400, 16), vgrad(FLOOR_Y - 14, FLOOR_Y + 2, rgb(120, 76, 40), rgb(60, 36, 18)))

    def _paint_window_frame(self, p: QPainter) -> None:
        frame = QPainterPath()
        frame.setFillRule(Qt.OddEvenFill)
        frame.addRect(WINDOW.adjusted(-14, -14, 40, 14))
        for pane in PANES:
            frame.addRect(pane)
        tex = tx.wood(int(WINDOW.width()) + 60, int(WINDOW.height()) + 30, 300, False, "cedar", 29, seams=False)
        tx.draw_textured(p, frame, tex, QPointF(0, 0))
        # bevelled edges round each pane
        p.setBrush(Qt.NoBrush)
        for pane in PANES:
            p.setPen(QPen(rgb(60, 32, 14, 180), 3))
            p.drawLine(pane.topLeft(), pane.topRight())
            p.drawLine(pane.topLeft(), pane.bottomLeft())
            p.setPen(QPen(rgb(255, 220, 170, 60), 2))
            p.drawLine(pane.bottomLeft() + QPointF(0, 1), pane.bottomRight() + QPointF(0, 1))
        p.setPen(Qt.NoPen)
        # a deep sill
        sill = QRectF(WINDOW.left() - 24, WINDOW.bottom() + 10, WINDOW.width() + 60, 18)
        p.drawImage(sill.topLeft(), tx.wood(int(sill.width()), 18, 300, True, "cedar", 31, seams=False))
        tx.shade_rect(p, sill, top=0.0, bottom=0.45)

    def _paint_floor(self, p: QPainter) -> None:
        # wide oak boards running away from us, laid in true perspective
        boards = tx.wood(1400, 1000, 70, False, "oak", 37)
        vx, vy = W / 2, 250.0  # vanishing point
        back_half = 1300.0
        front_y = H + 260
        front_half = back_half * (front_y - vy) / (FLOOR_Y - vy)
        quad = QPolygonF([QPointF(vx - back_half, FLOOR_Y), QPointF(vx + back_half, FLOOR_Y),
                          QPointF(vx + front_half, front_y), QPointF(vx - front_half, front_y)])
        src = QPolygonF([QPointF(0, 0), QPointF(boards.width(), 0), QPointF(boards.width(), boards.height()), QPointF(0, boards.height())])
        mapping = QTransform()
        QTransform.quadToQuad(src, quad, mapping)
        p.save()
        p.setClipRect(QRectF(-200, FLOOR_Y, W + 400, 700))
        p.setTransform(mapping, True)
        p.drawImage(QPointF(0, 0), boards)
        p.restore()
        p.fillRect(QRectF(-200, FLOOR_Y, W + 400, 700), vgrad(FLOOR_Y, H, (0, rgb(20, 10, 4, 160)), (0.35, rgb(20, 10, 4, 50)), (1, rgb(0, 0, 0, 0))))

    def _paint_fireplace(self, p: QPainter) -> None:
        c = CHIMNEY
        p.setPen(Qt.NoPen)
        # the stone chimney breast, rising through the ceiling
        stone = tx.stone_wall(int(c.width()), int(c.height()), 12)
        p.drawImage(c.topLeft(), stone)
        tx.shade_rect(p, c, left=0.35, right=0.45)
        p.fillRect(QRectF(c.right(), BEAM_Y, 14, FLOOR_Y - BEAM_Y), hgrad(c.right(), c.right() + 14, rgb(0, 0, 0, 90), rgb(0, 0, 0, 0)))

        # firebox: black iron surround, brick-lined, sooty at the top
        fb = FIREBOX
        p.setBrush(vgrad(fb.top() - 14, fb.bottom(), rgb(40, 38, 36), rgb(18, 16, 15)))
        p.drawRect(fb.adjusted(-14, -14, 14, 0))
        p.fillRect(fb, rgb(36, 18, 10))
        p.save()
        p.setClipRect(fb)
        # firebricks: the back wall, then the angled sides
        for row, y in enumerate(range(int(fb.top()), int(fb.bottom()), 15)):
            off = 0 if row % 2 else 20
            for x in range(int(fb.left()) - off, int(fb.right()), 40):
                b = QRectF(x + 1, y + 1, 38, 13)
                tone = 0.75 + 0.25 * ((x * 7 + y * 13) % 11) / 10
                p.setBrush(rgb(120 * tone, 56 * tone, 32 * tone))
                p.drawRect(b)
        for side in (-1, 1):
            x = fb.left() if side < 0 else fb.right()
            p.setBrush(rgb(20, 10, 6, 150))
            p.drawPolygon(poly((x, fb.top()), (x - side * 48, fb.top() + 40), (x - side * 48, fb.bottom()), (x, fb.bottom())))
        p.fillRect(fb, vgrad(fb.top(), fb.bottom(), (0, rgb(0, 0, 0, 230)), (0.45, rgb(0, 0, 0, 90)), (1, rgb(0, 0, 0, 40))))
        # andirons / grate
        p.setPen(QPen(rgb(26, 24, 22), 4))
        p.drawLine(QPointF(fb.left() + 60, fb.bottom() - 12), QPointF(fb.right() - 60, fb.bottom() - 12))
        for x in (fb.left() + 70, fb.right() - 70):
            p.drawLine(QPointF(x, fb.bottom() - 30), QPointF(x, fb.bottom()))
        p.setPen(Qt.NoPen)
        p.restore()

        # raised stone hearth: a slab on top, stone face below
        top = QRectF(c.left() - 16, HEARTH_TOP, c.width() + 32, 16)
        face = QRectF(c.left() - 16, HEARTH_TOP + 16, c.width() + 32, HEARTH_FRONT - HEARTH_TOP - 16)
        p.drawImage(face.topLeft(), tx.stone_wall(int(face.width()), int(face.height()), 15, 0.8))
        tx.shade_rect(p, face, top=0.25, bottom=0.2, left=0.2, right=0.3)
        p.drawImage(top.topLeft(), tx.stone_wall(int(top.width()), 16, 16, 2.5))
        p.setBrush(vgrad(top.top(), top.bottom(), rgb(255, 240, 220, 60), rgb(0, 0, 0, 40)))
        p.drawRect(top)
        p.fillRect(QRectF(face.left(), face.bottom(), face.width(), 12), vgrad(face.bottom(), face.bottom() + 12, rgb(0, 0, 0, 110), rgb(0, 0, 0, 0)))
        # fire tools on the hearth
        tools_x = fb.right() + 66
        p.setBrush(rgb(24, 22, 20))
        p.drawRect(QRectF(tools_x - 2, 520, 4, HEARTH_TOP - 520))
        p.drawEllipse(QPointF(tools_x, 516), 6, 6)
        p.drawRect(QRectF(tools_x - 16, HEARTH_TOP - 4, 32, 4))
        p.setPen(QPen(rgb(24, 22, 20), 2.4))
        for dx, top_y in ((-10, 548), (10, 540), (-4, 552)):
            p.drawLine(QPointF(tools_x + dx * 0.3, 534), QPointF(tools_x + dx, HEARTH_TOP - 8))
        p.setPen(Qt.NoPen)

        # the mantel: a rough-hewn beam on chunky corbels
        mantel = QRectF(c.left() - 20, 366, c.width() + 40, 42)
        for x in (mantel.left() + 34, mantel.right() - 74):
            corbel = QPainterPath()
            corbel.moveTo(x, mantel.bottom())
            corbel.lineTo(x + 40, mantel.bottom())
            corbel.lineTo(x + 40, mantel.bottom() + 16)
            corbel.quadTo(x + 20, mantel.bottom() + 18, x + 12, mantel.bottom() + 40)
            corbel.lineTo(x, mantel.bottom() + 40)
            corbel.closeSubpath()
            tx.draw_textured(p, corbel, tx.wood(44, 44, 200, False, "weathered", 41, seams=False, rough=0.4))
            p.setBrush(rgb(0, 0, 0, 70))
            p.drawRect(QRectF(x + 30, mantel.bottom(), 10, 40))
        p.drawImage(mantel.topLeft(), tx.wood(int(mantel.width()), 42, 400, True, "weathered", 43, seams=False, rough=0.5))
        tx.shade_rect(p, mantel, top=0.0, bottom=0.5)
        p.setBrush(rgb(255, 230, 200, 50))
        p.drawRect(QRectF(mantel.left(), mantel.top(), mantel.width(), 3))
        p.fillRect(QRectF(mantel.left(), mantel.bottom(), mantel.width(), 14), vgrad(mantel.bottom(), mantel.bottom() + 14, rgb(0, 0, 0, 120), rgb(0, 0, 0, 0)))

        self._paint_mantel_things(p, mantel.top())

    def _paint_mantel_things(self, p: QPainter, shelf: float) -> None:
        p.setPen(Qt.NoPen)
        # a framed painting of a canoe trip, leaning against the stone
        frame = QRectF(566, 166, 244, shelf - 166)
        p.setBrush(rgb(0, 0, 0, 100))
        p.drawRect(frame.translated(7, 5))
        p.drawImage(frame.topLeft(), tx.wood(int(frame.width()), int(frame.height()), 400, True, "walnut", 131, seams=False))
        tx.shade_rect(p, frame, top=0.1, bottom=0.35, left=0.15, right=0.3)
        lip = frame.adjusted(12, 12, -12, -12)
        p.setBrush(vgrad(lip.top(), lip.bottom(), rgb(236, 200, 120), rgb(150, 110, 46)))
        p.drawRect(lip)
        pic = lip.adjusted(4, 4, -4, -4)
        p.drawImage(pic, canoe_painting())
        p.setBrush(vgrad(pic.top(), pic.bottom(), rgb(255, 255, 255, 18), rgb(0, 0, 0, 30)))  # a little glazing sheen
        p.drawRect(pic)

        # an iron pot with greenery, and a stoneware bowl
        p.setBrush(radial(500, 330, 34, rgb(110, 100, 86), rgb(52, 46, 40)))
        pot = QPainterPath()
        pot.moveTo(484, shelf)
        pot.cubicTo(470, 344, 478, 320, 492, 316)
        pot.lineTo(530, 316)
        pot.cubicTo(544, 320, 552, 344, 538, shelf)
        pot.closeSubpath()
        p.drawPath(pot)
        rng = random.Random(53)
        for i in range(22):
            a = math.radians(rng.uniform(-75, 75))
            length = rng.uniform(40, 96)
            base = QPointF(511 + rng.uniform(-10, 10), 318)
            tip = QPointF(base.x() + math.sin(a) * length, base.y() - math.cos(a) * length * 0.9)
            p.setPen(QPen(rgb(70, 86, 46), 1.4))
            p.drawLine(base, tip)
            p.setPen(Qt.NoPen)
            for k in range(1, 6):
                lp = QPointF(base.x() + (tip.x() - base.x()) * k / 6, base.y() + (tip.y() - base.y()) * k / 6)
                p.setBrush(rgb(rng.randint(70, 110), rng.randint(100, 130), rng.randint(56, 70)))
                p.drawEllipse(lp, 4, 2.2)
        p.setBrush(vgrad(shelf - 22, shelf, rgb(170, 150, 120), rgb(110, 92, 72)))
        p.drawChord(QRectF(548, shelf - 40, 52, 40), 180 * 16, 180 * 16)

        # tall iron candlesticks (the flames are drawn per frame)
        for c in CANDLES:
            p.setBrush(rgb(30, 28, 26))
            p.drawEllipse(QPointF(c.x(), shelf - 3), 13, 4)
            p.drawRect(QRectF(c.x() - 2.5, c.y() + 46, 5, shelf - c.y() - 46))
            p.drawEllipse(QPointF(c.x(), c.y() + 72), 6, 4)
            p.drawEllipse(QPointF(c.x(), c.y() + 48), 9, 3.5)
            p.setBrush(hgrad(c.x() - 7, c.x() + 7, rgb(250, 244, 226), rgb(236, 228, 206), rgb(200, 190, 166)))
            p.drawRect(QRectF(c.x() - 6, c.y() + 6, 12, 40))
            p.setPen(QPen(rgb(40, 30, 20), 1.2))
            p.drawLine(QPointF(c.x(), c.y() + 6), QPointF(c.x(), c.y() + 1))
            p.setPen(Qt.NoPen)
        # a little brass pot
        p.setBrush(radial(916, 340, 26, rgb(240, 200, 120), rgb(160, 110, 40), rgb(90, 60, 20)))
        p.drawEllipse(QRectF(896, 336, 40, 30))
        p.drawRect(QRectF(906, 330, 20, 8))

    def _paint_lamp(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        x = LAMP.x()
        p.setBrush(rgb(30, 26, 22))
        p.drawEllipse(QPointF(x, FLOOR_Y + 6), 26, 6)
        p.drawRect(QRectF(x - 2.5, LAMP.y() + 30, 5, FLOOR_Y + 4 - LAMP.y() - 30))
        shade = QPainterPath()
        shade.moveTo(x - 30, LAMP.y() - 32)
        shade.lineTo(x + 30, LAMP.y() - 32)
        shade.lineTo(x + 40, LAMP.y() + 32)
        shade.lineTo(x - 40, LAMP.y() + 32)
        shade.closeSubpath()
        tx.draw_textured(p, shade, tx.fabric(90, 70, (228, 214, 186), 61))
        tx.shade_rect(p, shade.boundingRect(), left=0.2, right=0.35)

    def _paint_armchair(self, p: QPainter) -> None:
        """A leather club chair by the window, turned a little towards the fire."""
        leather = rgb(118, 58, 30)
        dark = scaled(leather, 0.5)
        hi = scaled(leather, 1.45)
        p.setPen(Qt.NoPen)
        p.setBrush(radial(1206, 748, 150, (0, rgb(0, 0, 0, 110)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(QPointF(1206, 748), 150, 20)
        p.setBrush(rgb(46, 28, 16))
        for x in (1104, 1300):
            p.drawRect(QRectF(x, 718, 12, 30))
        # the barrel back
        back = QPainterPath()
        back.moveTo(1112, 640)
        back.cubicTo(1108, 572, 1124, 520, 1166, 512)
        back.cubicTo(1200, 506, 1236, 506, 1262, 512)
        back.cubicTo(1300, 520, 1314, 572, 1310, 640)
        back.closeSubpath()
        p.setBrush(radial(1190, 540, 160, (0, hi), (0.5, leather), (1, dark)))
        p.drawPath(back)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(alpha(dark, 120), 1.4))
        p.drawPath(back.translated(0, 10))
        p.setPen(Qt.NoPen)
        # seat cushion and the front skirt
        p.setBrush(vgrad(660, 724, leather, dark))
        p.drawRoundedRect(QRectF(1132, 664, 160, 60), 10, 10)
        p.setBrush(radial(1200, 640, 120, (0, hi), (0.7, leather), (1, scaled(leather, 0.8))))
        p.drawRoundedRect(QRectF(1136, 632, 152, 40), 16, 16)
        # rolled arms, front faces towards us
        for x0 in (1092, 1272):
            arm = QRectF(x0, 588, 52, 136)
            p.setBrush(hgrad(arm.left(), arm.right(), scaled(leather, 0.7), hi, leather, dark))
            p.drawRoundedRect(arm, 20, 20)
            p.setBrush(radial(arm.center().x() - 6, arm.top() + 14, 30, (0, hi), (1, leather)))
            p.drawEllipse(QPointF(arm.center().x(), arm.top() + 18), 25, 20)
            p.setBrush(alpha(dark, 120))
            p.drawEllipse(QPointF(arm.center().x(), arm.top() + 18), 10, 8)
            # brass nailheads down the front of the arm
            p.setBrush(rgb(200, 160, 90))
            for y in range(604, 718, 10):
                p.drawEllipse(QPointF(arm.left() + 6, y), 1.4, 1.4)
        # an olive cushion against the back
        cushion = QPainterPath()
        cushion.moveTo(1156, 636)
        cushion.cubicTo(1150, 600, 1160, 566, 1176, 560)
        cushion.cubicTo(1210, 552, 1246, 554, 1258, 562)
        cushion.cubicTo(1270, 590, 1268, 616, 1262, 638)
        cushion.closeSubpath()
        tx.draw_textured(p, cushion, tx.fabric(130, 90, (128, 132, 92), 63))
        tx.shade_rect(p, cushion.boundingRect(), top=0.0, bottom=0.4, left=0.2, right=0.3)

    def _paint_rug(self, p: QPainter) -> None:
        rug = QPainterPath()
        rug.moveTo(330, 712)
        rug.lineTo(1260, 712)
        rug.lineTo(1450, H + 20)
        rug.lineTo(120, H + 20)
        rug.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 70))
        p.drawPath(rug.translated(0, 6))
        tx.draw_textured(p, rug, tx.jute(1340, 220, 71))
        tx.shade_rect(p, rug.boundingRect(), top=0.35, bottom=0.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgb(120, 92, 60), 4))
        p.drawPath(rug)
        p.setPen(Qt.NoPen)

    def _paint_log_bucket(self, p: QPainter) -> None:
        p.setPen(Qt.NoPen)
        rng = random.Random(81)
        for i in range(6):  # split logs standing up
            x = 404 + i * 10 + rng.uniform(-2, 2)
            top = 586 + rng.uniform(-10, 8)
            p.setBrush(vgrad(top, 640, rgb(196, 160, 112), rgb(140, 100, 60)))
            p.drawPolygon(poly((x - 6, 640), (x - 4, top + 6), (x + 2, top), (x + 8, top + 4), (x + 7, 640)))
        bucket = QPainterPath()
        bucket.moveTo(392, 618)
        bucket.lineTo(470, 618)
        bucket.lineTo(464, 690)
        bucket.lineTo(398, 690)
        bucket.closeSubpath()
        p.setBrush(hgrad(392, 470, rgb(90, 70, 50), rgb(170, 130, 90), rgb(120, 92, 64), rgb(60, 46, 34)))
        p.drawPath(bucket)
        p.setPen(QPen(rgb(50, 38, 28), 2))
        for y in (626, 682):
            p.drawLine(QPointF(394, y), QPointF(468, y))
        p.setPen(Qt.NoPen)

    def _paint_coffee_table(self, p: QPainter) -> None:
        top = poly((680, 640), (1130, 640), (1166, 690), (646, 690))
        front = QRectF(646, 690, 520, 34)
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 90))
        p.drawEllipse(QPointF(906, 838), 300, 24)
        # chunky block legs
        for x in (668, 1094):
            leg = QRectF(x, 720, 54, 112)
            p.drawImage(leg.topLeft(), tx.wood(54, 112, 27, False, "weathered", 91 + x, rough=0.3))
            tx.shade_rect(p, leg, top=0.4, left=0.2, right=0.45)
        p.setBrush(rgb(40, 24, 12, 200))
        p.drawRect(QRectF(722, 722, 372, 50))
        # the top: thick reclaimed planks
        top_path = QPainterPath()
        top_path.addPolygon(top)
        tx.draw_textured(p, top_path, tx.wood(530, 52, 13, True, "weathered", 93, rough=0.35))
        p.setBrush(vgrad(640, 690, rgb(255, 230, 190, 30), rgb(0, 0, 0, 30)))
        p.drawPolygon(top)
        p.drawImage(front.topLeft(), tx.wood(520, 34, 17, True, "weathered", 95, rough=0.35))
        tx.shade_rect(p, front, top=0.1, bottom=0.45)
        p.fillRect(QRectF(front.left(), front.top(), front.width(), 2), rgb(255, 230, 190, 60))

        # on the table: a wooden tray with bowls, books, a jar candle, greenery
        p.setBrush(vgrad(650, 672, rgb(130, 86, 48), rgb(84, 52, 28)))
        p.drawEllipse(QRectF(720, 648, 130, 26))
        p.setBrush(rgb(150, 110, 70))
        p.drawEllipse(QRectF(740, 648, 46, 16))
        p.drawEllipse(QRectF(792, 652, 38, 13))
        for i, (colour, h) in enumerate(((rgb(60, 66, 74), 9), (rgb(220, 214, 196), 8), (rgb(70, 58, 46), 9))):
            y = 676 - i * 9
            p.setBrush(colour)
            p.drawPolygon(poly((930 + i * 3, y), (1040 - i * 2, y), (1044 - i * 2, y - h), (934 + i * 3, y - h)))
            p.setBrush(rgb(236, 230, 214))
            p.drawRect(QRectF(1036 - i * 2, y - h + 2, 4, h - 3))
        p.setBrush(hgrad(970, 1002, rgb(240, 232, 214), rgb(255, 250, 238), rgb(214, 204, 184)))
        p.drawRect(QRectF(TABLE_CANDLE.x() - 15, TABLE_CANDLE.y() + 6, 30, 26))
        p.setBrush(rgb(255, 238, 200, 160))
        p.drawEllipse(QRectF(TABLE_CANDLE.x() - 15, TABLE_CANDLE.y() + 2, 30, 8))
        # a stoneware jug with a few sprigs
        p.setBrush(radial(884, 640, 26, rgb(150, 140, 120), rgb(84, 76, 64)))
        p.drawEllipse(QRectF(866, 622, 40, 46))
        rng = random.Random(97)
        for i in range(12):
            a = math.radians(rng.uniform(-60, 60))
            length = rng.uniform(26, 56)
            base = QPointF(886, 626)
            tip = QPointF(base.x() + math.sin(a) * length, base.y() - math.cos(a) * length)
            p.setPen(QPen(rgb(80, 96, 50), 1.2))
            p.drawLine(base, tip)
            p.setPen(Qt.NoPen)
            p.setBrush(rgb(96, 118, 62))
            for k in range(1, 5):
                p.drawEllipse(QPointF(base.x() + (tip.x() - base.x()) * k / 5, base.y() + (tip.y() - base.y()) * k / 5), 3.2, 1.8)

    def _paint_sofa(self, p: QPainter) -> None:
        """A linen sofa in the foreground, its back towards us, with cushions
        peeking over and a chunky knit throw over the end."""
        linen = tx.fabric(560, 320, (224, 214, 194), 101)
        p.setPen(Qt.NoPen)
        # cushions leaning against the back, seen over its top
        for x0, w, colour, seed, knitted in ((1290, 120, (150, 64, 40), 111, True), (1398, 116, (118, 124, 80), 113, False),
                                              (1500, 130, (168, 128, 86), 115, False)):
            top = 668 - (x0 - 1290) * 0.12
            cushion = QPainterPath()
            cushion.moveTo(x0, top + 70)
            cushion.cubicTo(x0 - 6, top + 20, x0 + 10, top - 6, x0 + w * 0.5, top - 4)
            cushion.cubicTo(x0 + w - 10, top - 6, x0 + w + 6, top + 20, x0 + w, top + 70)
            cushion.closeSubpath()
            tex = tx.knit(w + 10, 90, colour, seed) if knitted else tx.fabric(w + 10, 90, colour, seed)
            tx.draw_textured(p, cushion, tex)
            tx.shade_rect(p, cushion.boundingRect(), top=0.0, bottom=0.5, left=0.2, right=0.35)
        # the back: a long, softly rounded shape running off to the right
        back = QPainterPath()
        back.moveTo(1190, H + 20)
        back.lineTo(1196, 744)
        back.cubicTo(1200, 718, 1230, 706, 1290, 704)
        back.cubicTo(1420, 696, 1560, 682, 1660, 676)
        back.lineTo(1660, H + 20)
        back.closeSubpath()
        tx.draw_textured(p, back, linen)
        p.setBrush(vgrad(676, H, (0, rgb(255, 250, 240, 70)), (0.12, rgb(255, 250, 240, 0)), (0.6, rgb(0, 0, 0, 40)), (1, rgb(0, 0, 0, 110))))
        p.drawPath(back)
        # piping along the top edge
        top_edge = QPainterPath(QPointF(1196, 744))
        top_edge.cubicTo(1200, 718, 1230, 706, 1290, 704)
        top_edge.cubicTo(1420, 696, 1560, 682, 1660, 676)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rgb(176, 166, 146), 3))
        p.drawPath(top_edge.translated(0, 6))
        p.setPen(Qt.NoPen)
        # the rolled arm at the near end
        arm = QPainterPath()
        arm.moveTo(1150, H + 20)
        arm.lineTo(1150, 736)
        arm.cubicTo(1150, 700, 1200, 690, 1226, 704)
        arm.cubicTo(1246, 716, 1246, 740, 1240, 760)
        arm.lineTo(1240, H + 20)
        arm.closeSubpath()
        tx.draw_textured(p, arm, linen, QPointF(30, 0))
        p.setBrush(hgrad(1150, 1244, (0, rgb(255, 250, 240, 60)), (0.5, rgb(0, 0, 0, 0)), (1, rgb(0, 0, 0, 90))))
        p.drawPath(arm)
        p.setBrush(radial(1196, 714, 40, (0, rgb(255, 252, 244, 110)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(QPointF(1196, 716), 36, 20)
        # a chunky rust knit throw over the back, falling towards us
        throw = QPainterPath()
        throw.moveTo(1268, 712)
        throw.cubicTo(1300, 690, 1380, 688, 1420, 698)
        throw.cubicTo(1430, 760, 1418, 840, 1440, H + 20)
        throw.lineTo(1262, H + 20)
        throw.cubicTo(1276, 840, 1256, 760, 1268, 712)
        throw.closeSubpath()
        tx.draw_textured(p, throw, tx.knit(190, 230, (152, 58, 34), 117))
        p.setBrush(hgrad(1256, 1440, (0, rgb(0, 0, 0, 90)), (0.3, rgb(0, 0, 0, 0)), (0.75, rgb(0, 0, 0, 0)), (1, rgb(0, 0, 0, 110))))
        p.drawPath(throw)
        p.setBrush(vgrad(690, 740, rgb(255, 220, 190, 50), rgb(0, 0, 0, 0)))
        p.drawPath(throw)

    def _paint_glass(self, p: QPainter) -> None:
        w = self.outside.weather
        # frost creeping in from each pane's corners on a cold day
        if w.snow_on_ground or w.frozen_lake:
            k = 1.0 if w.frozen_lake else 0.6
            p.setPen(Qt.NoPen)
            for pane in PANES:
                r = min(pane.width(), pane.height()) * 0.45
                for corner in (pane.topLeft(), pane.topRight(), pane.bottomLeft(), pane.bottomRight()):
                    p.setBrush(radial(corner.x(), corner.y(), r, (0, rgb(235, 242, 250, 190 * k)),
                                      (0.5, rgb(225, 235, 245, 70 * k)), (1, rgb(220, 230, 240, 0))))
                    p.drawEllipse(corner, r, r)
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
        p.setPen(Qt.NoPen)
        flames = [(c, 1.0) for c in CANDLES] + [(TABLE_CANDLE + QPointF(0, 2), 0.9)]
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
        if self.lamp_on():  # the lamp shade glowing from within
            shade = QPainterPath()
            x = LAMP.x()
            shade.moveTo(x - 30, LAMP.y() - 32)
            shade.lineTo(x + 30, LAMP.y() - 32)
            shade.lineTo(x + 40, LAMP.y() + 32)
            shade.lineTo(x - 40, LAMP.y() + 32)
            shade.closeSubpath()
            p.setBrush(vgrad(LAMP.y() - 32, LAMP.y() + 32, rgb(255, 214, 140, 120), rgb(255, 200, 120, 190)))
            p.drawPath(shade)

    def _paint_dog(self, p: QPainter) -> None:
        """A golden retriever asleep on the rug, breathing slowly."""
        breath = 1 + 0.02 * math.sin(self.t * 1.7)
        gold, light, dark, deep = rgb(206, 140, 66), rgb(240, 196, 128), rgb(150, 92, 40), rgb(110, 64, 28)
        c = DOG
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(radial(c.x(), c.y() + 30, 150, (0, rgb(0, 0, 0, 100)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(QPointF(c.x() + 4, c.y() + 36), 140, 22)
        # feathery tail curled round in front
        tail = QPainterPath()
        tail.moveTo(c.x() - 84, c.y() + 16)
        tail.cubicTo(c.x() - 124, c.y() + 46, c.x() - 50, c.y() + 60, c.x() + 20, c.y() + 46)
        tail.cubicTo(c.x() - 40, c.y() + 44, c.x() - 92, c.y() + 38, c.x() - 74, c.y() + 10)
        tail.closeSubpath()
        p.setBrush(vgrad(c.y() + 10, c.y() + 58, light, gold))
        p.drawPath(tail)
        # the curled body, rising and falling
        p.save()
        p.translate(c.x() - 20, c.y() + 34)
        p.scale(1.0 + (breath - 1) * 0.4, breath)
        p.translate(-(c.x() - 20), -(c.y() + 34))
        body = QPainterPath()
        body.moveTo(c.x() - 96, c.y() + 34)
        body.cubicTo(c.x() - 112, c.y() - 28, c.x() - 40, c.y() - 62, c.x() + 14, c.y() - 50)
        body.cubicTo(c.x() + 56, c.y() - 42, c.x() + 66, c.y() + 6, c.x() + 54, c.y() + 34)
        body.closeSubpath()
        p.setBrush(radial(c.x() - 34, c.y() - 34, 120, (0, light), (0.55, gold), (1, dark)))
        p.drawPath(body)
        # haunch
        p.setBrush(radial(c.x() - 62, c.y() - 4, 52, (0, light), (0.6, gold), (1, dark)))
        p.drawEllipse(QPointF(c.x() - 56, c.y() + 6), 42, 34)
        # tufts of fur along the back
        p.setPen(QPen(alpha(dark, 110), 1.4, Qt.SolidLine, Qt.RoundCap))
        rng = random.Random(7)
        for _ in range(34):
            a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
            r = rng.uniform(0.6, 0.95)
            x = c.x() - 22 + math.cos(a) * 80 * r
            y = c.y() - 4 + math.sin(a) * 48 * r
            p.drawLine(QPointF(x, y), QPointF(x - 5, y + 6))
        p.setPen(Qt.NoPen)
        p.restore()
        # front legs stretched out, paws together
        for dy, shade in ((22, gold), (32, light)):
            p.setBrush(vgrad(c.y() + dy - 9, c.y() + dy + 9, shade, gold))
            p.drawRoundedRect(QRectF(c.x() + 30, c.y() + dy - 9, 76, 17), 8, 8)
            p.setBrush(light)
            p.drawEllipse(QPointF(c.x() + 104, c.y() + dy), 11, 9)
        # head resting on the paws: broad skull, short muzzle
        head = QPointF(c.x() + 66, c.y() - 4)
        p.setBrush(radial(head.x() - 10, head.y() - 16, 54, (0, light), (0.6, gold), (1, dark)))
        p.drawEllipse(head, 40, 34)
        muzzle = QPainterPath()
        muzzle.moveTo(head.x() + 14, head.y() - 4)
        muzzle.cubicTo(head.x() + 40, head.y() - 6, head.x() + 54, head.y() + 6, head.x() + 52, head.y() + 18)
        muzzle.cubicTo(head.x() + 44, head.y() + 30, head.x() + 18, head.y() + 30, head.x() + 8, head.y() + 22)
        muzzle.closeSubpath()
        p.setBrush(vgrad(head.y() - 6, head.y() + 30, light, gold))
        p.drawPath(muzzle)
        p.setBrush(rgb(34, 24, 22))
        p.drawEllipse(QPointF(head.x() + 50, head.y() + 8), 7, 5.5)
        p.setBrush(rgb(255, 255, 255, 80))
        p.drawEllipse(QPointF(head.x() + 48, head.y() + 6), 2, 1.4)
        p.setPen(QPen(rgb(90, 50, 24), 1.4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(head.x() + 30, head.y() + 16, 20, 10), 200 * 16, 120 * 16)  # mouth
        p.setPen(QPen(rgb(60, 34, 18), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(head.x() + 8, head.y() - 12, 18, 9), 200 * 16, 140 * 16)  # closed eye
        p.setPen(Qt.NoPen)
        # big feathery ear
        ear = QPainterPath()
        ear.moveTo(head.x() - 18, head.y() - 26)
        ear.cubicTo(head.x() - 46, head.y() - 18, head.x() - 44, head.y() + 26, head.x() - 22, head.y() + 34)
        ear.cubicTo(head.x() - 4, head.y() + 22, head.x() - 2, head.y() - 16, head.x() - 18, head.y() - 26)
        p.setBrush(vgrad(head.y() - 26, head.y() + 34, gold, deep))
        p.drawPath(ear)
        p.setPen(QPen(alpha(deep, 140), 1.2))
        for k in range(5):
            p.drawLine(QPointF(head.x() - 30 + k * 3, head.y() + 4 + k * 4), QPointF(head.x() - 34 + k * 3, head.y() + 16 + k * 4))
        p.restore()

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
        lp.scale(320 / target.width(), 180 / target.height())
        lp.translate(ox - target.x(), oy - target.y())
        lp.scale(s, s)
        lp.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        lp.setPen(Qt.NoPen)

        def light(x: float, y: float, r: float, strength: float) -> None:
            lp.setBrush(radial(x, y, r, (0, rgb(0, 0, 0, 255 * min(1, strength))), (0.45, rgb(0, 0, 0, 150 * min(1, strength))), (1, rgb(0, 0, 0, 0))))
            lp.drawEllipse(QPointF(x, y), r, r)

        fx, fy = FIREBOX.center().x(), FIREBOX.bottom() - 40
        light(fx, fy, 780 * (0.95 + 0.05 * f), 0.62 * f)
        light(fx, fy + 20, 300, 0.9)
        light(fx, HEARTH_FRONT + 40, 400, 0.6 * f)
        if self.lamp_on():
            light(LAMP.x(), LAMP.y(), 520, 0.72)
            light(LAMP.x() + 160, LAMP.y() + 300, 360, 0.4)
        for c in CANDLES:
            light(c.x(), c.y(), 150, 0.45)
        light(TABLE_CANDLE.x(), TABLE_CANDLE.y(), 160, 0.45)
        for x, y, r, strength in decorations.inside_lights(self.decoration):
            light(x, y, r, strength)
        light(clock.CX, 360, 230, 0.5)  # a soft light kept on the clock face
        light(WINDOW.center().x(), WINDOW.center().y(), 700, 0.85 * l.daylight * (1 - 0.3 * w.clouds) + flash)
        lp.end()
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(target, lm)
        p.restore()

        # warm firelight and lamplight, added on top
        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.setPen(Qt.NoPen)
        warm = 0.45 + 0.55 * darkness
        p.setBrush(radial(fx, fy, 900, (0, rgb(255, 120, 40, 110 * f * warm)), (0.35, rgb(255, 100, 30, 45 * f * warm)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(QPointF(fx, fy), 900, 900)
        if self.lamp_on():
            p.setBrush(radial(LAMP.x(), LAMP.y(), 420, (0, rgb(255, 170, 80, 80)), (1, rgb(0, 0, 0, 0))))
            p.drawEllipse(LAMP, 420, 420)
        p.restore()

