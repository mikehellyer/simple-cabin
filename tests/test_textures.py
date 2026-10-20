import pytest

pytest.importorskip("PySide6.QtGui", exc_type=ImportError)  # CI Linux has no libEGL

from simple_cabin.gui import textures as tx


@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tx, "_memory", {})
    tx.set_cache_dir(tmp_path)
    yield tmp_path
    monkeypatch.setattr(tx, "_cache_dir", None)


def test_textures_are_saved_and_loaded_back(fresh_cache, monkeypatch):
    first = tx.jute(64, 48, 3)
    files = list((fresh_cache / f"v{tx.TEXTURE_VERSION}").glob("jute-*.png"))
    assert len(files) == 1
    # a new run (empty memory) loads the file instead of generating again
    monkeypatch.setattr(tx, "_memory", {})
    monkeypatch.setattr(tx, "fbm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("regenerated")))
    again = tx.jute(64, 48, 3)
    assert again.size() == first.size()
    assert again.pixel(10, 10) == first.pixel(10, 10)


def test_old_texture_versions_are_removed(tmp_path):
    (tmp_path / "v0").mkdir()
    tx.set_cache_dir(tmp_path)
    assert not (tmp_path / "v0").exists()
    assert (tmp_path / f"v{tx.TEXTURE_VERSION}").is_dir()
    tx._cache_dir = None
