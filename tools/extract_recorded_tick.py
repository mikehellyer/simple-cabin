"""One-off tool: cut the "Recorded" clock voice out of a recording.

Finds each beat's onset near the given times, trims it with a short
pre-roll and fades, keeps the stereo, and levels all the clips together
(so the clock's natural strong/weak beat is kept). Writes the WAVs the app
plays to src/simple_cabin/sounds/.

Needs the dev-only decoder:  venv/bin/pip install miniaudio
Usage: venv/bin/python tools/extract_recorded_tick.py ~/Downloads/grandfather-clock.mp3
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import miniaudio
import numpy as np

RATE = 44100
OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "simple_cabin" / "sounds"

# Approximate times (s) of the beats to use, picked as the most typical and
# cleanest of each kind in grandfather-clock.mp3. The clock goes
# strong-weak-strong-weak, and its two strong beats differ slightly.
BEATS = {
    "tick_recorded": 0.305,  # strong, longer ring
    "tock_recorded": 15.305,  # weak
    "tick2_recorded": 8.308,  # strong, shorter ring
    "tock2_recorded": 13.305,  # weak
}
PRE_ROLL = 0.004
LENGTH = 0.45
FADE_IN = 0.002
FADE_OUT = 0.05
PEAK = 0.95


def onset(x: np.ndarray, near: float) -> int:
    """The sample where the beat's click begins, near a rough time."""
    mono = x.mean(1)
    lo, hi = int((near - 0.1) * RATE), int((near + 0.1) * RATE)
    seg = mono[lo:hi]
    f = np.fft.rfftfreq(len(seg), 1 / RATE)
    bright = np.abs(np.fft.irfft(np.fft.rfft(seg) * (f > 800), len(seg)))
    return lo + int(np.argmax(bright > bright.max() * 0.2))


def main(path: str) -> None:
    decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=2, sample_rate=RATE)
    x = np.array(decoded.samples, dtype=np.float32).reshape(-1, 2)
    clips = {}
    for name, near in BEATS.items():
        start = onset(x, near) - int(PRE_ROLL * RATE)
        clip = x[start : start + int(LENGTH * RATE)].astype(np.float64).copy()
        n_in, n_out = int(FADE_IN * RATE), int(FADE_OUT * RATE)
        clip[:n_in] *= np.linspace(0, 1, n_in)[:, None]
        clip[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
        clips[name] = clip
    gain = PEAK / max(np.abs(c).max() for c in clips.values())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, clip in clips.items():
        data = (np.clip(clip * gain, -1, 1) * 32767).astype("<i2")
        with wave.open(str(OUT_DIR / f"{name}.wav"), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(data.tobytes())
        print(f"wrote {name}.wav  peak {np.abs(clip * gain).max():.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
