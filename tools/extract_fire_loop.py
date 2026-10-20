"""One-off tool: turn a fire recording into the seamless loop the app plays.

Takes nearly the whole recording and blends its last few seconds into its
start with an equal-power crossfade, so the loop's join can't be heard.
Keeps the stereo and the recording's own level (peaks just under full
scale). Prints FIRE_GAIN, the playback gain that makes it as loud as the
old synthesised fire, for synth.py.

Needs the dev-only decoder:  venv/bin/pip install miniaudio
Usage: venv/bin/python tools/extract_fire_loop.py ~/Downloads/Fire.mp3
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import miniaudio
import numpy as np

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "src" / "simple_cabin" / "sounds" / "fire_recorded.wav"
TRIM = 0.25  # seconds dropped from each end (decoder start-up, any edit clicks)
CROSSFADE = 3.0
PEAK = 0.95
SYNTH_FIRE_RMS = 0.0733  # the synthesised fire this replaces (synth v2)


def make_loop(x: np.ndarray) -> np.ndarray:
    x = x[int(TRIM * RATE) : len(x) - int(TRIM * RATE)].astype(np.float64)
    c = int(CROSSFADE * RATE)
    # The loop is x[c:], whose last c samples fade into x[:c] — so the end
    # of the loop runs straight on into where the loop starts.
    loop = x[c:].copy()
    t = np.linspace(0, np.pi / 2, c)[:, None]
    loop[-c:] = loop[-c:] * np.cos(t) + x[:c] * np.sin(t)  # equal power: the fire is noise-like
    return loop


def main(path: str) -> None:
    decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=2, sample_rate=RATE)
    x = np.array(decoded.samples, dtype=np.float32).reshape(-1, 2)
    loop = make_loop(x)
    loop *= PEAK / np.abs(loop).max()
    data = (np.clip(loop, -1, 1) * 32767).astype("<i2")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    rms = float(np.sqrt((loop.mean(1) ** 2).mean()))
    print(f"wrote {OUT.name}: {len(loop) / RATE:.1f} s, rms {rms:.4f}")
    print(f"FIRE_GAIN = {SYNTH_FIRE_RMS / rms:.2f}")


if __name__ == "__main__":
    main(sys.argv[1])
