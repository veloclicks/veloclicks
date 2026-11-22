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


def test_wheel_four_under_overs_are_three_work_sets():
    # 14 Nov 2026: each set has six alternating high-power stages.
    laps = [lap(180, 106), lap(179, 147), lap(179, 190), lap(206, 63)]
    for i in range(3):
        laps += [lap(119, 200), lap(59, 222),
                 lap(119, 201), lap(59, 222),
                 lap(119, 201), lap(59, 222)]
        laps.append(lap(419 if i < 2 else 300, 85))
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 3
    assert result["summary"]["avg_interval_duration_s"] == pytest.approx(534, abs=1)


def test_rogers_ignores_warmup_threshold_step():
    laps = [lap(326, 79), lap(180, 152), lap(179, 203), lap(333, 85)]
    for i in range(3):
        laps += [lap(419, 215), lap(419 if i < 2 else 339, 85)]
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 3
    assert result["summary"]["avg_interval_duration_s"] == pytest.approx(419, abs=1)


def test_mono_two_has_four_under_over_work_blocks():
    laps = [lap(240, 106), lap(239, 137), lap(179, 179), lap(520, 84)]
    for i in range(4):
        laps += [lap(119, 200), lap(59, 222), lap(119, 201), lap(59, 222)]
        laps.append(lap(299, 85))
    result = _structure_from_laps(laps)
    assert result["interval_count"] == 4
    assert result["summary"]["avg_interval_duration_s"] == pytest.approx(356, abs=1)


def test_townsend_endurance_laps_are_not_intervals():
    laps = [lap(d, p) for d, p in [
        (300, 106), (299, 109), (299, 120), (239, 129),
        (599, 130), (179, 127), (479, 122), (179, 128),
        (539, 133), (119, 135), (539, 137), (239, 128),
        (479, 126), (40, 119)]]
    result = _structure_from_laps(laps)
    assert not result["is_interval_session"]


def test_missing_optional_lap_metrics_do_not_crash_summary():
    laps = [lap(300, 90)]
    for i in range(3):
        work = lap(600, 210)
        work.pop('average_cadence')
        work.pop('max_heartrate')
        laps.append(work)
        if i < 2:
            recovery = lap(300, 80)
            recovery.pop('average_cadence')
            laps.append(recovery)
    result = _structure_from_laps(laps)
    assert result['is_interval_session']
    assert result['interval_count'] == 3
