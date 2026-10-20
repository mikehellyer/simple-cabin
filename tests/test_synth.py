import wave
from pathlib import Path

import numpy as np

from simple_cabin.core import synth


def test_tick_and_tock_are_short_and_differ():
    tick, tock = synth.tick(False), synth.tick(True)
    assert len(tick) == len(tock) < synth.RATE
    assert not np.allclose(tick, tock)
    assert np.max(np.abs(tick)) <= 0.98


def test_each_clock_voice_sounds_different_and_solid():
    ticks = {voice: synth.tick(False, voice) for voice in synth.VOICES}
    names = list(ticks)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not np.allclose(ticks[a], ticks[b])
    for voice, sound in ticks.items():
        # plenty of energy in the first 150 ms (the old, thin tick had an RMS of ~0.09)
        assert np.sqrt(np.mean(sound[: int(0.15 * synth.RATE)] ** 2)) > 0.2, voice
        assert synth.VOICES[voice]["label"]


def test_render_names_for_voices():
    assert np.allclose(synth.render("tock_deep"), synth.tick(True, "deep"))
    assert np.allclose(synth.render("tick"), synth.tick(False, synth.DEFAULT_VOICE))


def test_fire_is_a_packaged_seamless_stereo_loop():
    path = synth.ensure_sound("fire", Path("/nonexistent-cache"))  # never synthesised or cached
    with wave.open(str(path)) as w:
        assert w.getframerate() == synth.RATE and w.getnchannels() == 2
        assert w.getnframes() > 20 * synth.RATE  # long enough not to sound repetitive
        y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2) / 32767
    # the jump across the loop point is no bigger than an ordinary step
    assert np.abs(y[0] - y[-1]).max() <= np.percentile(np.abs(np.diff(y, axis=0)), 99)


def test_hour_chime_length_grows_with_the_strikes():
    one, twelve = synth.chime("hour_1"), synth.chime("hour_12")
    extra_seconds = (len(twelve) - len(one)) / synth.RATE
    assert abs(extra_seconds - 11 * synth.STRIKE_GAP_SECONDS) < 0.01


def test_ensure_sound_writes_a_cached_wav(tmp_path):
    path = synth.ensure_sound("tick", tmp_path)
    assert path.exists() and path.parent.name == f"v{synth.SYNTH_VERSION}"
    with wave.open(str(path)) as w:
        assert w.getframerate() == synth.RATE and w.getnchannels() == 1
    (tmp_path / "v1").mkdir()
    synth.remove_stale(tmp_path)
    assert not (tmp_path / "v1").exists() and path.exists()
    mtime = path.stat().st_mtime_ns
    assert synth.ensure_sound("tick", tmp_path).stat().st_mtime_ns == mtime  # not remade


def test_recorded_voice_is_four_packaged_beats():
    beats = synth.beat_names(synth.RECORDED)
    assert beats == synth.RECORDED_BEATS and len(beats) == 4
    for name in beats:
        path = synth.ensure_sound(name, Path("/nonexistent-cache"))  # never synthesised or cached
        assert path.is_file()
        with wave.open(str(path)) as w:
            assert w.getframerate() == synth.RATE and w.getnchannels() == 2
            assert w.getnframes() < synth.RATE  # each beat finishes well inside its second
    assert synth.beat_names("bold") == ["tick_bold", "tock_bold"]
    assert synth.DEFAULT_CLOCK_VOICE in synth.VOICE_LABELS
