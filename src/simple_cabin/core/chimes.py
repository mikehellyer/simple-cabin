"""When the grandfather clock chimes, and what it plays (Westminster Quarters)."""
from __future__ import annotations

from typing import Optional

# The five "changes" of the Westminster chime, as notes in E major.
CHANGES = {
    1: ["G#4", "F#4", "E4", "B3"],
    2: ["E4", "G#4", "F#4", "B3"],
    3: ["E4", "F#4", "G#4", "E4"],
    4: ["G#4", "E4", "F#4", "B3"],
    5: ["B3", "F#4", "G#4", "E4"],
}

# Which changes ring at each quarter. The hour also strikes the hour count.
QUARTER_CHANGES = {
    15: [1],
    30: [2, 3],
    45: [4, 5, 1],
    0: [2, 3, 4, 5],
}


def chime_for(hour: int, minute: int, quarters: bool) -> Optional[str]:
    """The chime due at hour:minute (24h), or None. "hour_7" strikes seven;
    "quarter_15"/"quarter_30"/"quarter_45" are the quarter-hour chimes."""
    if minute == 0:
        return f"hour_{strike_count(hour)}"
    if quarters and minute in (15, 30, 45):
        return f"quarter_{minute}"
    return None


def strike_count(hour: int) -> int:
    return hour % 12 or 12


def melody(key: str) -> list[list[str]]:
    """The phrases (lists of notes) a chime plays before any hour strikes."""
    minute = 0 if key.startswith("hour_") else int(key.split("_")[1])
    return [CHANGES[c] for c in QUARTER_CHANGES[minute]]


def strikes(key: str) -> int:
    return int(key.split("_")[1]) if key.startswith("hour_") else 0


def all_keys() -> list[str]:
    return [f"hour_{n}" for n in range(1, 13)] + ["quarter_15", "quarter_30", "quarter_45"]
