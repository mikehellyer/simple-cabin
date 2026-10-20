"""The log fire: a bed of embers, crossed logs, licking flames and sparks."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath

from simple_cabin.gui.paint import alpha, hgrad, radial, rgb, vgrad, wobble


class Fire:
    def __init__(self, centre_x: float, base_y: float, width: float):
        self.cx, self.base, self.width = centre_x, base_y, width
        self.t = 0.0
        self._rng = random.Random(5)
        self._sparks: list[list[float]] = []
        rng = random.Random(8)
        # Each tongue: x offset, base width, height, speed, phase
        self._tongues = []
        for i in range(11):
            k = (i / 10) * 2 - 1  # -1..1 across the fire
            self._tongues.append((
                k * width * 0.36 + rng.uniform(-8, 8),
                rng.uniform(36, 62),
                (1 - abs(k) * 0.55) * rng.uniform(120, 175),
                rng.uniform(2.2, 3.6),
                rng.uniform(0, 20),
            ))
        self._tongues.sort(key=lambda t: -t[2])  # tallest at the back

    def flicker(self) -> float:
        """0.75..1.05: how bright the fire is right now, for room lighting."""
        return 0.9 + 0.1 * wobble(self.t, 7.3, 11.1, 3.7) + 0.05 * wobble(self.t, 23.0, 17.0)

    def step(self, dt: float) -> None:
        self.t += dt
        rng = self._rng
        if rng.random() < dt * 4:
            self._sparks.append([self.cx + rng.uniform(-60, 60), self.base - 40, rng.uniform(-18, 18), rng.uniform(-90, -50), 0.0, rng.uniform(0.8, 1.8)])
        for s in self._sparks:
            s[4] += dt
            s[0] += s[2] * dt + math.sin(self.t * 6 + s[5] * 9) * 20 * dt
            s[1] += s[3] * dt
        self._sparks = [s for s in self._sparks if s[4] < s[5]]

    def paint(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        cx, base, f = self.cx, self.base, self.flicker()

        # Glow on the back of the firebox
        p.setBrush(radial(cx, base - 60, 230, (0, rgb(255, 150, 50, 150 * f)), (0.5, rgb(200, 70, 20, 70 * f)), (1, rgb(120, 30, 10, 0))))
        p.drawEllipse(QPointF(cx, base - 60), 230, 200)

        # Bed of embers
        p.setBrush(radial(cx, base, self.width * 0.6, (0, rgb(255, 170, 60, 255)), (0.4, rgb(220, 70, 20, 230)), (1, rgb(90, 20, 10, 0))))
        p.drawEllipse(QPointF(cx, base + 2), self.width * 0.55, 16)
        rng = random.Random(3)
        for i in range(26):
            x = cx + rng.uniform(-self.width * 0.45, self.width * 0.45)
            y = base + rng.uniform(-4, 10)
            heat = 0.5 + 0.5 * math.sin(self.t * rng.uniform(1.5, 4) + i)
            p.setBrush(rgb(255, 120 + 100 * heat, 40 * heat, 220))
            p.drawEllipse(QPointF(x, y), rng.uniform(2, 5), rng.uniform(1.5, 3))

        # The back log, behind the flames
        self._log(p, cx - 4, base - 24, 260, 30, -3)

        # Flames: an outer red layer, an orange middle and a bright core
        layers = (
            (1.0, rgb(214, 62, 16), 170),
            (0.74, rgb(255, 140, 32), 210),
            (0.46, rgb(255, 222, 120), 235),
        )
        for scale, colour, a in layers:
            for i, (dx, bw, h, speed, phase) in enumerate(self._tongues):
                t = self.t * speed + phase
                height = h * scale * (0.72 + 0.28 * wobble(t, 1.0, 2.3, 0.6)) * f
                sway = 22 * wobble(t * 0.8, 1.3, 0.7) * scale
                width = bw * (0.55 + 0.45 * scale)
                x = cx + dx
                y0 = base - 14
                path = QPainterPath()
                path.moveTo(x - width / 2, y0)
                path.cubicTo(x - width * 0.62, y0 - height * 0.45, x + sway * 0.4 - width * 0.22, y0 - height * 0.72, x + sway, y0 - height)
                path.cubicTo(x + sway * 0.4 + width * 0.25, y0 - height * 0.7, x + width * 0.6, y0 - height * 0.4, x + width / 2, y0)
                path.closeSubpath()
                p.setBrush(vgrad(y0 - height, y0, (0, alpha(colour, 0)), (0.35, alpha(colour, a * 0.75)), (1, alpha(colour, a))))
                p.drawPath(path)

        # Front logs, crossed
        self._log(p, cx - 50, base - 6, 210, 32, 9)
        self._log(p, cx + 56, base - 4, 200, 30, -11)

        # Sparks
        for x, y, _, _, age, life in self._sparks:
            k = age / life
            p.setBrush(rgb(255, 200 - 80 * k, 80 - 60 * k, 255 * (1 - k)))
            p.drawEllipse(QPointF(x, y), 1.8, 1.8)

    def _log(self, p: QPainter, cx: float, cy: float, length: float, thickness: float, angle: float) -> None:
        p.save()
        p.translate(cx, cy)
        p.rotate(angle)
        rect = QRectF(-length / 2, -thickness / 2, length, thickness)
        p.setBrush(vgrad(rect.top(), rect.bottom(), rgb(92, 58, 34), rgb(60, 36, 22), rgb(30, 18, 12)))
        p.drawRoundedRect(rect, thickness / 2.5, thickness / 2.5)
        # glowing cracks underneath
        glow = 0.6 + 0.4 * math.sin(self.t * 2 + cx)
        p.setBrush(hgrad(rect.left(), rect.right(), (0, rgb(255, 90, 20, 0)), (0.5, rgb(255, 110, 30, 170 * glow)), (1, rgb(255, 90, 20, 0))))
        p.drawRect(QRectF(rect.left() + 10, rect.bottom() - 6, length - 20, 5))
        # cut end
        end = QPointF(rect.right() - thickness * 0.2, 0)
        p.setBrush(rgb(176, 130, 84))
        p.drawEllipse(end, thickness * 0.22, thickness / 2 - 1)
        p.setBrush(rgb(110, 70, 40))
        p.drawEllipse(end, thickness * 0.1, thickness / 4)
        p.restore()
