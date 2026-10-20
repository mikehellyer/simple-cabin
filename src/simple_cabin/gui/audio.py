"""Playing the cabin's sounds: the clock's tick-tock on every real second,
the fire, the chimes, and rain and thunder when the weather brings them."""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QSoundEffect

from simple_cabin.core import chimes, synth
from simple_cabin.gui.workers import BackgroundRunner

LOOPS = ("fire", "rain")


class AudioEngine(QObject):
    chime_started = Signal(str)

    def __init__(self, sound_dir: Path, runner: BackgroundRunner, parent=None):
        super().__init__(parent)
        self._dir = sound_dir
        self._runner = runner
        self._effects: dict[str, QSoundEffect] = {}
        self._preparing: set[str] = set()
        self._master, self._tick, self._fire, self._chime = 0.8, 0.7, 0.22, 0.75
        self._muted = False
        self._quarters = False
        self._rain = 0.0
        self._play_when_ready: Optional[str] = None
        self._next_second = 0
        self._voice = synth.DEFAULT_CLOCK_VOICE

        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.PreciseTimer)
        self._tick_timer.setSingleShot(True)
        self._tick_timer.timeout.connect(self._on_second)

    # --- setup

    def start(self) -> None:
        voice = self._voice

        def make_basics():
            names = (*synth.beat_names(voice), "fire", "rain", "thunder", "firework")
            synth.remove_stale(self._dir)
            return {name: synth.ensure_sound(name, self._dir) for name in names}

        self._runner.run(make_basics, self._on_basics_ready, lambda error: print(f"sound synthesis failed: {error}"))
        self._schedule_next_second()
        self._prepare_upcoming_chime()

    def _on_basics_ready(self, paths: dict) -> None:
        for name, path in paths.items():
            self._load(name, path)
        self._effects["fire"].play()
        self._apply_rain()

    def _load(self, name: str, path: Path) -> None:
        self._preparing.discard(name)
        effect = QSoundEffect(self)
        effect.setSource(QUrl.fromLocalFile(str(path)))
        if name in LOOPS:
            effect.setLoopCount(QSoundEffect.Loop.Infinite.value)
        self._effects[name] = effect
        self._apply_volume(name)
        if self._play_when_ready == name:
            self._play_when_ready = None
            self._play_chime(name)

    def _prepare(self, name: str) -> None:
        if name in self._effects or name in self._preparing:
            return
        self._preparing.add(name)
        self._runner.run(lambda: synth.ensure_sound(name, self._dir), lambda path: self._load(name, path),
                         lambda error: self._preparing.discard(name))

    # --- volume

    def set_volumes(self, master: int, tick: int, fire: int, chime: int) -> None:
        self._master, self._tick, self._fire, self._chime = master / 100, tick / 100, fire / 100, chime / 100
        for name in self._effects:
            self._apply_volume(name)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        for effect in self._effects.values():
            effect.setMuted(muted)

    def set_clock_voice(self, voice: str) -> None:
        """Change how the clock ticks (makes the new sounds if need be)."""
        if voice == self._voice:
            return
        self._voice = voice
        if self._effects:  # started already: load the new beats now
            for name in synth.beat_names(voice):
                self._prepare(name)

    def set_quarter_chimes(self, enabled: bool) -> None:
        self._quarters = enabled
        self._prepare_upcoming_chime()

    def _level(self, name: str) -> float:
        if name.startswith(("tick", "tock")):
            part = self._tick
        elif name == "fire":
            part = self._fire
        elif name == "rain":
            part = self._fire * 0.8 * self._rain
        elif name in ("thunder", "firework"):
            part = self._chime * 0.6
        else:
            part = self._chime
        # A gentle curve, so the sliders feel even to the ear.
        level = (self._master * part) ** 1.5
        if name == "fire":
            level *= synth.FIRE_GAIN
        return max(0.0, min(1.0, level))

    def _apply_volume(self, name: str) -> None:
        effect = self._effects.get(name)
        if effect is not None:
            effect.setVolume(self._level(name))
            effect.setMuted(self._muted)

    # --- weather sounds

    def set_rain(self, intensity: float) -> None:
        self._rain = intensity
        self._apply_rain()

    def _apply_rain(self) -> None:
        effect = self._effects.get("rain")
        if effect is None:
            return
        self._apply_volume("rain")
        if self._rain > 0 and not effect.isPlaying():
            effect.play()
        elif self._rain <= 0 and effect.isPlaying():
            effect.stop()

    def thunder(self, delay_ms: int) -> None:
        effect = self._effects.get("thunder")
        if effect is not None:
            QTimer.singleShot(delay_ms, effect.play)

    def firework(self, delay_ms: int) -> None:
        effect = self._effects.get("firework")
        if effect is not None:
            QTimer.singleShot(delay_ms, effect.play)

    # --- the clock

    def _schedule_next_second(self) -> None:
        now = time.time()
        if not self._next_second or abs(self._next_second - now) > 2:
            self._next_second = int(now) + 1  # (re)synchronise, e.g. after the machine slept
        self._tick_timer.start(max(0, int((self._next_second - now) * 1000)))

    def _on_second(self) -> None:
        second = self._next_second
        self._next_second += 1
        self._schedule_next_second()

        # The pendulum (see clock.pendulum_angle) ends its swing on the
        # second: one side on even seconds (tick), the other on odd (tock).
        beats = synth.beat_names(self._voice)
        effect = self._effects.get(beats[second % len(beats)])
        if effect is not None:
            effect.play()

        at = datetime.fromtimestamp(second)
        if at.second == 0:
            key = chimes.chime_for(at.hour, at.minute, self._quarters)
            if key:
                self._play_chime(key)
            self._prepare_upcoming_chime()

    def _prepare_upcoming_chime(self) -> None:
        """Make the next chime's sound in good time (the long ones take a
        second or two to synthesise the first time)."""
        now = datetime.now().replace(second=0, microsecond=0)
        for minutes_ahead in range(1, 17):
            at = now + timedelta(minutes=minutes_ahead)
            key = chimes.chime_for(at.hour, at.minute, self._quarters)
            if key:
                self._prepare(key)
                return

    def _play_chime(self, key: str) -> None:
        effect = self._effects.get(key)
        if effect is None:
            self._play_when_ready = key
            self._prepare(key)
            return
        effect.play()
        self.chime_started.emit(key)

    def play_hour_chime_now(self) -> None:
        """Ring the current hour, so the chime can be heard on demand."""
        self._play_chime(f"hour_{chimes.strike_count(datetime.now().hour)}")

    def stop_chimes(self) -> None:
        for name, effect in self._effects.items():
            if name.startswith(("hour_", "quarter_")):
                effect.stop()
