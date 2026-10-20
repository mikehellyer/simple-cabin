"""The weather screen: a big clock with the local forecast beside it."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from simple_cabin.core import weather as wx
from simple_cabin.gui.paint import H, W, alpha, mix, radial, rgb, vgrad
from simple_cabin.gui.scenes.icons import draw_icon
from simple_cabin.gui.scenes.outside import OutsideScene

WHITE = rgb(255, 255, 255)
DIM = rgb(255, 255, 255, 170)
FAINT = rgb(255, 255, 255, 110)
RAIN_BLUE = rgb(130, 196, 255)


def _font(px: float, weight=QFont.Normal) -> QFont:
    f = QFont()
    f.setPixelSize(max(1, int(px)))
    f.setWeight(weight)
    return f


class WeatherBoard:
    def __init__(self, outside: OutsideScene):
        self.outside = outside  # for the sky colours, so the board matches outside
        self.forecast: Optional[wx.Forecast] = None
        self.status = "Fetching the weather…"
        self.temperature_unit = "C"
        self.wind_unit = "mph"
        self.clock_24h = True

    def paint(self, p: QPainter, target: QRectF, now: datetime) -> None:
        top, bottom = self.outside.sky_colours()
        p.fillRect(target, vgrad(target.top(), target.bottom(), mix(top, rgb(0, 0, 0), 0.35), mix(bottom, rgb(0, 0, 0), 0.5)))

        s = min(target.width() / W, target.height() / H)
        p.save()
        p.translate(target.x() + (target.width() - W * s) / 2, target.y() + (target.height() - H * s) / 2)
        p.scale(s, s)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self._paint_clock(p, now)
        f = self.forecast
        if f is None:
            p.setFont(_font(34))
            p.setPen(DIM)
            p.drawText(QRectF(0, 520, W, 80), Qt.AlignCenter, self.status)
        else:
            self._paint_header(p, f)
            self._paint_current(p, f, now)
            self._paint_hours(p, f)
            self._paint_days(p, f, now)
        p.setFont(_font(18))
        p.setPen(FAINT)
        p.drawText(QRectF(0, 862, W, 30), Qt.AlignCenter, "Press W or Esc to go back to the cabin")
        p.restore()

    # --- parts

    def _paint_clock(self, p: QPainter, now: datetime) -> None:
        if self.clock_24h:
            main, suffix = now.strftime("%H:%M"), ""
        else:
            main, suffix = f"{now.hour % 12 or 12}:{now.minute:02d}", ("AM" if now.hour < 12 else "PM")
        big = _font(250, QFont.Light)
        secs = _font(80, QFont.Light)
        fm, sm = QFontMetricsF(big), QFontMetricsF(secs)
        seconds = f":{now.second:02d}"
        width = fm.horizontalAdvance(main) + sm.horizontalAdvance(seconds) + 10
        left = 470 - width / 2
        baseline = 300
        p.setPen(WHITE)
        p.setFont(big)
        p.drawText(QPointF(left, baseline), main)
        p.setFont(secs)
        p.setPen(DIM)
        x = left + fm.horizontalAdvance(main) + 10
        p.drawText(QPointF(x, baseline), seconds)
        if suffix:
            p.drawText(QPointF(x, baseline - fm.capHeight() + sm.capHeight()), suffix)
        p.setFont(_font(46))
        p.setPen(WHITE)
        p.drawText(QRectF(40, baseline + 20, 860, 60), Qt.AlignCenter, f"{now:%A} {now.day} {now:%B}")

    def _paint_header(self, p: QPainter, f: wx.Forecast) -> None:
        # a little map pin, then the place
        pin = QPainterPath()
        pin.moveTo(60, 70)
        pin.cubicTo(46, 52, 46, 36, 60, 34)
        pin.cubicTo(74, 36, 74, 52, 60, 70)
        p.setPen(Qt.NoPen)
        p.setBrush(rgb(255, 110, 90))
        p.drawPath(pin)
        p.setBrush(WHITE)
        p.drawEllipse(QPointF(60, 46), 4, 4)
        p.setFont(_font(30, QFont.DemiBold))
        p.setPen(WHITE)
        p.drawText(QRectF(82, 30, 820, 44), Qt.AlignLeft | Qt.AlignVCenter, f.location or "Here")
        updated = datetime.fromtimestamp(f.fetched_at).strftime("%H:%M" if self.clock_24h else "%I:%M %p").lstrip("0")
        p.setFont(_font(18))
        p.setPen(FAINT)
        p.drawText(QRectF(82, 70, 820, 26), Qt.AlignLeft | Qt.AlignVCenter, f"Updated {updated}" + (f" · {self.status}" if self.status else ""))

    def _card(self, p: QPainter, rect: QRectF) -> None:
        p.setPen(QPen(rgb(255, 255, 255, 40), 1))
        p.setBrush(rgb(255, 255, 255, 22))
        p.drawRoundedRect(rect, 22, 22)

    def _paint_current(self, p: QPainter, f: wx.Forecast, now: datetime) -> None:
        card = QRectF(950, 40, 600, 400)
        self._card(p, card)
        if f.is_day and f.condition in (wx.CLEAR, wx.PARTLY_CLOUDY):
            p.setPen(Qt.NoPen)
            p.setBrush(radial(1060, 160, 140, (0, rgb(255, 210, 90, 60)), (1, rgb(255, 210, 90, 0))))
            p.drawEllipse(QPointF(1060, 160), 140, 140)
        draw_icon(p, QPointF(1070, 160), 170, f.code, f.is_day)
        p.setPen(WHITE)
        p.setFont(_font(130, QFont.Light))
        p.drawText(QRectF(1170, 70, 360, 170), Qt.AlignRight | Qt.AlignVCenter, wx.format_temp(f.temperature, self.temperature_unit))
        p.setFont(_font(38, QFont.DemiBold))
        p.drawText(QRectF(980, 250, 540, 50), Qt.AlignLeft | Qt.AlignVCenter, f.description)

        today = f.today(None)
        rows = [
            ("Feels like", wx.format_temp(f.apparent_temperature, self.temperature_unit)),
            ("Wind", f"{wx.format_wind(f.wind_speed, self.wind_unit)} {wx.compass(f.wind_direction)}"
                     + (f", gusts {wx.format_wind(f.wind_gusts, self.wind_unit)}" if f.wind_gusts > f.wind_speed * 1.3 else "")),
            ("Humidity", f"{f.humidity}%"),
        ]
        if today and today.sunrise and today.sunset:
            fmt = "%H:%M" if self.clock_24h else "%I:%M %p"
            rise = datetime.fromisoformat(today.sunrise).strftime(fmt).lstrip("0")
            set_ = datetime.fromisoformat(today.sunset).strftime(fmt).lstrip("0")
            rows.append(("Sun", f"up {rise} · down {set_}"))
        p.setFont(_font(24))
        for i, (label, value) in enumerate(rows):
            y = 308 + i * 32
            p.setPen(DIM)
            p.drawText(QRectF(980, y, 160, 30), Qt.AlignLeft | Qt.AlignVCenter, label)
            p.setPen(WHITE)
            p.drawText(QRectF(1130, y, 400, 30), Qt.AlignLeft | Qt.AlignVCenter, value)

    def _paint_hours(self, p: QPainter, f: wx.Forecast) -> None:
        hours = f.upcoming_hours(12)
        card = QRectF(50, 470, 1500, 170)
        self._card(p, card)
        if not hours:
            return
        col = card.width() / len(hours)
        for i, h in enumerate(hours):
            x = card.left() + col * i
            t = datetime.fromisoformat(h.time)
            label = "Now" if i == 0 else (t.strftime("%H:%M") if self.clock_24h else (f"{t.hour % 12 or 12}{'am' if t.hour < 12 else 'pm'}"))
            p.setFont(_font(20, QFont.DemiBold if i == 0 else QFont.Normal))
            p.setPen(WHITE if i == 0 else DIM)
            p.drawText(QRectF(x, card.top() + 10, col, 28), Qt.AlignCenter, label)
            draw_icon(p, QPointF(x + col / 2, card.top() + 72), 58, h.code, h.is_day)
            p.setFont(_font(26))
            p.setPen(WHITE)
            p.drawText(QRectF(x, card.top() + 104, col, 32), Qt.AlignCenter, wx.format_temp(h.temperature, self.temperature_unit))
            if h.precip_probability >= 10:
                p.setFont(_font(17))
                p.setPen(RAIN_BLUE)
                p.drawText(QRectF(x, card.top() + 134, col, 24), Qt.AlignCenter, f"{h.precip_probability}%")

    def _paint_days(self, p: QPainter, f: wx.Forecast, now: datetime) -> None:
        days = f.daily[:7]
        card = QRectF(50, 660, 1500, 190)
        self._card(p, card)
        if not days:
            return
        lows = [d.temp_min for d in days]
        highs = [d.temp_max for d in days]
        lo, hi = min(lows), max(highs)
        span = max(1.0, hi - lo)
        today = f.local_now().date().isoformat()
        col = card.width() / len(days)
        for i, d in enumerate(days):
            x = card.left() + col * i
            date = datetime.fromisoformat(d.date)
            label = "Today" if d.date == today else date.strftime("%a")
            p.setFont(_font(22, QFont.DemiBold if d.date == today else QFont.Normal))
            p.setPen(WHITE)
            p.drawText(QRectF(x, card.top() + 10, col, 30), Qt.AlignCenter, label)
            draw_icon(p, QPointF(x + col / 2, card.top() + 78), 64, d.code, True)
            # high / low, with a little range bar
            p.setFont(_font(24))
            p.drawText(QRectF(x, card.top() + 116, col / 2 - 6, 30), Qt.AlignRight | Qt.AlignVCenter, wx.format_temp(d.temp_max, self.temperature_unit))
            p.setPen(DIM)
            p.drawText(QRectF(x + col / 2 + 6, card.top() + 116, col / 2, 30), Qt.AlignLeft | Qt.AlignVCenter, wx.format_temp(d.temp_min, self.temperature_unit))
            bar = QRectF(x + 30, card.top() + 154, col - 60, 6)
            p.setPen(Qt.NoPen)
            p.setBrush(rgb(255, 255, 255, 40))
            p.drawRoundedRect(bar, 3, 3)
            a = bar.left() + bar.width() * (d.temp_min - lo) / span
            b = bar.left() + bar.width() * (d.temp_max - lo) / span
            p.setBrush(rgb(255, 196, 90))
            p.drawRoundedRect(QRectF(a, bar.top(), max(6, b - a), bar.height()), 3, 3)
            if d.precip_probability >= 10:
                p.setFont(_font(17))
                p.setPen(RAIN_BLUE)
                p.drawText(QRectF(x, card.top() + 162, col, 24), Qt.AlignCenter, f"{d.precip_probability}%")
