"""Regression tests for interval reconstruction from TrainerRoad lap exports.

These intentionally capture known failures in the current classifier. Keep the
pull request in draft until the implementation passes these tests.
"""
import pytest

from app.analytics.activity_classifier import _structure_from_laps


def lap(seconds, watts):
    return {
        "elapsed_time": seconds,
        "average_watts": watts,
        "max_watts": watts,
        "average_heartrate": 140,
        "max_heartrate": 150,
        "average_cadence": 85,
    }


def test_stepped_warmup_is_not_a_fourth_threshold_rep():
    # 21 Nov 2026: stepped warmup then 3 x 12 min @ 199 W.
    laps = [
        lap(120, 104), lap(119, 139), lap(119, 159), lap(59, 179),
        lap(428, 73), lap(719, 199), lap(299, 105),
        lap(719, 199), lap(303, 102), lap(719, 199),
        lap(306, 87), lap(15, 30),
    ]
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 3
    assert result["summary"]["avg_interval_duration_s"] == pytest.approx(719, abs=2)


def test_vo2_split_laps_are_nine_efforts_not_eighteen():
    # 26 Aug 2026: each main VO2 effort is two adjacent high-power laps.
    laps = [lap(60, 106), lap(59, 137), lap(59, 169),
            lap(59, 231), lap(59, 108), lap(29, 248),
            lap(29, 110), lap(29, 268), lap(347, 84)]
    for i in range(9):
        laps += [lap(44, 250), lap(74, 245)]
        if i != 8:
            laps.append(lap(179 if i % 3 else 391, 85))
    laps.append(lap(121, 71))
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 9
    assert result["summary"]["avg_interval_duration_s"] == pytest.approx(118, abs=5)


def test_four_sustained_threshold_reps():
    # 7 Nov 2026 Coomnadiha.
    laps = [lap(39, 94), lap(264, 126), lap(179, 158),
            lap(288, 62)]
    for i in range(4):
        laps.append(lap(539, 200))
        laps.append(lap([267, 209, 268, 314][i], 84))
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 4
