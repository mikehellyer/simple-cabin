import wave

import numpy as np

from simple_cabin.core import synth


def test_tick_and_tock_are_short_and_differ():
    tick, tock = synth.tick(False), synth.tick(True)
    assert len(tick) == len(tock) < synth.RATE
    assert not np.allclose(tick, tock)
    assert np.max(np.abs(tick)) <= 0.81


def test_fire_loop_joins_up_seamlessly():
    fire = synth.fire_loop(seconds=4.0)
    assert len(fire) == 4 * synth.RATE
    # the jump across the loop point is no bigger than an ordinary step
    steps = np.abs(np.diff(fire))
    assert abs(fire[0] - fire[-1]) <= steps.max()


def test_hour_chime_length_grows_with_the_strikes():
    one, twelve = synth.chime("hour_1"), synth.chime("hour_12")
    extra_seconds = (len(twelve) - len(one)) / synth.RATE
    assert abs(extra_seconds - 11 * synth.STRIKE_GAP_SECONDS) < 0.01


def test_ensure_sound_writes_a_cached_wav(tmp_path):
    path = synth.ensure_sound("tick", tmp_path)
    assert path.exists() and path.parent.name == f"v{synth.SYNTH_VERSION}"
    with wave.open(str(path)) as w:
        assert w.getframerate() == synth.RATE and w.getnchannels() == 1
    mtime = path.stat().st_mtime_ns
    assert synth.ensure_sound("tick", tmp_path).stat().st_mtime_ns == mtime  # not remade
