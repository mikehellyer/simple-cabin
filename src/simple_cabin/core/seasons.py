"""Which seasonal decorations are up, by the date."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

HALLOWEEN, CHRISTMAS, EASTER, NEW_YEAR = "halloween", "christmas", "easter", "new_year"
ALL = (HALLOWEEN, CHRISTMAS, EASTER, NEW_YEAR)
NAMES = {HALLOWEEN: "Halloween", CHRISTMAS: "Christmas", EASTER: "Easter", NEW_YEAR: "New Year"}


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter: the anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def decoration_for(day: date) -> Optional[str]:
    """The decorations up on this day, if any."""
    if (day.month, day.day) in ((12, 31), (1, 1)):
        return NEW_YEAR
    if day.month == 12 or (day.month == 1 and day.day <= 5):  # until Twelfth Night
        return CHRISTMAS
    if day.month == 10 and day.day >= 17:
        return HALLOWEEN
    easter = easter_sunday(day.year)
    if easter - timedelta(days=7) <= day <= easter + timedelta(days=1):  # Palm Sunday to Easter Monday
        return EASTER
    return None


def fireworks_now(now: datetime) -> bool:
    """New Year's Eve, from dark until one in the morning."""
    return (now.month == 12 and now.day == 31 and now.hour >= 17) or (now.month == 1 and now.day == 1 and now.hour < 1)
