from simple_cabin.core import chimes


def test_hours_chime_with_the_right_number_of_strikes():
    assert chimes.chime_for(0, 0, quarters=False) == "hour_12"
    assert chimes.chime_for(13, 0, quarters=False) == "hour_1"
    assert chimes.chime_for(19, 0, quarters=False) == "hour_7"
    assert chimes.strikes("hour_7") == 7


def test_quarters_only_when_enabled():
    assert chimes.chime_for(10, 15, quarters=False) is None
    assert chimes.chime_for(10, 15, quarters=True) == "quarter_15"
    assert chimes.chime_for(10, 45, quarters=True) == "quarter_45"
    assert chimes.chime_for(10, 20, quarters=True) is None
    assert chimes.strikes("quarter_30") == 0


def test_westminster_sequence():
    assert len(chimes.melody("quarter_15")) == 1
    assert len(chimes.melody("quarter_30")) == 2
    assert len(chimes.melody("quarter_45")) == 3
    assert chimes.melody("hour_3") == [chimes.CHANGES[c] for c in (2, 3, 4, 5)]
    assert len(chimes.all_keys()) == 15
