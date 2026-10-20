"""The window's one big canvas: animates the cabin scenes and the weather
screen, and crossfades between them."""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from simple_cabin.core import weather as wx
from simple_cabin.core.sky import Light
from simple_cabin.gui.paint import radial, rgb
from simple_cabin.gui.scenes.fire import Fire
from simple_cabin.gui.scenes.icons import draw_icon
from simple_cabin.gui.scenes.inside import InsideScene, fit_scale
from simple_cabin.gui.scenes.outside import OutsideScene
from simple_cabin.gui.scenes.weather_board import WeatherBoard

INSIDE, OUTSIDE, WEATHER = "inside", "outside", "weather"
FRAME_MS = 33
LIGHT_FRAME_MS = 50  # 20 fps in light graphics mode
LIGHT_SCALE = 0.6  # light mode draws the scenes at this fraction of the window's size
FADE_SECONDS = 1.4
HINT_SECONDS = 5.0
CURSOR_HIDE_SECONDS = 3.0

HINT = "Space  inside / outside     W  weather & clock     F  full screen     M  mute     Right-click  menu"


class Stage(QWidget):
    thunder = Signal()
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setMinimumSize(480, 270)

        self.outside = OutsideScene()
        self.inside = InsideScene(self.outside)
        self.board = WeatherBoard(self.outside)
        self.forecast: Optional[wx.Forecast] = None

        self.mode = INSIDE
        self._scene_mode = INSIDE  # the last cabin view, to return to from the weather screen
        self._fade_from: Optional[QPixmap] = None
        self._fade_left = 0.0
        self._mode_time = 0.0
        self.auto_switch = True
        self.inside_seconds = 300.0
        self.outside_seconds = 40.0

        self._toast = ""
        self._toast_left = 0.0
        self._hint_left = HINT_SECONDS
        self._idle = 0.0
        self.temperature_unit = "C"

        # Until the room has been built (textures and all — a couple of
        # seconds the very first time), show a "lighting the fire" screen.
        self._loading = True
        self._loader: Optional[threading.Thread] = None
        self._loaded = threading.Event()
        self._loading_fire = Fire(0, 0, 150)
        self._light = False
        self._buffer: Optional[QImage] = None

        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(FRAME_MS)

    # --- state

    def set_conditions(self, weather: wx.SceneWeather, light: Light, moon_phase: float) -> None:
        self.outside.set_conditions(weather, light, moon_phase)

    def set_forecast(self, forecast: Optional[wx.Forecast], status: str = "") -> None:
        self.forecast = forecast
        self.board.forecast = forecast
        self.board.status = status

    def set_mode(self, mode: str, fade: bool = True) -> None:
        if mode == self.mode:
            return
        if fade and self.isVisible() and self.width() > 0:
            self._fade_from = self.grab()
            self._fade_left = FADE_SECONDS
        self.mode = mode
        if mode != WEATHER:
            self._scene_mode = mode
        self._mode_time = 0.0
        self.mode_changed.emit(mode)
        self.update()

    def set_light_graphics(self, light: bool) -> None:
        """Light graphics: the scenes are drawn smaller and scaled up, at a
        lower frame rate, for slower machines such as a Raspberry Pi."""
        self._light = light
        self._buffer = None
        self._timer.setInterval(LIGHT_FRAME_MS if light else FRAME_MS)

    def _scene_target(self) -> tuple[QRectF, float]:
        """Where the scenes are drawn: the window itself, or (light mode) a
        smaller offscreen image."""
        if self._light:
            return QRectF(0, 0, max(1, int(self.width() * LIGHT_SCALE)), max(1, int(self.height() * LIGHT_SCALE))), 1.0
        return QRectF(self.rect()), self.devicePixelRatioF()

    def toggle_view(self) -> None:
        self.set_mode(OUTSIDE if self.mode == INSIDE else INSIDE)

    def toggle_weather(self) -> None:
        self.set_mode(self._scene_mode if self.mode == WEATHER else WEATHER)

    def leave_weather(self) -> bool:
        if self.mode == WEATHER:
            self.set_mode(self._scene_mode)
            return True
        return False

    def toast(self, text: str, seconds: float = 3.0) -> None:
        self._toast, self._toast_left = text, seconds
        self.update()

    # --- animation

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now
        if self._loading:
            self._tick_loading(dt)
            return
        self.outside.step(dt)
        self.inside.step(dt)
        if self.outside.thunder_pending:
            self.outside.thunder_pending = False
            self.thunder.emit()

        self._mode_time += dt
        if self.auto_switch and self.mode != WEATHER:
            if self.mode == INSIDE and self._mode_time > self.inside_seconds:
                self.set_mode(OUTSIDE)
            elif self.mode == OUTSIDE and self._mode_time > self.outside_seconds:
                self.set_mode(INSIDE)

        if self._fade_left > 0:
            self._fade_left -= dt
            if self._fade_left <= 0:
                self._fade_from = None
        self._toast_left = max(0.0, self._toast_left - dt)
        self._hint_left = max(0.0, self._hint_left - dt)
        self._idle += dt
        if self._idle > CURSOR_HIDE_SECONDS and self.window().isFullScreen():
            self.setCursor(Qt.BlankCursor)
        self.update()

    def _tick_loading(self, dt: float) -> None:
        self._loading_fire.step(dt)
        if self._loader is None and self.isVisible() and self.width() > 0:
            rect, dpr = self._scene_target()

            def build() -> None:
                try:
                    self.inside.prerender(rect, dpr)
                    self.inside.prepare_window_view(rect, dpr)
                finally:
                    self._loaded.set()

            self._loader = threading.Thread(target=build, daemon=True)
            self._loader.start()
        if self._loaded.is_set():
            self._fade_from = self.grab()  # the loading screen, to fade from
            self._fade_left = FADE_SECONDS
            self._loading = False
            self._hint_left = HINT_SECONDS
        self.update()

    def _paint_loading(self, p: QPainter, rect: QRectF) -> None:
        p.fillRect(rect, rgb(14, 9, 7))
        c = rect.center()
        size = min(rect.width(), rect.height())
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        f = self._loading_fire.flicker()
        p.setBrush(radial(c.x(), c.y(), size * 0.6, (0, rgb(120, 52, 18, 160 * f)), (0.5, rgb(60, 24, 10, 60)), (1, rgb(0, 0, 0, 0))))
        p.drawEllipse(c, size * 0.6, size * 0.6)
        p.save()
        k = size / 900
        p.translate(c.x(), c.y() + size * 0.06)
        p.scale(k * 0.8, k * 0.8)
        self._loading_fire.paint(p)
        p.restore()
        font = QFont("serif")
        font.setPixelSize(max(14, int(size * 0.045)))
        font.setItalic(True)
        p.setFont(font)
        p.setPen(rgb(255, 214, 160, 230))
        p.drawText(QRectF(rect.left(), c.y() + size * 0.12, rect.width(), size * 0.08), Qt.AlignCenter, "Lighting the fire…")

    def mouseMoveEvent(self, event) -> None:
        self._idle = 0.0
        if self.cursor().shape() == Qt.BlankCursor:
            self.unsetCursor()
        if self._hint_left < 1.0:
            self._hint_left = 2.5
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        w = self.window()
        w.showNormal() if w.isFullScreen() else w.showFullScreen()

    # --- painting

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        if self._loading:
            self._paint_loading(p, rect)
            p.end()
            return
        now_seconds = time.time()
        now = datetime.fromtimestamp(now_seconds)
        if self.mode == WEATHER:
            self.board.paint(p, rect, now)
        else:
            target, dpr = self._scene_target()
            if self._light:
                size = (int(target.width()), int(target.height()))
                if self._buffer is None or (self._buffer.width(), self._buffer.height()) != size:
                    self._buffer = QImage(size[0], size[1], QImage.Format_RGB32)
                sp = QPainter(self._buffer)
                sp.setRenderHint(QPainter.SmoothPixmapTransform)
            else:
                sp = p
            if self.mode == INSIDE:
                self.inside.paint(sp, target, now, now_seconds)
                self.outside.prepare(target, dpr)  # ready for the next step outside
            else:
                self.outside.paint(sp, target)
            if self._light:
                sp.end()
                p.drawImage(rect, self._buffer)
        if self.mode != WEATHER:
            self._paint_badge(p, rect)

        if self._fade_from is not None and self._fade_left > 0:
            p.setOpacity(max(0.0, self._fade_left / FADE_SECONDS) ** 1.5)
            p.drawPixmap(self.rect(), self._fade_from)
            p.setOpacity(1.0)
        self._paint_messages(p, rect)
        p.end()

    def _paint_badge(self, p: QPainter, rect: QRectF) -> None:
        """A small, quiet weather note in the corner of the cabin views."""
        f = self.forecast
        if f is None:
            return
        s = max(0.6, min(1.4, fit_scale(rect)))
        w, h = 150 * s, 56 * s
        box = QRectF(rect.right() - w - 16 * s, rect.top() + 14 * s, w, h)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(0, 0, 0, 80))
        p.drawRoundedRect(box, h / 2, h / 2)
        draw_icon(p, QPointF(box.left() + h * 0.62, box.center().y()), h * 0.78, f.code, f.is_day)
        font = QFont()
        font.setPixelSize(int(26 * s))
        p.setFont(font)
        p.setPen(rgb(255, 255, 255, 230))
        p.drawText(QRectF(box.left() + h * 1.1, box.top(), w - h * 1.25, h), Qt.AlignVCenter | Qt.AlignLeft,
                   wx.format_temp(f.temperature, self.temperature_unit))

    def _paint_messages(self, p: QPainter, rect: QRectF) -> None:
        font = QFont()
        size = max(12, int(rect.width() / 90))
        font.setPixelSize(size)
        p.setFont(font)
        p.setPen(Qt.NoPen)
        if self._hint_left > 0 and self.mode != WEATHER:
            a = min(1.0, self._hint_left)
            box = QRectF(rect.left(), rect.bottom() - size * 3, rect.width(), size * 2.2)
            p.setBrush(rgb(0, 0, 0, 110 * a))
            p.drawRect(box)
            p.setPen(rgb(255, 255, 255, 220 * a))
            p.drawText(box, Qt.AlignCenter, HINT)
        if self._toast_left > 0:
            a = min(1.0, self._toast_left)
            metrics_w = p.fontMetrics().horizontalAdvance(self._toast) + size * 3
            box = QRectF(rect.center().x() - metrics_w / 2, rect.top() + size * 1.5, metrics_w, size * 2.4)
            p.setPen(Qt.NoPen)
            p.setBrush(rgb(0, 0, 0, 150 * a))
            p.drawRoundedRect(box, size * 1.2, size * 1.2)
            p.setPen(rgb(255, 255, 255, 240 * a))
            p.drawText(box, Qt.AlignCenter, self._toast)
