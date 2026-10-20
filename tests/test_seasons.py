from datetime import date, datetime

from simple_cabin.core import seasons


def test_easter_dates():
    assert seasons.easter_sunday(2026) == date(2026, 4, 5)
    assert seasons.easter_sunday(2027) == date(2027, 3, 28)
    assert seasons.easter_sunday(2024) == date(2024, 3, 31)
    assert seasons.easter_sunday(2000) == date(2000, 4, 23)


def test_decorations_through_the_year():
    d = seasons.decoration_for
    assert d(date(2026, 10, 16)) is None
    assert d(date(2026, 10, 17)) == seasons.HALLOWEEN
    assert d(date(2026, 10, 31)) == seasons.HALLOWEEN
    assert d(date(2026, 11, 1)) is None
    assert d(date(2026, 12, 1)) == seasons.CHRISTMAS
    assert d(date(2026, 12, 30)) == seasons.CHRISTMAS
    assert d(date(2026, 12, 31)) == seasons.NEW_YEAR
    assert d(date(2027, 1, 1)) == seasons.NEW_YEAR
    assert d(date(2027, 1, 5)) == seasons.CHRISTMAS
    assert d(date(2027, 1, 6)) is None
    assert d(date(2026, 3, 28)) is None  # day before Palm Sunday 2026
    assert d(date(2026, 3, 29)) == seasons.EASTER
    assert d(date(2026, 4, 6)) == seasons.EASTER  # Easter Monday
    assert d(date(2026, 4, 7)) is None
    assert d(date(2026, 7, 1)) is None


def test_fireworks_on_new_years_eve_after_dark():
    assert not seasons.fireworks_now(datetime(2026, 12, 31, 12, 0))
    assert seasons.fireworks_now(datetime(2026, 12, 31, 23, 59))
    assert seasons.fireworks_now(datetime(2027, 1, 1, 0, 30))
    assert not seasons.fireworks_now(datetime(2027, 1, 1, 1, 0))
