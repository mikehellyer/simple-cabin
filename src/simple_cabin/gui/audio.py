"""Playing the cabin's sounds: the clock's tick-tock on every real second,
the fire, the chimes, and rain, thunder and fireworks when they happen.

Everything is mixed (core.mixer) into one continuous stream on a single
QAudioSink. The sink lives on its own thread, kept topped up a few
hundredths of a second at a time, so a slow frame of animation can never
starve it (on a Raspberry Pi that made the tick-tock stutter now and then).
A tick is placed on the sample that will be heard on the real second,
using how much sound is already queued ahead of it.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from simple_cabin.core import chimes, synth
from simple_cabin.core.diagnostics import log_event
from simple_cabin.core.mixer import RATE, Mixer, load_wav

BUFFER_SECONDS = 1.0  # sound queued ahead: plenty to ride out a busy moment
FILL_MS = 20
RETRY_SECONDS = 5.0


class _Output(QObject):
    """Owns the audio sink, on the audio thread, and keeps it fed."""

    def __init__(self, engine: "AudioEngine"):
        super().__init__()
        self._engine = engine
        self._sink: Optional[QAudioSink] = None
        self._io = None
        self._timer: Optional[QTimer] = None
        self._next_retry = 0.0
        self._last_second = 0
        self._t0: Optional[float] = None  # wall-clock time of the stream's first frame
        self._written = 0  # frames written since then

    @Slot()
    def open(self) -> None:
        self._open_sink()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._fill)
        self._timer.start(FILL_MS)

    def _open_sink(self) -> None:
        engine = self._engine
        device = QMediaDevices.defaultAudioOutput()
        engine.device_name = device.description() or "(no audio output)"
        fmt = QAudioFormat()
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        for rate in (engine.rate, RATE, 48000, device.preferredFormat().sampleRate()):
            fmt.setSampleRate(rate)
            if device.isFormatSupported(fmt):
                break
        engine.use_rate(fmt.sampleRate())
        self._sink = QAudioSink(device, fmt, self)
        self._sink.setBufferSize(int(engine.rate * 4 * BUFFER_SECONDS))
        self._io = self._sink.start()
        engine.status = f"{self._sink.state().name} on {engine.device_name} at {engine.rate} Hz"
        engine.opened.set()
        log_event(f"audio: {engine.status} (buffer {self._sink.bufferSize()} bytes, error {self._sink.error().name})")

    def state_text(self) -> str:
        if self._sink is None:
            return "no sink"
        return f"{self._sink.state().name}, error {self._sink.error().name}"

    @Slot()
    def _fill(self) -> None:
        sink, engine = self._sink, self._engine
        if sink is None or self._io is None:
            return
        if sink.state() == QAudio.State.StoppedState and sink.error() != QAudio.Error.NoError:
            now = time.monotonic()
            if now >= self._next_retry:  # the device went away: try again now and then
                self._next_retry = now + RETRY_SECONDS
                log_event(f"audio stopped ({sink.error().name}); reopening")
                sink.stop()
                self._open_sink()
                self._t0, self._written = None, 0
            return
        free = sink.bytesFree()
        frames = free // 4
        if frames < 256:
            return
        # When will this stretch be heard? Each stretch follows straight on
        # from the last (start = t0 + frames written so far), and t0 is
        # nudged gently towards what the sink says is queued: that report
        # wobbles by tens of milliseconds, which would put beats early or
        # late, but over hours it keeps the stream on the real clock.
        queued = max(0, sink.bufferSize() - free) // 4
        measured = time.time() + queued / engine.rate
        predicted = self._t0 + self._written / engine.rate if self._t0 is not None else None
        if predicted is None or abs(predicted - measured) > 0.5:
            self._t0 = measured - self._written / engine.rate  # (re)synchronise
        else:
            self._t0 += (measured - predicted) * 0.01
        start = self._t0 + self._written / engine.rate
        end = start + frames / engine.rate
        # Every second up to the end of this stretch that hasn't had its
        # beat yet. (Not just the seconds inside [start, end): the estimate
        # of start wobbles a little between top-ups, and a second falling
        # in the gap would lose its tick.) A beat that's a moment late just
        # plays at once; after a long gap (the machine slept) start afresh.
        if self._last_second < start - 2:
            self._last_second = int(start) - 1
        for second in range(self._last_second + 1, int(math.ceil(end))):
            self._last_second = second
            engine.on_second(second)
        self._io.write(engine.mixer.render(frames, start))
        self._written += frames

    @Slot()
    def close(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        if self._sink is not None:
            self._sink.stop()


class AudioEngine(QObject):
    chime_started = Signal(str)
    _close_requested = Signal()

    def __init__(self, sound_dir: Path, runner=None, parent=None):
        super().__init__(parent)
        self._dir = sound_dir
        self._preparing: set[str] = set()
        self._lock = threading.Lock()
        self._master, self._tick, self._fire, self._chime = 0.8, 0.7, 0.22, 0.75
        self._quarters = False
        self._rain = 0.0
        self._voice = synth.DEFAULT_CLOCK_VOICE

        self.rate = RATE
        self.device_name = ""
        self.status = "not started"
        self.opened = threading.Event()
        self.mixer = Mixer(self._level, RATE)

        self._thread: Optional[QThread] = None
        self._output: Optional[_Output] = None

    # --- setup

    def start(self) -> None:
        self._thread = QThread()
        self._thread.setObjectName("audio")
        self._output = _Output(self)
        self._output.moveToThread(self._thread)
        self._thread.started.connect(self._output.open)
        self._close_requested.connect(self._output.close)
        self._thread.start()
        self.opened.wait(5.0)  # so the rate is known before loading sounds
        self._thread.setPriority(QThread.TimeCriticalPriority)

        voice = self._voice

        def load_basics() -> None:
            names = (*synth.beat_names(voice), "fire", "rain", "thunder", "firework")
            try:
                synth.remove_stale(self._dir)
                for name in names:
                    self.mixer.add(name, load_wav(synth.ensure_sound(name, self._dir), self.rate))
            except Exception as error:
                log_event(f"sound loading failed: {error}")
                return
            self.mixer.play("fire", loop=True)
            self._apply_rain()

        threading.Thread(target=load_basics, daemon=True).start()
        self._prepare_upcoming_chime()

    def use_rate(self, rate: int) -> None:
        """(audio thread) The output's sample rate; sounds are loaded at it."""
        if rate != self.rate:
            self.rate = rate
            self.mixer = Mixer(self._level, rate)

    def state_text(self) -> str:
        return self._output.state_text() if self._output is not None else "no sink"

    def _prepare(self, name: str) -> None:
        """Make (if need be) and load a sound, on a plain background thread."""
        with self._lock:
            if self.mixer.has(name) or name in self._preparing:
                return
            self._preparing.add(name)

        def work() -> None:
            try:
                self.mixer.add(name, load_wav(synth.ensure_sound(name, self._dir), self.rate))
            except Exception as error:
                log_event(f"couldn't make the {name} sound: {error}")
            finally:
                with self._lock:
                    self._preparing.discard(name)

        threading.Thread(target=work, daemon=True).start()

    # --- the clock (called on the audio thread, as each second is queued)

    def on_second(self, second: int) -> None:
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
        self.chime_started.emit(key)  # (reaches the window on its own thread)

    def play_hour_chime_now(self) -> None:
        """Ring the current hour, so the chime can be heard on demand."""
        self._play_chime(f"hour_{chimes.strike_count(datetime.now().hour)}")

    def stop_chimes(self) -> None:
        self.mixer.stop_matching(lambda name: name.startswith(("hour_", "quarter_")))

    def shutdown(self) -> None:
        if self._thread is None:
            return
        self._close_requested.emit()  # stops the timer and sink on their own thread
        self._thread.quit()
        self._thread.wait(3000)
        self._thread = None
