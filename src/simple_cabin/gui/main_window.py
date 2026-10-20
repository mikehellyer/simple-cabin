"""The main window: the stage, the update banner, keyboard shortcuts,
the right-click menu, and keeping the weather up to date."""
from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from platformdirs import user_cache_dir
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox, QVBoxLayout, QWidget

from simple_cabin import __version__
from simple_cabin.core import chimes, seasons, sky
from simple_cabin.core import weather as wx
from simple_cabin.core.diagnostics import log_event
from simple_cabin.core.keep_awake import KeepAwake
from simple_cabin.core.platform_info import is_raspberry_pi
from simple_cabin.core.self_update import download_asset, find_asset_for_this_platform, launch_installer
from simple_cabin.core.settings import SettingsStore
from simple_cabin.core.updater import API_TIMEOUT_SECONDS, check_for_update
from simple_cabin.gui import textures
from simple_cabin.gui.audio import AudioEngine
from simple_cabin.gui.settings_dialog import SettingsDialog
from simple_cabin.gui.stage import INSIDE, OUTSIDE, WEATHER, Stage
from simple_cabin.gui.update_banner import UpdateBanner
from simple_cabin.gui.workers import BackgroundRunner

UPDATE_OWNER = "mikehellyer"
UPDATE_REPO = "simple-cabin"
BACKGROUND_JOIN_TIMEOUT_MS = (max(API_TIMEOUT_SECONDS, wx.TIMEOUT_SECONDS) + 1) * 1000
ICON_PATH = Path(__file__).parent / "resources" / "icon.png"
WEATHER_REFRESH_MS = 15 * 60 * 1000
WEATHER_RETRY_MS = 2 * 60 * 1000
CONDITIONS_REFRESH_MS = 20 * 1000

NUMBERS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple-Cabin")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1280, 760)

        self._store = SettingsStore()
        self._runner = BackgroundRunner(self)
        self._keep_awake = KeepAwake()
        self._pending_update = None
        cache = Path(user_cache_dir("Simple-Cabin"))
        textures.set_cache_dir(cache / "textures")
        self._forecast_path = cache / "forecast.json"
        self._forecast: Optional[wx.Forecast] = wx.load_forecast(self._forecast_path)
        self._location: Optional[wx.Location] = None
        self._fetching = False
        self._weather_preview: Optional[str] = None
        self._time_preview: Optional[str] = None
        self._decoration_preview: Optional[str] = None  # a season, "off", or None for the real date

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._update_banner = UpdateBanner()
        self._update_banner.update_clicked.connect(self._start_update)
        layout.addWidget(self._update_banner)
        self._stage = Stage()
        self._stage.setContextMenuPolicy(Qt.CustomContextMenu)
        self._stage.customContextMenuRequested.connect(self._show_menu)
        self._stage.thunder.connect(lambda: self._audio.thunder(random.randint(900, 3200)))
        self._stage.firework.connect(lambda: self._audio.firework(random.randint(700, 1600)))
        layout.addWidget(self._stage, 1)
        self.setCentralWidget(central)

        self._audio = AudioEngine(cache / "sounds", self._runner, self)
        self._audio.chime_started.connect(self._on_chime)

        self._build_actions()
        self._apply_settings()
        self._stage.set_forecast(self._forecast, "" if self._forecast else "Fetching the weather…")
        self._refresh_conditions()

        self._conditions_timer = QTimer(self)
        self._conditions_timer.timeout.connect(self._refresh_conditions)
        self._conditions_timer.start(CONDITIONS_REFRESH_MS)
        self._weather_timer = QTimer(self)
        self._weather_timer.setSingleShot(True)
        self._weather_timer.timeout.connect(self._update_weather)

        self._audio.start()
        self._update_weather()
        self._check_for_updates()

    # --- actions and the menu

    def _action(self, text: str, keys, slot, checkable: bool = False) -> QAction:
        action = QAction(text, self)
        if keys:
            action.setShortcuts([QKeySequence(k) for k in (keys if isinstance(keys, (list, tuple)) else [keys])])
        action.setShortcutContext(Qt.WindowShortcut)
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        self._act_inside = self._action("Inside the cabin", "I", lambda: self._stage.set_mode(INSIDE))
        self._act_outside = self._action("Outside by the lake", "O", lambda: self._stage.set_mode(OUTSIDE))
        self._act_toggle = self._action("Switch inside / outside", ["Space", "Tab"], self._stage.toggle_view)
        self._act_weather = self._action("Weather and clock screen", "W", self._stage.toggle_weather)
        self._act_full = self._action("Full screen", ["F", "F11"], self._toggle_full_screen, checkable=True)
        self._act_mute = self._action("Mute", "M", self._toggle_mute, checkable=True)
        self._act_chime = self._action("Ring the hour chime now", "C", self._audio.play_hour_chime_now)
        self._act_preview_weather = self._action("Preview another weather", "P", self._cycle_weather_preview)
        self._act_preview_time = self._action("Preview another time of day", "T", self._cycle_time_preview)
        self._act_preview_decor = self._action("Preview seasonal decorations", "D", self._cycle_decoration_preview)
        self._act_refresh = self._action("Refresh the weather now", "R", self._update_weather)
        self._act_settings = self._action("Settings…", ["S", "Ctrl+,"], self._open_settings)
        self._act_about = self._action("About Simple-Cabin", None, self._about)
        self._act_quit = self._action("Quit", "Ctrl+Q", self.close)
        self._action("", "Escape", self._on_escape)

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        for action in (self._act_inside, self._act_outside, self._act_weather, None, self._act_full, self._act_mute,
                       self._act_chime, None, self._act_preview_weather, self._act_preview_time, self._act_preview_decor, self._act_refresh,
                       None, self._act_settings, self._act_about, self._act_quit):
            menu.addSeparator() if action is None else menu.addAction(action)
        menu.exec(self._stage.mapToGlobal(pos))

    def _on_escape(self) -> None:
        if self._stage.leave_weather():
            return
        if self.isFullScreen():
            self._toggle_full_screen()

    def _toggle_full_screen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        self._act_full.setChecked(self.isFullScreen())

    def _toggle_mute(self) -> None:
        muted = not self._store.settings.muted
        self._store.update(muted=muted)
        self._audio.set_muted(muted)
        self._act_mute.setChecked(muted)
        self._stage.toast("Sound off" if muted else "Sound on")

    def _on_chime(self, key: str) -> None:
        count = chimes.strikes(key)
        if count:
            # Come in to watch the clock strike.
            if self._stage.mode == OUTSIDE:
                self._stage.set_mode(INSIDE)
            self._stage.toast(f"The clock strikes {NUMBERS[count - 1]}", 6)

    # --- previews (to see each weather without waiting for it)

    def _cycle_weather_preview(self) -> None:
        names = [None, *wx.PREVIEWS]
        self._weather_preview = names[(names.index(self._weather_preview) + 1) % len(names)]
        self._stage.toast(f"Weather preview: {self._weather_preview}  (P for the next)" if self._weather_preview else "Live weather")
        self._refresh_conditions()

    def _cycle_decoration_preview(self) -> None:
        names = [None, *seasons.ALL, "off"]
        self._decoration_preview = names[(names.index(self._decoration_preview) + 1) % len(names)]
        if self._decoration_preview is None:
            self._stage.toast("Decorations for today's date")
        elif self._decoration_preview == "off":
            self._stage.toast("Decorations preview: none  (D for the next)")
        else:
            self._stage.toast(f"Decorations preview: {seasons.NAMES[self._decoration_preview]}  (D for the next)")
        self._refresh_conditions()

    def _cycle_time_preview(self) -> None:
        names = [None, *sky.PREVIEW_LIGHTS]
        self._time_preview = names[(names.index(self._time_preview) + 1) % len(names)]
        self._stage.toast(f"Time-of-day preview: {self._time_preview}  (T for the next)" if self._time_preview else "Live time of day")
        self._refresh_conditions()

    # --- settings

    def _apply_settings(self) -> None:
        s = self._store.settings
        self._audio.set_volumes(s.master_volume, s.tick_volume, s.fire_volume, s.chime_volume)
        self._audio.set_muted(s.muted)
        self._audio.set_quarter_chimes(s.quarter_chimes)
        self._audio.set_clock_voice(s.clock_voice)
        self._act_mute.setChecked(s.muted)
        self._stage.auto_switch = s.auto_switch_views
        light = s.graphics == "light" or (s.graphics == "auto" and is_raspberry_pi())
        self._stage.set_light_graphics(light)
        if s.keep_awake and not self._keep_awake.active:
            log_event(f"keeping the screen awake via {self._keep_awake.start() or 'nothing (not supported here)'}")
        elif not s.keep_awake and self._keep_awake.active:
            self._keep_awake.stop()
            log_event("no longer keeping the screen awake")
        self._stage.inside_seconds = s.inside_minutes * 60
        self._stage.outside_seconds = s.outside_seconds
        self._stage.temperature_unit = s.temperature_unit
        board = self._stage.board
        board.temperature_unit, board.wind_unit, board.clock_24h = s.temperature_unit, s.wind_unit, s.clock_24h

    def _open_settings(self) -> None:
        s = self._store.settings
        before = (s.location_mode, s.location_name, s.latitude, s.longitude)
        dialog = SettingsDialog(s, self._runner, self)
        dialog.volumes_changed.connect(self._audio.set_volumes)
        dialog.play_chime.connect(self._audio.play_hour_chime_now)
        dialog.voice_changed.connect(self._audio.set_clock_voice)
        if dialog.exec():
            self._store.update(**dialog.values())
        self._apply_settings()  # also undoes any live volume preview after Cancel
        self._refresh_conditions()  # (decorations on or off)
        s = self._store.settings
        if (s.location_mode, s.location_name, s.latitude, s.longitude) != before:
            self._location = None
            self._stage.set_forecast(self._forecast, "Fetching the weather…")
            self._update_weather()

    # --- weather

    def _update_weather(self) -> None:
        if self._fetching:
            return
        self._fetching = True
        self._weather_timer.stop()
        s = self._store.settings
        known = self._location
        if s.location_mode == "manual":
            known = wx.Location(s.location_name, s.latitude, s.longitude)

        def job():
            location = known or wx.locate_by_ip()
            if location is None:
                return None, None
            return location, wx.fetch_forecast(location)

        self._runner.run(job, self._on_weather, lambda error: self._on_weather((None, None)))

    def _on_weather(self, result) -> None:
        self._fetching = False
        location, forecast = result
        if location is not None:
            self._location = location
        if forecast is not None:
            self._forecast = forecast
            wx.save_forecast(forecast, self._forecast_path)
            self._stage.set_forecast(forecast, "")
            self._weather_timer.start(WEATHER_REFRESH_MS)
        else:
            if self._forecast is not None:
                status = "offline — showing the last forecast"
            elif location is None:
                status = "Couldn't work out where you are — choose a place in Settings (S)"
            else:
                status = "Weather unavailable — check your connection (retrying)"
            self._stage.set_forecast(self._forecast, status)
            self._weather_timer.start(WEATHER_RETRY_MS)
        self._refresh_conditions()

    def _refresh_conditions(self) -> None:
        f = self._forecast
        weather = wx.PREVIEWS[self._weather_preview] if self._weather_preview else wx.scene_weather(f)
        if self._time_preview:
            light = sky.PREVIEW_LIGHTS[self._time_preview]
        else:
            now, rise, set_ = datetime.now(), None, None
            if f is not None:
                now = f.local_now()
                today = f.today()
                if today and today.sunrise and today.sunset:
                    rise, set_ = datetime.fromisoformat(today.sunrise), datetime.fromisoformat(today.sunset)
            light = sky.light_at(now, rise, set_)
        self._stage.set_conditions(weather, light, sky.moon_phase())
        if self._decoration_preview is not None:
            kind = None if self._decoration_preview == "off" else self._decoration_preview
            fireworks = kind == seasons.NEW_YEAR
        elif self._store.settings.decorations:
            today = datetime.now()
            kind, fireworks = seasons.decoration_for(today.date()), seasons.fireworks_now(today)
        else:
            kind, fireworks = None, False
        self._stage.set_decoration(kind, fireworks)
        self._audio.set_rain(weather.rain)

    # --- about & updates

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Simple-Cabin",
            f"<b>Simple-Cabin</b> v{__version__}<br><br>"
            "A log cabin by a forest lake, with a grandfather clock that keeps the real time "
            "and chimes the hours, a crackling fire, and the real local weather outside.<br><br>"
            "Weather data by <a href='https://open-meteo.com/'>Open-Meteo.com</a> (CC BY 4.0).<br><br>"
            "By Mike Hellyer, built with Claude Code.",
        )

    def _check_for_updates(self) -> None:
        self._runner.run(
            lambda: check_for_update(__version__, UPDATE_OWNER, UPDATE_REPO),
            self._on_update_checked,
            lambda error: None,
        )

    def _on_update_checked(self, info) -> None:
        if info:
            self._pending_update = info
            self._update_banner.announce(info.version)

    def _start_update(self) -> None:
        if self._pending_update is None:
            return
        asset_url = find_asset_for_this_platform(self._pending_update.assets)
        if asset_url is None:
            self._update_banner.set_status(f"No installer for this platform — see {self._pending_update.url}")
            return
        self._update_banner.set_busy(True, "Downloading…")
        self._runner.run(lambda: download_asset(asset_url), self._on_update_downloaded, lambda error: self._on_update_downloaded(None))

    def _on_update_downloaded(self, path) -> None:
        if path is None:
            self._update_banner.set_status("Couldn't download the update — try again")
            self._update_banner.set_busy(False)
            return
        try:
            process = launch_installer(path)
        except OSError:
            self._update_banner.set_status(f"Downloaded to {path} — open it manually")
            self._update_banner.set_busy(False)
            return

        self._update_banner.set_status("Installer launched — closing to finish…")
        if sys.platform not in ("win32", "darwin") and process is not None:
            # Linux: wait for pkexec/apt to finish before quitting — quitting
            # immediately can kill its password prompt before it's answered.
            self._runner.run(lambda: (path, self._wait_for_installer(process)), self._on_installer_finished)
        else:
            QTimer.singleShot(1500, self.close)

    @staticmethod
    def _wait_for_installer(process) -> tuple[int, str]:
        returncode = process.wait()
        stderr_text = process.stderr.read().strip() if process.stderr is not None else ""
        return returncode, stderr_text

    def _on_installer_finished(self, result) -> None:
        path, (returncode, stderr_text) = result
        if returncode == 0:
            self.close()
            return
        detail = f": {stderr_text}" if stderr_text else f" (exit code {returncode})"
        self._update_banner.set_status(f"Update didn't install{detail} — installer is at {path}")
        self._update_banner.set_busy(False)

    def closeEvent(self, event) -> None:
        self._keep_awake.stop()
        self._store.save()
        self._runner.shutdown(BACKGROUND_JOIN_TIMEOUT_MS)
        super().closeEvent(event)
