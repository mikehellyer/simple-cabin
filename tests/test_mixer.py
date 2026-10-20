import wave

import numpy as np

from simple_cabin.core.mixer import RATE, Mixer, load_wav, seconds_in


def stream(mixer, seconds, start=1000.0, block=441):
    """Render a run of blocks, as the audio engine would."""
    chunks, t = [], start
    for _ in range(int(seconds * RATE / block)):
        chunks.append(np.frombuffer(mixer.render(block, t), "<i2").reshape(-1, 2))
        t += block / RATE
    return np.concatenate(chunks)


def click(n=100):
    s = np.zeros((n, 2), np.float32)
    s[0] = 0.5
    return s


def test_a_sound_starts_on_the_exact_frame_asked_for():
    m = Mixer(lambda name: 1.0)
    m.add("tick", click())
    m.play("tick", at=1000.25)  # a quarter of a second into the stream
    out = stream(m, 0.5)
    first = np.flatnonzero(out[:, 0])[0]
    assert abs(first - int(0.25 * RATE)) <= 1


def test_loops_keep_going_and_one_shots_end():
    m = Mixer(lambda name: 1.0)
    m.add("fire", np.full((300, 2), 0.1, np.float32))
    m.add("tick", np.full((50, 2), 0.2, np.float32))
    m.play("fire", loop=True)
    m.play("tick")
    out = stream(m, 0.1)
    assert m.is_playing("fire") and not m.is_playing("tick")
    assert np.all(out[-100:, 0] > 0)  # the fire is still going


def test_gain_mute_and_stop():
    level = {"fire": 0.5}
    m = Mixer(lambda name: level[name])
    m.add("fire", np.full((1000, 2), 0.4, np.float32))
    m.play("fire", loop=True)
    out = np.frombuffer(m.render(100, 0), "<i2")
    assert abs(out[0] / 32767 - 0.2) < 0.01
    m.muted = True
    assert not np.any(np.frombuffer(m.render(100, 0), "<i2"))
    m.muted = False
    m.stop("fire")
    assert not np.any(np.frombuffer(m.render(100, 0), "<i2"))


def test_sounds_that_arent_loaded_yet_wait():
    m = Mixer(lambda name: 1.0)
    m.play("chime")
    assert not np.any(np.frombuffer(m.render(100, 0), "<i2"))
    m.add("chime", click())
    assert np.any(np.frombuffer(m.render(100, 0), "<i2"))


def test_load_wav_makes_mono_stereo(tmp_path):
    path = tmp_path / "mono.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.array([0, 16384, -16384], "<i2").tobytes())
    data = load_wav(path)
    assert data.shape == (3, 2)
    assert abs(data[1, 0] - 0.5) < 0.001 and data[1, 0] == data[1, 1]


def test_seconds_in_a_window():
    assert seconds_in(999.9, 1001.0) == [1000]
    assert seconds_in(1000.0, 1000.5) == [1000]
    assert seconds_in(1000.1, 1000.9) == []
