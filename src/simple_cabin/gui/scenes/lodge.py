"""The cabin seen from outside: a timber-frame lodge with a tall glass
gable, a lower wing with a lantern-lit porch, a fieldstone chimney and
foundation, and a dark standing-seam metal roof.

paint_lodge() draws the building (cached, in the outside scene's static
layer). The glass is then cut out of that layer, and paint_glass() fills it
every frame: the sky's reflection by day, the warm, firelit room by night.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from simple_cabin.gui import textures as tx
from simple_cabin.gui.paint import alpha, hgrad, mix, poly, radial, rgb, scaled, vgrad, wobble
from simple_cabin.gui.scenes.trees import tint

FOUND_TOP, GROUND = 584.0, 616.0
DEPTH = QPointF(-64, -30)  # the direction the building recedes in

# Main gable
EAVE_L, EAVE_R, APEX = QPointF(526, 404), QPointF(1044, 404), QPointF(785, 176)
FASCIA = 16.0
GABLE_POSTS = (570.0, 674.0, 785.0, 896.0, 1000.0)
COLLAR_Y, TRANSOM_Y, SILL_Y = 300.0, 420.0, 576.0

# Wing with its covered porch
WING_APEX, WING_L, WING_R = QPointF(318, 236), QPointF(144, 366), QPointF(492, 366)
PORCH_FASCIA_Y = 380.0
PORCH_POSTS = (112.0, 372.0, 536.0)
WING_WINDOWS = (QRectF(156, 430, 80, 104), QRectF(404, 430, 80, 104))
WING_DOOR = QRectF(272, 418, 64, 166)

CHIMNEY = QRectF(432, 148, 80, FOUND_TOP - 148)
CHIMNEY_TOP = QPointF(472, 128)

RIGHT_PORCH_WINDOW = QRectF(1052, 452, 62, 92)
LANTERNS = (QPointF(254, 448), QPointF(354, 448), QPointF(1028, 470), QPointF(122, 448))


def _slope() -> float:
    return (EAVE_L.y() - APEX.y()) / (APEX.x() - EAVE_L.x())


def roof_underside(x: float) -> float:
    """y of the underside of the main gable's fascia at x."""
    return APEX.y() + FASCIA + 6 + abs(APEX.x() - x) * _slope()


def _gable_inner() -> QPainterPath:
    path = QPainterPath()
    path.moveTo(560, roof_underside(560))
    path.lineTo(APEX.x(), roof_underside(APEX.x()))
    path.lineTo(1010, roof_underside(1010))
    path.lineTo(1010, SILL_Y)
    path.lineTo(560, SILL_Y)
    path.closeSubpath()
    return path


def glass_panes() -> list[QPainterPath]:
    """Every pane of glass on the front of the lodge."""
    inner = _gable_inner()
    panes = []
    for x0, x1 in zip(GABLE_POSTS, GABLE_POSTS[1:]):
        for y0, y1 in ((100, COLLAR_Y - 7), (COLLAR_Y + 7, TRANSOM_Y - 8), (TRANSOM_Y + 8, SILL_Y)):
            rect = QPainterPath()
            rect.addRect(QRectF(x0 + 7, y0, x1 - x0 - 14, y1 - y0))
            pane = rect.intersected(inner)
            if pane.boundingRect().height() > 6:
                panes.append(pane)
    for r in (*WING_WINDOWS, RIGHT_PORCH_WINDOW):
        path = QPainterPath()
        path.addRect(r)
        panes.append(path)
    door = QPainterPath()
    door.addRect(WING_DOOR.adjusted(10, 12, -10, -70))
    panes.append(door)
    # a little window high in the wing's gable
    tri = QPainterPath()
    tri.addPolygon(poly((WING_APEX.x() - 40, 344), (WING_APEX.x(), 296), (WING_APEX.x() + 40, 344)))
    panes.append(tri)
    return panes


GLASS = glass_panes()
GABLE_PANES = len(GLASS) - len(WING_WINDOWS) - 3  # the rest are the wing, porch and door


# --- the building


def paint_lodge(p: QPainter, lit, light: QColor, snow: bool) -> None:
    """lit(colour) adjusts a daylight colour to the scene's light; light is
    what textures get multiplied by to match."""
    p.setPen(Qt.NoPen)
    _paint_wing(p, lit, light, snow)
    _paint_roof_plane(p, lit, snow, EAVE_L, APEX)  # the main roof receding behind the chimney
    _paint_chimney(p, lit, light, snow)
    _paint_gable(p, lit, light, snow)
    _paint_right_porch(p, lit, light, snow)
    # fieldstone foundation along the whole front
    found = QRectF(96, FOUND_TOP, 1080, GROUND - FOUND_TOP)
    p.drawImage(found.topLeft(), tx.stone_wall(int(found.width()), int(found.height()), 61, 0.55))
    tint(p, found, light)
    tx.shade_rect(p, found, top=0.35, bottom=0.2)
    # lantern fixtures (their glow is drawn per frame)
    for c in LANTERNS:
        p.setBrush(lit(rgb(30, 26, 22)))
        p.drawRect(QRectF(c.x() - 7, c.y() - 12, 14, 22))
        p.drawPolygon(poly((c.x() - 9, c.y() - 12), (c.x(), c.y() - 20), (c.x() + 9, c.y() - 12)))


def _metal(p: QPainter, path: QPainterPath, lit, snow: bool, seam_dir: QPointF, start: QPointF, end: QPointF) -> None:
    """A dark standing-seam metal roof surface, seams running down the slope."""
    p.setBrush(lit(rgb(56, 60, 64)) if not snow else lit(rgb(232, 236, 242)))
    p.drawPath(path)
    p.save()
    p.setClipPath(path)
    p.setPen(QPen(lit(rgb(84, 90, 96)) if not snow else lit(rgb(200, 208, 220)), 1.4))
    steps = int(math.hypot(end.x() - start.x(), end.y() - start.y()) / 12)
    for i in range(steps + 1):
        t = i / max(1, steps)
        a = QPointF(start.x() + (end.x() - start.x()) * t, start.y() + (end.y() - start.y()) * t)
        p.drawLine(a, a + seam_dir * 400)
    p.restore()
    p.setPen(Qt.NoPen)


def _paint_roof_plane(p: QPainter, lit, snow: bool, eave: QPointF, apex: QPointF) -> None:
    plane = QPainterPath()
    plane.addPolygon(poly((eave.x(), eave.y()), (apex.x(), apex.y()), (apex.x() + DEPTH.x() * 2.2, apex.y() + DEPTH.y() * 2.2),
                          (eave.x() + DEPTH.x() * 2.2, eave.y() + DEPTH.y() * 2.2)))
    plane.closeSubpath()
    down = QPointF(eave.x() - apex.x(), eave.y() - apex.y())
    n = math.hypot(down.x(), down.y())
    _metal(p, plane, lit, snow, QPointF(down.x() / n, down.y() / n), apex + DEPTH * 2.2, apex)


def _siding(p: QPainter, shape, light: QColor, vertical: bool, seed: int) -> None:
    r = shape.boundingRect() if isinstance(shape, QPainterPath) else shape
    tex = tx.wood(int(r.width()) + 4, int(r.height()) + 4, 22 if vertical else 18, not vertical, "cedar", seed)
    tx.draw_textured(p, shape, tex)
    tint(p, shape, light)


def _timber(p: QPainter, rect: QRectF, lit, vertical: bool = True) -> None:
    c = lit(rgb(150, 98, 54))
    if vertical:
        p.setBrush(hgrad(rect.left(), rect.right(), scaled(c, 1.2), c, scaled(c, 0.7)))
    else:
        p.setBrush(vgrad(rect.top(), rect.bottom(), scaled(c, 1.25), c, scaled(c, 0.65)))
    p.drawRect(rect)


def _paint_wing(p: QPainter, lit, light: QColor, snow: bool) -> None:
    # roof plane receding from the wing's gable
    _paint_roof_plane(p, lit, snow, WING_L, WING_APEX)
    # gable end, with board-and-batten siding
    gable = QPainterPath()
    gable.addPolygon(poly((WING_L.x() + 8, WING_L.y() - 4), (WING_APEX.x(), WING_APEX.y() + 14), (WING_R.x() - 8, WING_R.y() - 4),
                          (WING_R.x() - 8, PORCH_FASCIA_Y), (WING_L.x() + 8, PORCH_FASCIA_Y)))
    gable.closeSubpath()
    _siding(p, gable, light, True, 71)
    # under the porch roof: the wing's front wall, in shade
    wall = QRectF(118, PORCH_FASCIA_Y, 430, FOUND_TOP - PORCH_FASCIA_Y)
    _siding(p, wall, light, False, 73)
    p.fillRect(wall, vgrad(wall.top(), wall.bottom(), rgb(0, 0, 0, 150), rgb(0, 0, 0, 60)))
    # window and door frames
    for r in WING_WINDOWS:
        _timber(p, r.adjusted(-7, -7, 7, 7), lit)
        p.setBrush(lit(rgb(40, 30, 22)))
        p.drawRect(r)
    _timber(p, WING_DOOR.adjusted(-6, -6, 6, 0), lit)
    p.setBrush(lit(rgb(110, 66, 34)))
    p.drawRect(WING_DOOR)
    # the porch roof: a shed roof on timber posts and stone piers
    roof = QPainterPath()
    roof.addPolygon(poly((100, PORCH_FASCIA_Y - 18), (548, PORCH_FASCIA_Y - 18), (556, PORCH_FASCIA_Y), (92, PORCH_FASCIA_Y)))
    roof.closeSubpath()
    _metal(p, roof, lit, snow, QPointF(0.15, 1), QPointF(100, PORCH_FASCIA_Y - 18), QPointF(548, PORCH_FASCIA_Y - 18))
    _timber(p, QRectF(90, PORCH_FASCIA_Y, 468, 14), lit, vertical=False)
    for x in PORCH_POSTS:
        pier = QRectF(x - 18, 520, 36, FOUND_TOP - 520)
        p.drawImage(pier.topLeft(), tx.stone_wall(36, int(pier.height()), 81 + int(x), 0.5))
        tint(p, pier, light)
        tx.shade_rect(p, pier, left=0.2, right=0.4)
        _timber(p, QRectF(x - 8, PORCH_FASCIA_Y + 14, 16, 520 - PORCH_FASCIA_Y - 14), lit)
        # knee braces
        p.setBrush(lit(rgb(130, 84, 46)))
        for side in (-1, 1):
            p.drawPolygon(poly((x, PORCH_FASCIA_Y + 40), (x, PORCH_FASCIA_Y + 50), (x + side * 34, PORCH_FASCIA_Y + 14), (x + side * 24, PORCH_FASCIA_Y + 14)))
    # the wing gable's fascia
    p.setPen(QPen(lit(rgb(120, 76, 40)), 12, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(WING_L, WING_APEX)
    p.drawLine(WING_APEX, WING_R)
    p.setPen(Qt.NoPen)
    _timber(p, QRectF(WING_APEX.x() - 46, 344, 92, 8), lit, vertical=False)
    if snow:
        p.setPen(QPen(lit(rgb(240, 244, 250)), 5))
        p.drawLine(WING_L + QPointF(0, -6), WING_APEX + QPointF(0, -6))
        p.drawLine(WING_APEX + QPointF(0, -6), WING_R + QPointF(0, -6))
        p.setPen(Qt.NoPen)


def _paint_chimney(p: QPainter, lit, light: QColor, snow: bool) -> None:
    c = CHIMNEY
    p.drawImage(c.topLeft(), tx.stone_wall(int(c.width()), int(c.height()), 91, 0.6))
    tint(p, c, light)
    tx.shade_rect(p, c, left=0.15, right=0.5)
    cap = QRectF(c.left() - 6, c.top() - 12, c.width() + 12, 14)
    p.setBrush(vgrad(cap.top(), cap.bottom(), lit(rgb(70, 72, 74)), lit(rgb(30, 30, 32))))
    p.drawRect(cap)
    p.setBrush(lit(rgb(40, 40, 42)))
    p.drawRect(QRectF(c.center().x() - 18, cap.top() - 10, 36, 10))
    if snow:
        p.setBrush(lit(rgb(240, 244, 250)))
        p.drawRoundedRect(QRectF(cap.left() - 2, cap.top() - 6, cap.width() + 4, 8), 4, 4)


def _paint_gable(p: QPainter, lit, light: QColor, snow: bool) -> None:
    # the gable wall (mostly glass)
    wall = QPainterPath()
    wall.addPolygon(poly((548, roof_underside(548)), (APEX.x(), roof_underside(APEX.x()) - 4), (1022, roof_underside(1022)),
                         (1022, FOUND_TOP), (548, FOUND_TOP)))
    wall.closeSubpath()
    _siding(p, wall, light, True, 101)
    p.setBrush(lit(rgb(36, 28, 22)))
    for pane in GLASS[:GABLE_PANES]:
        p.drawPath(pane)
    # the timber frame: posts, transom, collar tie, sill and a king-post truss
    for x in GABLE_POSTS:
        top = roof_underside(x)
        _timber(p, QRectF(x - 7, top, 14, SILL_Y + 4 - top), lit)
    for y, h in ((COLLAR_Y - 7, 14), (TRANSOM_Y - 8, 16), (SILL_Y, 10)):
        half = min(APEX.x() - 560, (y - roof_underside(APEX.x())) / _slope())
        _timber(p, QRectF(APEX.x() - half, y, 2 * half, h), lit, vertical=False)
    p.setPen(QPen(lit(rgb(140, 90, 50)), 9, Qt.SolidLine, Qt.FlatCap))
    for side in (-1, 1):
        p.drawLine(QPointF(APEX.x() + side * 70, COLLAR_Y - 6), QPointF(APEX.x() + side * 8, roof_underside(APEX.x()) + 34))
    p.setPen(Qt.NoPen)
    # the fascia boards along the roof edges, with exposed purlin ends
    p.setPen(QPen(lit(rgb(126, 80, 42)), FASCIA, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(EAVE_L + QPointF(0, FASCIA / 2), APEX + QPointF(0, FASCIA / 2))
    p.drawLine(APEX + QPointF(0, FASCIA / 2), EAVE_R + QPointF(0, FASCIA / 2))
    p.setPen(Qt.NoPen)
    for k in range(1, 5):
        for side in (-1, 1):
            x = APEX.x() + side * (APEX.x() - EAVE_L.x()) * k / 5
            y = roof_underside(x)
            p.setBrush(lit(rgb(110, 70, 36)))
            p.drawRect(QRectF(x - 6, y - 2, 12, 14))
    # a thin metal edge (or a snow load) along the top of the fascia
    p.setPen(QPen(lit(rgb(240, 244, 250)) if snow else lit(rgb(46, 48, 52)), 6 if snow else 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(EAVE_L + QPointF(-2, -2), APEX + QPointF(0, -3))
    p.drawLine(APEX + QPointF(0, -3), EAVE_R + QPointF(2, -2))
    p.setPen(Qt.NoPen)
    # knee braces at the eaves
    p.setBrush(lit(rgb(130, 84, 46)))
    for x, side in ((560, -1), (1010, 1)):
        p.drawPolygon(poly((x, 440), (x, 456), (x + side * 40, roof_underside(x + side * 40) - 4), (x + side * 28, roof_underside(x + side * 28) - 4)))


def _paint_right_porch(p: QPainter, lit, light: QColor, snow: bool) -> None:
    wall = QRectF(1022, 420, 140, FOUND_TOP - 420)
    _siding(p, wall, light, False, 111)
    p.fillRect(wall, rgb(0, 0, 0, 110))
    _timber(p, RIGHT_PORCH_WINDOW.adjusted(-6, -6, 6, 6), lit)
    p.setBrush(lit(rgb(40, 30, 22)))
    p.drawRect(RIGHT_PORCH_WINDOW)
    roof = QPainterPath()
    roof.addPolygon(poly((1016, 400), (1150, 412), (1170, 428), (1016, 420)))
    roof.closeSubpath()
    _metal(p, roof, lit, snow, QPointF(0.4, 1), QPointF(1016, 400), QPointF(1150, 412))
    _timber(p, QRectF(1012, 420, 162, 10), lit, vertical=False)
    pier = QRectF(1132, 532, 34, FOUND_TOP - 532)
    p.drawImage(pier.topLeft(), tx.stone_wall(34, int(pier.height()), 121, 0.5))
    tint(p, pier, light)
    _timber(p, QRectF(1141, 430, 16, 102), lit)


# --- per frame


def paint_glass(p: QPainter, daylight: float, sky: QColor, glow: float, t: float) -> None:
    """The panes: the sky reflected by day, the warm room within at night.
    glow (0..1) is how strongly the lit interior shows."""
    reflection = mix(scaled(sky, 0.6), rgb(34, 42, 52), 0.55)
    interior = rgb(255, 176, 90)
    glow = max(glow, 0.22)  # the room always shows a little through the glass
    p.setPen(Qt.NoPen)
    flicker = 0.9 + 0.1 * wobble(t, 7.3, 11.1)
    for i, pane in enumerate(GLASS):
        r = pane.boundingRect()
        p.save()
        p.setClipPath(pane)
        base = mix(reflection, scaled(interior, 0.55), glow * 0.9)
        p.fillRect(r, vgrad(r.top(), r.bottom(), scaled(base, 1.15), scaled(base, 0.85)))
        if glow > 0.05:
            p.setOpacity(glow)
            _interior(p, i, r, flicker)
            p.setOpacity(1.0)
        # a sky reflection streak on the glass
        p.fillRect(r, hgrad(r.left(), r.right(), (0, alpha(sky, 0)), (0.3, alpha(sky, 60 * daylight)), (0.45, alpha(sky, 0))))
        p.restore()


def _interior(p: QPainter, index: int, r: QRectF, flicker: float) -> None:
    """Hints of the room seen through the gable: beams, the stone fireplace
    with its fire, lamps and the backs of chairs."""
    warm = rgb(255, 196, 120)
    p.fillRect(r, vgrad(r.top(), r.bottom(), rgb(150, 86, 40), rgb(230, 150, 80)))
    if index < GABLE_PANES:
        # the fireplace, in the middle of the great room
        fx = APEX.x()
        p.setBrush(hgrad(fx - 50, fx + 50, rgb(70, 56, 46), rgb(112, 92, 76), rgb(60, 46, 38)))
        p.drawRect(QRectF(fx - 50, 250, 100, 330))
        p.setPen(QPen(rgb(50, 38, 30, 160), 1))
        for y in range(262, 500, 22):  # courses of stone
            p.drawLine(QPointF(fx - 50, y), QPointF(fx + 50, y))
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(40, 24, 16))
        p.drawRect(QRectF(fx - 34, 500, 68, 52))
        p.setBrush(radial(fx, 540, 50, (0, rgb(255, 230, 140, int(255 * flicker))), (0.5, rgb(255, 140, 40, 200)), (1, rgb(255, 120, 40, 0))))
        p.drawEllipse(QPointF(fx, 538), 46, 26)
        # ceiling beams
        p.setBrush(rgb(100, 56, 26))
        for y in (318, 436):
            p.drawRect(QRectF(560, y, 450, 8))
        # lamps with glowing shades
        for x in (640, 930):
            p.setBrush(radial(x, 496, 46, (0, rgb(255, 236, 180, 230)), (1, rgb(255, 200, 120, 0))))
            p.drawEllipse(QPointF(x, 496), 46, 46)
            p.setBrush(rgb(255, 232, 180))
            p.drawPolygon(poly((x - 12, 484), (x + 12, 484), (x + 16, 504), (x - 16, 504)))
        # sofa backs
        p.setBrush(rgb(120, 70, 40))
        p.drawRoundedRect(QRectF(600, 546, 130, 30), 10, 10)
        p.drawRoundedRect(QRectF(840, 546, 130, 30), 10, 10)
    else:
        p.setBrush(radial(r.center().x(), r.center().y(), r.width(), (0, alpha(warm, 220)), (1, alpha(warm, 0))))
        p.drawEllipse(r.center(), r.width() * 0.8, r.height() * 0.6)
