"""Playing the cabin's sounds: the clock's tick-tock on every real second,
the fire, the chimes, and rain, thunder and fireworks when they happen.

Everything is mixed (core.mixer) into one continuous stream on a single
QAudioSink, kept topped up a few hundredths of a second at a time. A tick
is placed on the sample that will be heard on the real second, using how
much sound is already queued ahead of it.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from simple_cabin.core import chimes, synth
from simple_cabin.core.diagnostics import log_event
from simple_cabin.core.mixer import RATE, Mixer, load_wav, seconds_in
from simple_cabin.gui.workers import BackgroundRunner

BUFFER_SECONDS = 0.5  # sound queued ahead: enough to ride out a slow frame on a Pi
FILL_MS = 15
RETRY_SECONDS = 5.0


class AudioEngine(QObject):
    chime_started = Signal(str)

    def __init__(self, sound_dir: Path, runner: BackgroundRunner, parent=None):
        super().__init__(parent)
        self._dir = sound_dir
        self._runner = runner
        self._preparing: set[str] = set()
        self._master, self._tick, self._fire, self._chime = 0.8, 0.7, 0.22, 0.75
        self._quarters = False
        self._rain = 0.0
        self._voice = synth.DEFAULT_CLOCK_VOICE
        self._last_second = 0

        self._sink: Optional[QAudioSink] = None
        self._io = None
        self.rate = RATE
        self.device_name = ""
        self.status = "not started"
        self._next_retry = 0.0
        self.mixer = Mixer(self._level, RATE)

        self._fill_timer = QTimer(self)
        self._fill_timer.setTimerType(Qt.PreciseTimer)
        self._fill_timer.timeout.connect(self._fill)

    # --- setup

    def start(self) -> None:
        self._open_output()
        voice = self._voice

        def make_basics():
            names = (*synth.beat_names(voice), "fire", "rain", "thunder", "firework")
            synth.remove_stale(self._dir)
            return {name: load_wav(synth.ensure_sound(name, self._dir), self.rate) for name in names}

        self._runner.run(make_basics, self._on_basics_ready, lambda error: log_event(f"sound loading failed: {error}"))
        self._prepare_upcoming_chime()
        self._fill_timer.start(FILL_MS)

    def _open_output(self) -> None:
        device = QMediaDevices.defaultAudioOutput()
        self.device_name = device.description() or "(no audio output)"
        fmt = QAudioFormat()
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        for rate in (RATE, 48000, device.preferredFormat().sampleRate()):
            fmt.setSampleRate(rate)
            if device.isFormatSupported(fmt):
                break
        if fmt.sampleRate() != self.rate:  # sounds already loaded are at the old rate: start again at this one
            self.rate = fmt.sampleRate()
            self.mixer = Mixer(self._level, self.rate)
        self._sink = QAudioSink(device, fmt, self)
        self._sink.setBufferSize(int(self.rate * 4 * BUFFER_SECONDS))
        self._io = self._sink.start()
        self.status = f"{self._state_name()} on {self.device_name} at {self.rate} Hz"
        log_event(f"audio: {self.status} (buffer {self._sink.bufferSize()} bytes, error {self._sink.error().name})")

    def _state_name(self) -> str:
        return self._sink.state().name if self._sink is not None else "no sink"

    def _on_basics_ready(self, sounds: dict) -> None:
        for name, samples in sounds.items():
            self.mixer.add(name, samples)
        self.mixer.play("fire", loop=True)
        self._apply_rain()

    def _prepare(self, name: str) -> None:
        if self.mixer.has(name) or name in self._preparing:
            return
        self._preparing.add(name)

        def done(samples) -> None:
            self._preparing.discard(name)
            self.mixer.add(name, samples)

        self._runner.run(lambda: load_wav(synth.ensure_sound(name, self._dir), self.rate), done,
                         lambda error: self._preparing.discard(name))

    # --- the stream

    def _fill(self) -> None:
        """Top up the stream, placing any ticks and chimes that fall in it."""
        sink = self._sink
        if sink is None or self._io is None:
            return
        if sink.state() == QAudio.State.StoppedState and sink.error() != QAudio.Error.NoError:
            now = time.monotonic()
            if now >= self._next_retry:  # the device went away: try again now and then
                self._next_retry = now + RETRY_SECONDS
                log_event(f"audio stopped ({sink.error().name}); reopening")
                sink.stop()
                self._open_output()
            return
        free = sink.bytesFree()
        frames = free // 4
        if frames < 256:
            return
        queued = max(0, sink.bufferSize() - free) // 4
        start = time.time() + queued / self.rate
        end = start + frames / self.rate
        for second in seconds_in(start, end):
            if second > self._last_second:
                self._last_second = second
                self._on_second(second)
        self._io.write(self.mixer.render(frames, start))

    def _on_second(self, second: int) -> None:
        # The pendulum (see clock.pendulum_angle) ends its swing on the
        # second: one side on even seconds (tick), the other on odd (tock).
        beats = synth.beat_names(self._voice)
        beat = beats[second % len(beats)]
        if self.mixer.has(beat):  # (no backlog of ticks while the sounds load)
            self.mixer.play(beat, at=second)
        at = datetime.fromtimestamp(second)
        if at.second == 0:
            key = chimes.chime_for(at.hour, at.minute, self._quarters)
            if key:
                self._play_chime(key, at=second)
            self._prepare_upcoming_chime()

    # --- volume

    def set_volumes(self, master: int, tick: int, fire: int, chime: int) -> None:
        self._master, self._tick, self._fire, self._chime = master / 100, tick / 100, fire / 100, chime / 100

    def set_muted(self, muted: bool) -> None:
        self.mixer.muted = muted

    def set_clock_voice(self, voice: str) -> None:
        """Change how the clock ticks (makes the new sounds if need be)."""
        if voice == self._voice:
            return
        self._voice = voice
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

    # --- weather sounds

    def set_rain(self, intensity: float) -> None:
        self._rain = intensity
        self._apply_rain()

    def _apply_rain(self) -> None:
        if self._rain > 0:
            self.mixer.play("rain", loop=True)
        else:
            self.mixer.stop("rain")

    def thunder(self, delay_ms: int) -> None:
        self.mixer.play("thunder", at=time.time() + delay_ms / 1000)

    def firework(self, delay_ms: int) -> None:
        self.mixer.play("firework", at=time.time() + delay_ms / 1000)

    # --- chimes

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

    def _play_chime(self, key: str, at: float = 0.0) -> None:
        self._prepare(key)  # (if it isn't ready it starts as soon as it is)
        self.mixer.play(key, at=at)
        self.chime_started.emit(key)

    def play_hour_chime_now(self) -> None:
        """Ring the current hour, so the chime can be heard on demand."""
        self._play_chime(f"hour_{chimes.strike_count(datetime.now().hour)}")

    def stop_chimes(self) -> None:
        self.mixer.stop_matching(lambda name: name.startswith(("hour_", "quarter_")))

    def shutdown(self) -> None:
        self._fill_timer.stop()
        if self._sink is not None:
            self._sink.stop()
