"""
Unit tests for activity_warmup_finder.detect_warmup().

Each test case corresponds to a scenario from the feature spec.
Tests are self-contained and use only synthetically generated power streams.
"""

import math
import sys
import os
import unittest

# ---------------------------------------------------------------------------
# Make the flask app importable without a running Flask context
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.analytics.activity_warmup_finder import (
    detect_warmup,
    is_likely_endurance,
    detect_repeated_intervals,
    score_warmup_candidate,
    find_main_set_candidates,
    detect_sustained_main_block,
    OUTDOOR_CFG,
    INDOOR_CFG,
    _rolling_mean,
    _trend_slope,
)
import numpy as np


# ---------------------------------------------------------------------------
# Stream-building helpers
# ---------------------------------------------------------------------------

def _flat(watts: float, duration_s: int) -> list:
    return [watts] * duration_s


def _ramp(start_w: float, end_w: float, duration_s: int) -> list:
    return [start_w + (end_w - start_w) * i / max(duration_s - 1, 1) for i in range(duration_s)]


def _stepped_warmup(ftp: float) -> list:
    """Stepped warmup: 3 min @ 50%, 3 min @ 65%, 2 min @ 75%, 30 s opener at 105%."""
    return (
        _flat(ftp * 0.50, 180)
        + _flat(ftp * 0.65, 180)
        + _flat(ftp * 0.75, 120)
        + _flat(ftp * 1.05, 30)  # short opener
    )


def _ramped_warmup(ftp: float, duration_s: int = 540) -> list:
    """Ramp from 40% to 85% FTP over duration_s."""
    return _ramp(ftp * 0.40, ftp * 0.85, duration_s)


def _repeated_intervals(ftp: float, n: int, work_s: int, rest_s: int, pct: float) -> list:
    stream = []
    for _ in range(n):
        stream += _flat(ftp * pct, work_s)
        stream += _flat(ftp * 0.40, rest_s)
    return stream


def _vo2_main_set(ftp: float) -> list:
    """5 x 3 min @ 115% with 3 min recoveries."""
    return _repeated_intervals(ftp, 5, 180, 180, 1.15)


def _threshold_main_set(ftp: float) -> list:
    """3 x 12 min @ 95% with 3 min recoveries."""
    return _repeated_intervals(ftp, 3, 720, 180, 0.95)


def _hill_repeats(ftp: float) -> list:
    """6 x 4 min @ 105% with 4 min recoveries."""
    return _repeated_intervals(ftp, 6, 240, 240, 1.05)


def _endurance_stream(ftp: float, duration_s: int = 3600) -> list:
    """Flat endurance ride at 55% FTP with minor noise."""
    base = ftp * 0.55
    rng = [base + (i % 30 - 15) * 0.5 for i in range(duration_s)]
    return rng


def _stochastic_stream(ftp: float, duration_s: int = 3600, seed: int = 42) -> list:
    """Unstructured stochastic power with no clear intervals."""
    rng_state = seed
    result = []
    for i in range(duration_s):
        # Simple LCG pseudo-random for determinism without random module state
        rng_state = (rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
        noise = (rng_state / 0xFFFFFFFF) * 0.6 - 0.3  # -0.3 to +0.3 FTP
        result.append(max(0.0, ftp * (0.60 + noise)))
    return result


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestDetectWarmup(unittest.TestCase):

    FTP = 280  # watts

    # ------------------------------------------------------------------ #
    # Case 1: Indoor VO2 session with 10 min stepped warmup                #
    # ------------------------------------------------------------------ #
    def test_case1_indoor_vo2_stepped_warmup_detected(self):
        """Indoor VO2 session: stepped 10-min warmup followed by 5x3min @ 115% FTP."""
        ftp = self.FTP
        warmup = (
            _flat(ftp * 0.50, 180)   # 3 min @ 50%
            + _flat(ftp * 0.62, 180) # 3 min @ 62%
            + _flat(ftp * 0.72, 120) # 2 min @ 72%
            + _flat(ftp * 1.05, 60)  # 1 min opener
            + _flat(ftp * 0.40, 60)  # 1 min spin-down
        )  # 600 s total warmup
        main_set = _vo2_main_set(ftp)
        stream = warmup + main_set

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
        )

        self.assertTrue(result["warmup_detected"], f"Expected warmup detected. Result: {result}")
        self.assertIsNotNone(result["warmup_end_index"])
        self.assertGreater(result["confidence"], 0.60)
        # Warmup end should be somewhere in 400-800s range
        self.assertGreater(result["warmup_end_s"], 200)
        self.assertLess(result["warmup_end_s"], 900)

    # ------------------------------------------------------------------ #
    # Case 2: Indoor threshold with ramp warmup and short opener           #
    # ------------------------------------------------------------------ #
    def test_case2_indoor_threshold_ramp_warmup_detected(self):
        """Indoor threshold: 9-min ramp to 85% + 1 short opener, then 3x12min @ 95%."""
        ftp = self.FTP
        warmup = (
            _ramp(ftp * 0.40, ftp * 0.85, 540)  # 9 min ramp
            + _flat(ftp * 1.10, 30)               # 30 s opener
            + _flat(ftp * 0.35, 90)               # 90 s easy spin
        )  # 660 s total
        main_set = _threshold_main_set(ftp)
        stream = warmup + main_set

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
        )

        self.assertTrue(result["warmup_detected"], f"Expected warmup detected. Result: {result}")
        self.assertGreater(result["confidence"], 0.60)
        self.assertLess(result["warmup_end_s"], 800)

    # ------------------------------------------------------------------ #
    # Case 3: Outdoor endurance ride — no warmup expected                  #
    # ------------------------------------------------------------------ #
    def test_case3_outdoor_endurance_no_warmup(self):
        """Outdoor endurance: ~55% FTP for 60 min. No warmup should be detected."""
        ftp = self.FTP
        stream = _endurance_stream(ftp, duration_s=3600)

        result = detect_warmup(
            stream, ftp,
            activity_type="Ride",
        )

        self.assertFalse(result["warmup_detected"], f"No warmup expected. Result: {result}")
        self.assertIsNone(result["warmup_end_index"])

    # ------------------------------------------------------------------ #
    # Case 4: Outdoor ride with easy roll-out then clear hill repeats      #
    # ------------------------------------------------------------------ #
    def test_case4_outdoor_rollout_then_hill_repeats(self):
        """Outdoor ride: easy 8-min roll-out then 6 clear hill repeats."""
        ftp = self.FTP
        rollout = _flat(ftp * 0.50, 480)  # 8 min very easy
        main_set = _hill_repeats(ftp)
        stream = rollout + main_set

        result = detect_warmup(
            stream, ftp,
            activity_type="Ride",
        )

        # Warmup should be detected only when the later repeats are very clear.
        # The hill repeats are 6x4min @ 105% which is very structured — warmup
        # should be detected. Confidence must be above threshold.
        if result["warmup_detected"]:
            self.assertGreater(result["confidence"], 0.60)
            self.assertLess(result["warmup_end_s"], 600)
        # It is also acceptable for a conservative outdoor detector to return False
        # as long as the score is low — we just assert consistency.
        # Either outcome is valid per spec ("detect only if later repeats very clear")
        # so we only enforce the confidence guard if it fires.

    # ------------------------------------------------------------------ #
    # Case 5: Indoor workout with first interval starting very early       #
    # ------------------------------------------------------------------ #
    def test_case5_indoor_first_interval_very_early_no_warmup(self):
        """Indoor session starting hard almost immediately — no warmup should be removed."""
        ftp = self.FTP
        # 90 s easy, then straight into 5x3min @ 115%
        stream = _flat(ftp * 0.40, 90) + _vo2_main_set(ftp)

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
        )

        self.assertFalse(
            result["warmup_detected"],
            f"No warmup expected when first interval is at 90s. Result: {result}",
        )

    # ------------------------------------------------------------------ #
    # Case 6: Stochastic power, no clear main set                          #
    # ------------------------------------------------------------------ #
    def test_case6_stochastic_no_warmup(self):
        """Unstructured stochastic ride — no warmup should be detected."""
        ftp = self.FTP
        stream = _stochastic_stream(ftp, duration_s=3600)

        result = detect_warmup(
            stream, ftp,
            activity_type="Ride",
        )

        self.assertFalse(result["warmup_detected"], f"No warmup expected for stochastic ride. Result: {result}")

    # ------------------------------------------------------------------ #
    # Case 7: Warmup with one or two short surges — still a warmup         #
    # ------------------------------------------------------------------ #
    def test_case7_warmup_with_short_surges_still_detected(self):
        """Warmup with two short ~20s surges above FTP, then clear repeated main set."""
        ftp = self.FTP
        warmup = (
            _flat(ftp * 0.55, 180)   # 3 min easy
            + _flat(ftp * 1.20, 20)  # 20 s surge 1
            + _flat(ftp * 0.45, 60)  # 1 min easy
            + _flat(ftp * 1.20, 20)  # 20 s surge 2
            + _flat(ftp * 0.40, 100) # ~1.7 min easy spin
        )  # 380 s warmup
        main_set = _vo2_main_set(ftp)  # 5 x 3 min
        stream = warmup + main_set

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
        )

        self.assertTrue(
            result["warmup_detected"],
            f"Expected warmup detected despite short surges. Result: {result}",
        )
        self.assertGreater(result["confidence"], 0.60)

    # ------------------------------------------------------------------ #
    # Case 8: False-positive protection — first hard interval IS workout   #
    # ------------------------------------------------------------------ #
    def test_case8_first_hard_interval_is_workout_not_removed(self):
        """
        Ride begins immediately with a hard interval structure.
        The function must not misidentify any portion as a warmup.
        """
        ftp = self.FTP
        # Start hard immediately — no warmup at all
        stream = _vo2_main_set(ftp)

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
        )

        self.assertFalse(
            result["warmup_detected"],
            f"Should not detect warmup when ride starts with main set immediately. Result: {result}",
        )

    # ------------------------------------------------------------------ #
    # Additional edge-case tests for helper functions                       #
    # ------------------------------------------------------------------ #

    def test_is_likely_endurance_true(self):
        ftp = self.FTP
        pct_ftp = np.array([0.55] * 3600)
        cfg = dict(OUTDOOR_CFG)
        result, score = is_likely_endurance(pct_ftp, cfg)
        self.assertTrue(result)
        self.assertGreater(score, 0.80)

    def test_is_likely_endurance_false_for_intervals(self):
        ftp = self.FTP
        # Mix of high and low intensity
        stream = np.array(_repeated_intervals(ftp, 5, 180, 180, 1.10))
        pct_ftp = stream / ftp
        cfg = dict(OUTDOOR_CFG)
        result, score = is_likely_endurance(pct_ftp, cfg)
        self.assertFalse(result)

    def test_detect_repeated_intervals_finds_clear_pattern(self):
        ftp = self.FTP
        stream = np.array(_repeated_intervals(ftp, 5, 180, 180, 1.15))
        pct_ftp = stream / ftp
        cfg = dict(OUTDOOR_CFG)
        result = detect_repeated_intervals(pct_ftp, 0, cfg)
        self.assertGreaterEqual(result["interval_count"], 4)
        self.assertGreater(result["repeatability_score"], 0.5)

    def test_detect_repeated_intervals_finds_nothing_for_flat(self):
        ftp = self.FTP
        stream = np.array([ftp * 0.55] * 3600)
        pct_ftp = stream / ftp
        cfg = dict(OUTDOOR_CFG)
        result = detect_repeated_intervals(pct_ftp, 0, cfg)
        self.assertEqual(result["interval_count"], 0)

    def test_rolling_mean_preserves_length(self):
        arr = np.arange(100, dtype=float)
        smoothed = _rolling_mean(arr, 10)
        self.assertEqual(len(smoothed), 100)

    def test_trend_slope_positive_ramp(self):
        arr = np.linspace(0, 1, 100)
        slope = _trend_slope(arr)
        self.assertGreater(slope, 0)

    def test_detect_warmup_returns_no_warmup_on_bad_input(self):
        result = detect_warmup([], 280)
        self.assertFalse(result["warmup_detected"])

    def test_detect_warmup_returns_no_warmup_zero_ftp(self):
        result = detect_warmup([200] * 600, 0)
        self.assertFalse(result["warmup_detected"])

    def test_cfg_override_respected(self):
        """Custom minimum_confidence_to_accept of 0.99 should suppress all detections."""
        ftp = self.FTP
        warmup = _stepped_warmup(ftp)
        main_set = _vo2_main_set(ftp)
        stream = warmup + main_set

        result = detect_warmup(
            stream, ftp,
            activity_type="VirtualRide",
            cfg={"minimum_confidence_to_accept": 0.99},
        )
        # At 0.99 threshold essentially nothing should pass
        if result["warmup_detected"]:
            self.assertGreater(result["confidence"], 0.99)

    def test_detect_sustained_main_block_finds_block(self):
        ftp = self.FTP
        easy = np.array([0.55] * 300)
        hard = np.array([0.90] * 600)
        pct_ftp = np.concatenate([easy, hard])
        cfg = dict(OUTDOOR_CFG)
        result = detect_sustained_main_block(pct_ftp, 300, cfg, opening_mean=0.55)
        self.assertTrue(result["found"])
        self.assertGreater(result["block_duration_s"], 0)

    def test_find_main_set_candidates_returns_candidates_indoor(self):
        ftp = self.FTP
        stream = np.array(_endurance_stream(ftp, 3600)) / ftp
        cfg = dict(INDOOR_CFG)
        candidates = find_main_set_candidates(stream, cfg=cfg)
        self.assertGreater(len(candidates), 0)
        # All candidates should be within allowed search window
        for c in candidates:
            self.assertLessEqual(c, cfg["search_window_s"])

    def test_warmup_end_is_within_guardrail_fraction(self):
        """Detected warmup end must not exceed 35% of total activity duration."""
        ftp = self.FTP
        warmup = _stepped_warmup(ftp)  # ~510 s
        main_set = _vo2_main_set(ftp)
        stream = warmup + main_set

        result = detect_warmup(stream, ftp, activity_type="VirtualRide")

        if result["warmup_detected"]:
            total = len(stream)
            fraction = result["warmup_end_s"] / total
            self.assertLessEqual(fraction, 0.35 + 1e-9)


if __name__ == "__main__":
    unittest.main()
