"""Persisted user preferences."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

from platformdirs import user_config_dir


@dataclass
class Settings:
    # Where the weather is for: "auto" (from this machine's IP address) or
    # "manual" (a place picked in Settings).
    location_mode: str = "auto"
    location_name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0

    temperature_unit: str = "C"  # "C" or "F"
    wind_unit: str = "mph"  # "mph" or "kmh"
    clock_24h: bool = True  # the weather screen's big clock

    master_volume: int = 80  # all 0..100
    tick_volume: int = 70
    fire_volume: int = 22
    chime_volume: int = 75
    muted: bool = False
    quarter_chimes: bool = False
    clock_voice: str = "recorded"  # or one of synth.VOICES

    # Drift outside now and then, but spend most of the time indoors.
    auto_switch_views: bool = True
    # Stop the screensaver, screen blanking and lock while the cabin is open.
    keep_awake: bool = True
    # Halloween, Christmas, Easter and New Year decorations, in season.
    decorations: bool = True
    # "auto" picks "light" on a Raspberry Pi: drawn at lower resolution and
    # frame rate, which a Pi can keep up with.
    graphics: str = "auto"
    inside_minutes: int = 5
    outside_seconds: int = 40


_CHOICES = {
    "location_mode": ("auto", "manual"),
    "temperature_unit": ("C", "F"),
    "wind_unit": ("mph", "kmh"),
    "clock_voice": ("recorded", "classic", "bold", "deep"),
    "graphics": ("auto", "full", "light"),
}
_RANGES = {
    "master_volume": (0, 100),
    "tick_volume": (0, 100),
    "fire_volume": (0, 100),
    "chime_volume": (0, 100),
    "inside_minutes": (1, 60),
    "outside_seconds": (10, 600),
}


class SettingsStore:
    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or Path(user_config_dir("Simple-Cabin")) / "settings.json"
        self.settings = Settings()
        self.load()

    def update(self, **changes) -> None:
        for name, value in changes.items():
            if not hasattr(self.settings, name):
                raise AttributeError(name)
            setattr(self.settings, name, value)
        self.save()

    def load(self) -> None:
        try:
            data = json.loads(self._config_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        defaults = Settings()
        for f in fields(Settings):
            if f.name not in data:
                continue
            value, default = data[f.name], getattr(defaults, f.name)
            if isinstance(default, float) and isinstance(value, int) and not isinstance(value, bool):
                value = float(value)
            if type(value) is not type(default):
                continue
            if f.name in _CHOICES and value not in _CHOICES[f.name]:
                continue
            if f.name in _RANGES:
                low, high = _RANGES[f.name]
                value = max(low, min(high, value))
            setattr(self.settings, f.name, value)
        if self.settings.location_mode == "manual" and not self.settings.location_name:
            self.settings.location_mode = "auto"

    def save(self) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(json.dumps(asdict(self.settings), indent=2))
        except OSError:
            pass
