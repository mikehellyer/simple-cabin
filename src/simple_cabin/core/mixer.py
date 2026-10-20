"""Mixing every sound into one stream.

The app used to give each sound its own audio stream (Qt's QSoundEffect).
On a Raspberry Pi only the long, looping fire ever played: the short tick,
tock and chime streams were silent. So now everything is mixed here, by
the app itself, into a single continuous stream, and each sound can be
placed exactly: a tick lands on the very sample of the real second.

Plain numpy, no Qt: the audio engine asks for the next stretch of sound
with render(), saying when its first frame will be heard.
"""
from __future__ import annotations

import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

RATE = 44100
CHANNELS = 2


def load_wav(path: Path, rate: int = RATE) -> np.ndarray:
    """A WAV file as float32 frames × 2 channels, at the mixer's rate."""
    with wave.open(str(path)) as w:
        channels, width, file_rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path.name}: only 16-bit WAV is supported")
    data = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    data = data.reshape(-1, channels)
    if channels == 1:
        data = np.repeat(data, 2, axis=1)
    elif channels > 2:
        data = data[:, :2]
    if file_rate != rate:  # simple linear resampling
        n = int(len(data) * rate / file_rate)
        src = np.linspace(0, len(data) - 1, n)
        data = np.stack([np.interp(src, np.arange(len(data)), data[:, c]) for c in range(2)], axis=1).astype(np.float32)
    return np.ascontiguousarray(data)


@dataclass
class _Voice:
    name: str
    start: float  # wall-clock time it should start (seconds since the epoch)
    loop: bool
    pos: int = -1  # next frame to play; -1 until it has started


class Mixer:
    def __init__(self, level: Callable[[str], float], rate: int = RATE):
        self.rate = rate
        self._level = level  # name -> 0..1 gain, asked every block (so sliders apply at once)
        self._sounds: dict[str, np.ndarray] = {}
        self._voices: list[_Voice] = []
        self.muted = False
        # The audio thread renders while the rest of the app starts and
        # stops sounds, so every change goes through this lock.
        self._lock = threading.Lock()

    # --- sounds

    def add(self, name: str, samples: np.ndarray) -> None:
        with self._lock:
            self._sounds[name] = samples

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._sounds

    # --- playing

    def play(self, name: str, at: float = 0.0, loop: bool = False) -> None:
        """Start a sound at wall-clock time at (0: as soon as possible)."""
        with self._lock:
            if loop and any(v.name == name for v in self._voices):
                return
            self._voices.append(_Voice(name, at, loop))

    def stop(self, name: str) -> None:
        with self._lock:
            self._voices = [v for v in self._voices if v.name != name]

    def stop_matching(self, test: Callable[[str], bool]) -> None:
        with self._lock:
            self._voices = [v for v in self._voices if not test(v.name)]

    def is_playing(self, name: str) -> bool:
        with self._lock:
            return any(v.name == name for v in self._voices)

    # --- mixing

    def render(self, frames: int, start_time: float) -> bytes:
        """The next frames of sound as 16-bit stereo, the first of which will
        be heard at start_time (wall clock)."""
        with self._lock:
            return self._render(frames, start_time)

    def _render(self, frames: int, start_time: float) -> bytes:
        out = np.zeros((frames, 2), np.float32)
        end_time = start_time + frames / self.rate
        keep = []
        for v in self._voices:
            samples = self._sounds.get(v.name)
            if samples is None or len(samples) == 0:
                keep.append(v)  # not loaded yet: wait for it
                continue
            if v.pos < 0:
                if v.start >= end_time:
                    keep.append(v)  # not due yet
                    continue
                offset = max(0, int(round((v.start - start_time) * self.rate)))
                v.pos = 0
            else:
                offset = 0
            gain = self._level(v.name)
            i = offset
            finished = False
            while i < frames:
                take = min(frames - i, len(samples) - v.pos)
                if gain > 0:
                    out[i : i + take] += samples[v.pos : v.pos + take] * gain
                v.pos += take
                i += take
                if v.pos >= len(samples):
                    if v.loop:
                        v.pos = 0
                    else:
                        finished = True
                        break
            if not finished:
                keep.append(v)
        self._voices = keep
        if self.muted:
            out[:] = 0
        # Soft-limit, so a chime over the fire and a tick never crackles:
        # untouched below 0.75, then eased smoothly towards full scale.
        loud = np.abs(out) > 0.75
        if loud.any():
            x = out[loud]
            out[loud] = np.sign(x) * (0.75 + 0.25 * np.tanh((np.abs(x) - 0.75) / 0.25))
        return (out * 32767).astype("<i2").tobytes()


def seconds_in(start_time: float, end_time: float) -> list[int]:
    """The whole seconds (wall clock) falling in [start_time, end_time)."""
    first = int(np.ceil(start_time))
    return list(range(first, int(np.ceil(end_time))))
