from app.strava.coverage import missing_intervals


def test_empty_coverage():
    assert missing_intervals(0, 100, []) == [(0, 100)]


def test_overlapping_and_adjacent_coverage():
    assert missing_intervals(0, 100, [(20, 40), (30, 50), (50, 70)]) == [
        (70, 100), (0, 20)
    ]


def test_clipped_coverage():
    assert missing_intervals(10, 90, [(0, 20), (80, 100)]) == [(20, 80)]


def test_complete_coverage():
    assert missing_intervals(0, 100, [(-10, 110)]) == []
