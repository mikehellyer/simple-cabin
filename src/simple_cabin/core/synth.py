"""Every sound in the cabin, synthesised with numpy and saved as WAV files.

Nothing is shipped as a recording: the clock's tick and tock, the fire's
crackle and the Westminster chimes are all made here the first time
they're needed, then kept in the cache folder. Bump SYNTH_VERSION after
changing how anything sounds, so old files get remade.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from simple_cabin.core import chimes

RATE = 44100
SYNTH_VERSION = 1

NOTES = {"B3": 246.94, "E4": 329.63, "F#4": 369.99, "G#4": 415.30, "E3": 164.81}

BEAT_SECONDS = 0.72  # one note of the chime tune
STRIKE_GAP_SECONDS = 2.1  # between the hour strikes


def _time(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * RATE)) / RATE


def _filtered(signal: np.ndarray, gain) -> np.ndarray:
    """Filter in the frequency domain: gain(freqs_hz) -> weights. This is
    circular, which suits the fire loop — it wraps round seamlessly."""
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / RATE)
    return np.fft.irfft(spectrum * gain(freqs), len(signal))


def _normalise(signal: np.ndarray, peak: float = 0.9) -> np.ndarray:
    top = float(np.max(np.abs(signal))) or 1.0
    return signal * (peak / top)


# --- the clock


def tick(tock: bool = False) -> np.ndarray:
    """One beat of the escapement. The tock is a touch lower, so the pair
    has the familiar lopsided "tick… tock…" of a long-case clock."""
    rng = np.random.default_rng(11 if tock else 7)
    pitch = 0.86 if tock else 1.0
    t = _time(0.3)
    out = np.zeros_like(t)

    def strike(start: float, level: float) -> None:
        offset = int(start * RATE)
        tt = t[: len(t) - offset]
        click = rng.standard_normal(len(tt)) * np.exp(-tt / 0.0012)
        click = _filtered(click, lambda f: (f > 900) * 1.0)
        ring = sum(
            amp * np.sin(2 * np.pi * freq * pitch * tt) * np.exp(-tt / decay)
            for freq, decay, amp in ((1280, 0.011, 0.5), (2470, 0.007, 0.32), (3900, 0.004, 0.18))
        )
        body = 0.55 * np.sin(2 * np.pi * 205 * pitch * tt) * np.exp(-tt / 0.05)
        body += 0.3 * np.sin(2 * np.pi * 96 * pitch * tt) * np.exp(-tt / 0.08)
        out[offset:] += level * (0.6 * click + ring + body)

    strike(0.0, 1.0)
    strike(0.017, 0.35)  # the escape wheel's tooth landing
    fade = np.ones_like(t)
    fade[-2000:] = np.linspace(1, 0, 2000)
    return _normalise(out * fade, 0.8)


# --- the fire


def fire_loop(seconds: float = 24.0, seed: int = 3) -> np.ndarray:
    """A seamless loop of a log fire: a low roar that breathes, a soft
    hiss, and a scatter of crackles and the odd bigger pop."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE

    def lfo(*cycles: int) -> np.ndarray:
        # Whole numbers of cycles across the loop, so it joins up exactly.
        waves = [np.sin(2 * np.pi * c * t / seconds + rng.uniform(0, 6.3)) for c in cycles]
        return sum(waves) / len(waves)

    roar = _filtered(rng.standard_normal(n), lambda f: (f > 30) / (1 + (f / 110) ** 2))
    roar = _normalise(roar, 1.0) * (0.65 + 0.35 * lfo(5, 9, 14, 23))
    hiss = _filtered(rng.standard_normal(n), lambda f: np.exp(-(((f - 3800) / 1800) ** 2)))
    hiss = _normalise(hiss, 1.0) * (0.5 + 0.5 * lfo(7, 19))
    flutter = _filtered(rng.standard_normal(n), lambda f: np.exp(-(((f - 600) / 250) ** 2)))
    flutter = _normalise(flutter, 1.0) * np.clip(lfo(11, 17, 31), 0, None)

    crackles = np.zeros(n)
    event_times = []
    for start in rng.uniform(0, seconds, int(seconds * 5)):
        event_times.append(start)
        if rng.random() < 0.35:  # crackles come in little bursts
            event_times.extend(start + rng.uniform(0.005, 0.12, rng.integers(1, 5)))
    for when in event_times:
        length = int(rng.uniform(0.002, 0.012) * RATE)
        tt = np.arange(length) / RATE
        burst = rng.standard_normal(length) * np.exp(-tt / rng.uniform(0.0003, 0.0025))
        burst = np.diff(burst, prepend=0.0)  # brighter, snappier
        level = min(1.0, rng.lognormal(-1.6, 0.8))
        idx = (int(when * RATE) + np.arange(length)) % n
        np.add.at(crackles, idx, level * burst)

    pops = np.zeros(n)
    for when in rng.uniform(0, seconds, int(seconds * 0.5)):
        length = int(0.06 * RATE)
        tt = np.arange(length) / RATE
        freq = rng.uniform(250, 900)
        pop = np.sin(2 * np.pi * freq * tt) * np.exp(-tt / rng.uniform(0.004, 0.012))
        pop += 0.6 * rng.standard_normal(length) * np.exp(-tt / 0.002)
        idx = (int(when * RATE) + np.arange(length)) % n
        np.add.at(pops, idx, rng.uniform(0.5, 1.0) * pop)

    mix = 0.55 * roar + 0.05 * hiss + 0.08 * flutter + 0.9 * _normalise(crackles, 1.0) + 0.5 * _normalise(pops, 1.0)
    return _normalise(mix, 0.85)


# --- the weather


def rain_loop(seconds: float = 16.0, seed: int = 5) -> np.ndarray:
    """A seamless loop of steady rain on the roof and window."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    wash = _filtered(rng.standard_normal(n), lambda f: (f > 200) * np.exp(-(((f - 2500) / 3000) ** 2)))
    swell = 0.8 + 0.2 * np.sin(2 * np.pi * 3 * t / seconds)
    drops = np.zeros(n)
    for when in rng.uniform(0, seconds, int(seconds * 40)):
        length = int(0.01 * RATE)
        tt = np.arange(length) / RATE
        freq = rng.uniform(1500, 5000)
        drop = np.sin(2 * np.pi * freq * tt) * np.exp(-tt / 0.0015)
        idx = (int(when * RATE) + np.arange(length)) % n
        np.add.at(drops, idx, rng.uniform(0.1, 1.0) * drop)
    return _normalise(_normalise(wash, 1.0) * swell * 0.7 + _normalise(drops, 1.0) * 0.35, 0.8)


def thunder(seed: int = 9) -> np.ndarray:
    """A distant roll of thunder."""
    rng = np.random.default_rng(seed)
    seconds = 7.0
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    rumble = _normalise(_filtered(rng.standard_normal(n), lambda f: (f > 20) / (1 + (f / 90) ** 2)), 1.0)
    crack = _normalise(_filtered(rng.standard_normal(n), lambda f: (f > 300) / (1 + (f / 1500) ** 2)), 1.0)
    # Rolling: a few swells, decaying overall
    rolls = sum(np.exp(-(((t - c) / w) ** 2)) for c, w in ((0.4, 0.3), (1.3, 0.5), (2.4, 0.7), (3.8, 1.0)))
    envelope = np.minimum(1.0, t / 0.08) * np.exp(-t / 2.6) * (0.5 + rolls)
    out = rumble * envelope + 0.25 * crack * np.exp(-t / 0.25) * np.minimum(1.0, t / 0.02)
    return _normalise(out, 0.85)


# --- the chimes


def _rod(freq: float, seconds: float, hour_bell: bool = False) -> np.ndarray:
    """One struck chime rod (or, for the hour, a deeper bell)."""
    t = _time(seconds)
    if hour_bell:
        partials = ((1.0, 1.0, 5.5), (2.0, 0.55, 3.6), (2.41, 0.35, 2.6), (3.0, 0.22, 1.9), (4.2, 0.14, 1.2), (5.4, 0.07, 0.8))
    else:
        partials = ((1.0, 1.0, 3.2), (2.0, 0.22, 1.8), (2.76, 0.42, 1.3), (4.07, 0.18, 0.7), (5.40, 0.12, 0.4))
    out = np.zeros_like(t)
    for ratio, amp, decay in partials:
        f = freq * ratio
        # Each partial as a slightly mistuned pair, for a slow shimmer.
        out += amp * 0.5 * (np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.0017 * t)) * np.exp(-t / decay)
    attack = np.minimum(1.0, t / 0.002)
    knock = np.random.default_rng(int(freq)).standard_normal(len(t)) * np.exp(-t / 0.003) * 0.15
    return (out + knock) * attack


def chime(key: str) -> np.ndarray:
    phrases = chimes.melody(key)
    count = chimes.strikes(key)
    starts: list[tuple[float, str, bool]] = []
    beat = 0
    for phrase in phrases:
        for i, note in enumerate(phrase):
            starts.append((beat * BEAT_SECONDS, note, False))
            # The last note of a change is held, which is the pause between changes.
            beat += 2 if i == len(phrase) - 1 else 1
    melody_end = beat * BEAT_SECONDS
    for s in range(count):
        starts.append((melody_end + 1.2 + s * STRIKE_GAP_SECONDS, "E3", True))

    tail = 6.0
    total = max(when for when, _, _ in starts) + tail
    out = np.zeros(int(total * RATE))
    for when, note, hour_bell in starts:
        sound = _rod(NOTES[note], tail, hour_bell) * (1.0 if hour_bell else 0.8)
        i = int(when * RATE)
        out[i : i + len(sound)] += sound[: len(out) - i]
    return _normalise(out, 0.85)


# --- files


def write_wav(path: Path, samples: np.ndarray) -> None:
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    tmp.replace(path)


def render(name: str) -> np.ndarray:
    if name == "tick":
        return tick(False)
    if name == "tock":
        return tick(True)
    if name == "fire":
        return fire_loop()
    if name == "rain":
        return rain_loop()
    if name == "thunder":
        return thunder()
    if name in chimes.all_keys():
        return chime(name)
    raise KeyError(name)


def ensure_sound(name: str, directory: Path) -> Path:
    """The WAV file for a sound, making it first if it isn't cached yet."""
    folder = directory / f"v{SYNTH_VERSION}"
    path = folder / f"{name}.wav"
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        write_wav(path, render(name))
    return path
