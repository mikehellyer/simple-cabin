import json

from simple_cabin.core.settings import Settings, SettingsStore


def test_defaults_when_no_file(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.settings == Settings()


def test_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.update(location_mode="manual", location_name="Keswick", latitude=54.6, longitude=-3.13, fire_volume=40)
    again = SettingsStore(path)
    assert again.settings.location_name == "Keswick" and again.settings.fire_volume == 40


def test_bad_values_are_ignored_or_clamped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "temperature_unit": "K", "clock_voice": "cuckoo", "master_volume": 400, "latitude": 12, "muted": "yes",
        "location_mode": "manual", "location_name": "",
    }))
    s = SettingsStore(path).settings
    assert s.temperature_unit == "C"
    assert s.clock_voice == "classic"
    assert s.master_volume == 100
    assert s.latitude == 12.0
    assert s.muted is False
    assert s.location_mode == "auto"  # manual with no place falls back
