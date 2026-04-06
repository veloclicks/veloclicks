"""
Warmup detection for cycling activities.

detect_warmup() analyses the opening segment of a power stream and decides
whether it constitutes a structured warmup that should be excluded from
main-set analysis.

Design principles
-----------------
- Scoring-based rather than brittle if/else logic.
- Conservative: "no warmup" is always the safer default.
- Activity type drives the entire algorithm via a per-tier config dict.
  There are no scattered is_indoor conditionals in helper functions.
- Three tiers, each with its own config:
    smart_trainer  VirtualRide (Zwift / TrainerRoad / RGT)
    indoor         IndoorCycling / IndoorRide
    outdoor        everything else (default)
- Endurance rides default to no warmup unless evidence is overwhelming.
- Only numpy and the standard library are used.

Public API
----------
    detect_warmup(power_stream, ftp, ...) -> dict
"""

import logging
import math
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================ #
# Per-tier configuration                                                         #
# ============================================================================ #

# Smart-trainer rides (Zwift, TrainerRoad, RGT …)
# ERG mode produces near-perfect repeatability and sharp power transitions.
# Warmup is almost always present and clearly defined.
SMART_TRAINER_CFG = {
    # Smoothing — ERG transitions are sharp; less smoothing needed
    "smooth_window_s": 5,

    # Endurance classification
    "endurance_pct_ftp_threshold":  0.60,
    "endurance_fraction_threshold": 0.85,   # trainer sessions are mostly sub-threshold
    "endurance_repeatability_min":  0.35,   # ERG gives near-perfect repeatability

    # Candidate search
    "search_window_s":               1200,  # 20 min — covers warmups with stretch breaks
    "candidate_warmup_max_duration_s": 1200,
    "candidate_step_s":              30,
    "candidate_min_duration_s":      120,

    # Interval detection — tighter tolerances; ERG intervals are very consistent
    "minimum_repeated_intervals":    3,
    "interval_duration_tolerance":   0.15,
    "interval_power_tolerance":      0.06,
    "min_interval_duration_s":       20,
    "interval_work_floor_pct_ftp":   0.70,
    "interval_recovery_ceiling_pct_ftp": 0.65,

    # Sustained block
    "sustained_block_min_duration_s":  300,
    "sustained_block_min_pct_ftp":     0.75,
    "sustained_block_intensity_uplift": 0.10,

    # Scoring
    "minimum_confidence_to_accept":  0.58,  # slightly lower — structure is unambiguous
    "activity_type_bonus":           0.10,  # bonus applied in score_warmup_candidate

    # Guardrails
    "max_warmup_fraction_of_total":  0.35,
    "min_first_interval_start_s":    240,
    "guardrail_min_interval_duration_s": 45,
}

# Indoor trainer rides without ERG (standard turbo / spin-bike)
# Warmup is likely; transitions are softer than smart-trainer ERG.
INDOOR_CFG = {
    "smooth_window_s": 7,

    "endurance_pct_ftp_threshold":  0.60,
    "endurance_fraction_threshold": 0.85,
    "endurance_repeatability_min":  0.40,

    "search_window_s":               1200,
    "candidate_warmup_max_duration_s": 1200,
    "candidate_step_s":              30,
    "candidate_min_duration_s":      120,

    "minimum_repeated_intervals":    3,
    "interval_duration_tolerance":   0.20,
    "interval_power_tolerance":      0.08,
    "min_interval_duration_s":       20,
    "interval_work_floor_pct_ftp":   0.70,
    "interval_recovery_ceiling_pct_ftp": 0.65,

    "sustained_block_min_duration_s":  300,
    "sustained_block_min_pct_ftp":     0.75,
    "sustained_block_intensity_uplift": 0.10,

    "minimum_confidence_to_accept":  0.60,
    "activity_type_bonus":           0.08,

    "max_warmup_fraction_of_total":  0.35,
    "min_first_interval_start_s":    240,
    "guardrail_min_interval_duration_s": 45,
}

# Outdoor rides — variable terrain, conservative defaults
OUTDOOR_CFG = {
    "smooth_window_s": 7,

    # Lower fraction threshold: climbs / descents / accelerations mean even a
    # genuine endurance ride will have significant time above 0.60 FTP.
    "endurance_pct_ftp_threshold":  0.60,
    "endurance_fraction_threshold": 0.50,
    # High repeatability bar: terrain fluctuations produce many low-repeatability
    # "intervals" that should not disqualify an endurance classification.
    "endurance_repeatability_min":  0.60,

    "search_window_s":               720,   # 12 min — be conservative
    "candidate_warmup_max_duration_s": 1200,
    "candidate_step_s":              30,
    "candidate_min_duration_s":      120,

    "minimum_repeated_intervals":    3,
    "interval_duration_tolerance":   0.20,
    "interval_power_tolerance":      0.08,
    "min_interval_duration_s":       20,
    "interval_work_floor_pct_ftp":   0.70,
    "interval_recovery_ceiling_pct_ftp": 0.65,

    "sustained_block_min_duration_s":  300,
    "sustained_block_min_pct_ftp":     0.75,
    "sustained_block_intensity_uplift": 0.10,

    "minimum_confidence_to_accept":  0.65,  # higher bar outdoors
    "activity_type_bonus":           0.0,   # no bonus for outdoor

    "max_warmup_fraction_of_total":  0.35,
    "min_first_interval_start_s":    240,
    "guardrail_min_interval_duration_s": 45,
}

_CONFIGS = {
    "smart_trainer": SMART_TRAINER_CFG,
    "indoor":        INDOOR_CFG,
    "outdoor":       OUTDOOR_CFG,
}


def _classify_activity_type(activity_type: Optional[str]) -> str:
    """
    Map a Strava activity type string to one of 'smart_trainer', 'indoor', 'outdoor'.

    VirtualRide covers Zwift, TrainerRoad, RGT, Sufferfest etc.
    IndoorCycling / IndoorRide covers turbo trainers without a virtual platform.
    Everything else defaults to 'outdoor'.
    """
    if not activity_type:
        return "outdoor"
    t = activity_type.lower()
    if t == "virtualride":
        return "smart_trainer"
    if t in ("indoorcycling", "indoorride"):
        return "indoor"
    return "outdoor"


def _select_cfg(tier: str, user_overrides: Optional[dict]) -> dict:
    """Return the base config for tier merged with any user overrides."""
    cfg = dict(_CONFIGS[tier])
    if user_overrides:
        cfg.update(user_overrides)
    return cfg


# ============================================================================ #
# Rolling mean helper (no pandas / scipy)                                        #
# ============================================================================ #

def _rolling_mean(arr: np.ndarray, window: int) -> np.ndarray:
    """Simple symmetric rolling mean using convolution."""
    if window <= 1 or len(arr) == 0:
        return arr.copy()
    w = min(window, len(arr))
    kernel = np.ones(w) / w
    padded = np.pad(arr, (w // 2, w - w // 2 - 1), mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(arr)]


# ============================================================================ #
# Linear trend slope                                                             #
# ============================================================================ #

def _trend_slope(series: np.ndarray) -> float:
    """Return OLS slope (units per sample index). Returns 0 if < 2 points."""
    n = len(series)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    y_mean = series.mean()
    denom = float(np.sum((x - x_mean) ** 2))
    if denom == 0:
        return 0.0
    return float(np.sum((x - x_mean) * (series - y_mean)) / denom)


# ============================================================================ #
# Helper: is_likely_endurance                                                    #
# ============================================================================ #

def is_likely_endurance(
    pct_ftp_series: np.ndarray,
    cfg: dict,
) -> tuple:
    """
    Return (bool, score) where score is 0..1 representing endurance likelihood.

    Thresholds are driven entirely by cfg, which varies by activity tier:
    - smart_trainer / indoor: strict fraction threshold (0.85) — steady trainer
      sessions spend the vast majority of time in the endurance zone.
    - outdoor: lower fraction threshold (0.50) — variable terrain means even a
      genuine endurance ride will have significant time above 0.60 FTP.
      The interval repeatability check is the primary discriminator for outdoor.
    """
    if len(pct_ftp_series) == 0:
        return False, 0.0

    threshold = cfg["endurance_pct_ftp_threshold"]
    fraction_below = float(np.mean(pct_ftp_series <= threshold))

    if fraction_below < cfg["endurance_fraction_threshold"]:
        return False, fraction_below

    # Check for repeated interval structure across the whole series.
    interval_result = detect_repeated_intervals(pct_ftp_series, 0, cfg)
    has_intervals = interval_result["interval_count"] >= cfg["minimum_repeated_intervals"]
    rep_score = interval_result["repeatability_score"]

    if has_intervals and rep_score >= cfg["endurance_repeatability_min"]:
        # Has clear structured intervals — not purely endurance
        return False, fraction_below * 0.5

    score = min(1.0, fraction_below)
    return True, score


# ============================================================================ #
# Helper: find_main_set_candidates                                               #
# ============================================================================ #

def find_main_set_candidates(
    pct_ftp_series: np.ndarray,
    cfg: dict,
) -> list:
    """
    Return a list of candidate warmup-end indices to evaluate.

    The search window is read directly from cfg["search_window_s"], which is
    set per activity tier. Candidates are evenly spaced within the window and
    sorted by local power (ascending) so transition points are evaluated first.
    """
    n = len(pct_ftp_series)
    if n == 0:
        return []

    max_dur = cfg["candidate_warmup_max_duration_s"]
    upper = min(n - 1, min(cfg["search_window_s"], max_dur))
    lower = cfg["candidate_min_duration_s"]

    if upper <= lower:
        return []

    step = cfg["candidate_step_s"]
    candidates = list(range(lower, upper + 1, step))

    if upper not in candidates:
        candidates.append(upper)

    def _local_power(idx):
        lo = max(0, idx - 15)
        hi = min(n, idx + 15)
        return float(np.mean(pct_ftp_series[lo:hi]))

    candidates.sort(key=_local_power)
    return candidates


# ============================================================================ #
# Helper: detect_repeated_intervals                                              #
# ============================================================================ #

def detect_repeated_intervals(
    pct_ftp_series: np.ndarray,
    start_idx: int,
    cfg: dict,
) -> dict:
    """
    Detect repeated work/recovery intervals in pct_ftp_series[start_idx:].

    Returns a dict with:
        interval_count          int
        work_durations          list[int]
        work_powers             list[float]
        recovery_durations      list[int]
        repeatability_score     float  0..1
        first_interval_start_s  int or None   (relative to full series start)
    """
    series = pct_ftp_series[start_idx:]
    n = len(series)

    work_floor = cfg["interval_work_floor_pct_ftp"]
    min_dur = cfg["min_interval_duration_s"]

    on = series >= work_floor

    # Run-length encode
    blocks = []  # (is_work, start_local, length)
    i = 0
    while i < n:
        state = bool(on[i])
        j = i
        while j < n and bool(on[j]) == state:
            j += 1
        blocks.append((state, i, j - i))
        i = j

    # Absorb very short noise blocks (< min_dur)
    merged = []
    for state, start, length in blocks:
        if not merged:
            merged.append([state, start, length])
            continue
        prev = merged[-1]
        if length < min_dur and state != prev[0]:
            prev[2] += length
        else:
            merged.append([state, start, length])

    work_blocks = [(s, l) for (is_w, s, l) in merged if is_w and l >= min_dur]
    rec_blocks  = [(s, l) for (is_w, s, l) in merged if not is_w and l >= min_dur // 2]

    if len(work_blocks) < 2:
        return {
            "interval_count": len(work_blocks),
            "work_durations": [],
            "work_powers": [],
            "recovery_durations": [],
            "repeatability_score": 0.0,
            "first_interval_start_s": None,
        }

    work_durations = [l for (_, l) in work_blocks]
    work_powers = [
        float(np.mean(series[s: s + l])) if l > 0 else 0.0
        for s, l in work_blocks
    ]
    recovery_durations = [l for (_, l) in rec_blocks]

    def _cv(vals):
        if len(vals) < 2:
            return 0.0
        mean_v = sum(vals) / len(vals)
        if mean_v == 0:
            return 1.0
        std_v = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / len(vals))
        return std_v / mean_v

    dur_cv = _cv(work_durations)
    pow_cv = _cv(work_powers)
    repeatability_score = max(0.0, 1.0 - (dur_cv + pow_cv))

    first_start_global = (work_blocks[0][0] + start_idx) if work_blocks else None

    return {
        "interval_count": len(work_blocks),
        "work_durations": work_durations,
        "work_powers": work_powers,
        "recovery_durations": recovery_durations,
        "repeatability_score": float(np.clip(repeatability_score, 0.0, 1.0)),
        "first_interval_start_s": first_start_global,
    }


# ============================================================================ #
# Helper: detect_sustained_main_block                                            #
# ============================================================================ #

def detect_sustained_main_block(
    pct_ftp_series: np.ndarray,
    start_idx: int,
    cfg: dict,
    opening_mean: float = 0.0,
) -> dict:
    """
    Look for a long sustained high-intensity block starting at or after start_idx.

    Returns dict with:
        found           bool
        block_start_s   int or None
        block_duration_s int
        block_mean_pct_ftp float
    """
    series = pct_ftp_series[start_idx:]
    n = len(series)

    min_dur = cfg["sustained_block_min_duration_s"]
    min_pct = cfg["sustained_block_min_pct_ftp"]
    uplift  = cfg["sustained_block_intensity_uplift"]

    if n < min_dur:
        return {"found": False, "block_start_s": None, "block_duration_s": 0, "block_mean_pct_ftp": 0.0}

    smooth_60 = _rolling_mean(series, 60)

    in_block = False
    block_start = 0
    best_start = None
    best_mean  = 0.0
    best_dur   = 0

    for i, val in enumerate(smooth_60):
        above = val >= min_pct
        if above and not in_block:
            in_block = True
            block_start = i
        elif not above and in_block:
            dur = i - block_start
            mean_val = float(np.mean(series[block_start:i]))
            if dur >= min_dur and mean_val > opening_mean + uplift and dur > best_dur:
                best_dur   = dur
                best_start = block_start
                best_mean  = mean_val
            in_block = False

    if in_block:
        dur = len(smooth_60) - block_start
        mean_val = float(np.mean(series[block_start:]))
        if dur >= min_dur and mean_val > opening_mean + uplift and dur > best_dur:
            best_dur   = dur
            best_start = block_start
            best_mean  = mean_val

    if best_start is None:
        return {"found": False, "block_start_s": None, "block_duration_s": 0, "block_mean_pct_ftp": 0.0}

    return {
        "found": True,
        "block_start_s":     best_start + start_idx,
        "block_duration_s":  best_dur,
        "block_mean_pct_ftp": round(best_mean, 4),
    }


# ============================================================================ #
# Helper: score_warmup_candidate                                                 #
# ============================================================================ #

def score_warmup_candidate(
    pct_ftp_series: np.ndarray,
    candidate_end_idx: int,
    cfg: dict,
    total_duration_s: int = 0,
) -> tuple:
    """
    Score a candidate warmup end index.

    Returns (score: float, reason_codes: list[str]).

    All branching is driven by cfg values — there are no activity-type
    conditionals in this function. The activity_type_bonus in cfg is 0.0
    for outdoor, 0.08 for indoor, 0.10 for smart_trainer.
    """
    n = len(pct_ftp_series)
    if candidate_end_idx <= 0 or candidate_end_idx >= n:
        return 0.0, ["candidate_out_of_range"]

    opening = pct_ftp_series[:candidate_end_idx]
    after   = pct_ftp_series[candidate_end_idx:]

    if len(opening) == 0 or len(after) < 30:
        return 0.0, ["insufficient_data"]

    reasons = []
    score   = 0.0

    # --- Signal A1: opening average intensity (lower = more warmup-like) -----
    opening_mean = float(np.mean(opening))
    after_mean   = float(np.mean(after))
    if opening_mean < 0.75:
        score += 0.15
        reasons.append("low_opening_intensity")
    elif opening_mean < 0.85:
        score += 0.05
        reasons.append("moderate_opening_intensity")

    # --- Signal A2: opening has rising trend ----------------------------------
    slope     = _trend_slope(opening)
    norm_slope = slope * len(opening)
    if norm_slope > 0.05:
        score += 0.10
        reasons.append("rising_opening_trend")
    elif norm_slope > 0.02:
        score += 0.05
        reasons.append("slightly_rising_trend")

    # --- Signal A3: stepped / ramped shape ------------------------------------
    thirds = max(1, len(opening) // 3)
    t1 = float(np.mean(opening[:thirds]))
    t2 = float(np.mean(opening[thirds: 2 * thirds]))
    t3 = float(np.mean(opening[2 * thirds:]))
    if t3 > t2 > t1:
        score += 0.10
        reasons.append("stepped_warmup_shape")
    elif t2 > t1 and t3 >= t2 * 0.95:
        score += 0.05
        reasons.append("ramped_warmup_shape")

    # --- Signal A4: opening vs after intensity contrast -----------------------
    if after_mean > opening_mean * 1.10:
        score += 0.15
        reasons.append("main_set_intensity_uplift")
    elif after_mean > opening_mean * 1.05:
        score += 0.08
        reasons.append("mild_intensity_uplift")

    # --- Signal A5: power rise immediately after candidate --------------------
    window            = min(30, len(opening))
    pre_candidate     = float(np.mean(opening[-window:]))
    post_window       = min(30, len(after))
    post_candidate    = float(np.mean(after[:post_window]))
    if post_candidate > pre_candidate * 1.10:
        score += 0.10
        reasons.append("post_candidate_power_rise")

    # --- Signal A6: main set repeatability after candidate --------------------
    interval_result = detect_repeated_intervals(pct_ftp_series, candidate_end_idx, cfg)
    n_intervals  = interval_result["interval_count"]
    rep_score    = interval_result["repeatability_score"]
    first_iv_start = interval_result["first_interval_start_s"]
    work_powers  = interval_result.get("work_powers", [])

    # Only award the full interval bonus when post-candidate intervals are
    # consistent in power (low CV). A stepped/ramped pattern has high CV and
    # could itself be a warmup continuation rather than a true main set.
    pow_cv = 0.0
    if len(work_powers) >= 2:
        mean_p = sum(work_powers) / len(work_powers)
        if mean_p > 0:
            pow_cv = math.sqrt(
                sum((p - mean_p) ** 2 for p in work_powers) / len(work_powers)
            ) / mean_p
    main_set_consistent = pow_cv < 0.15

    if n_intervals >= cfg["minimum_repeated_intervals"]:
        if main_set_consistent:
            score += 0.20
            reasons.append(f"repeated_intervals_after_candidate_{n_intervals}")
            if rep_score > 0.6:
                score += 0.10
                reasons.append("high_repeatability")
        else:
            score += 0.05
            reasons.append(f"variable_intervals_after_candidate_{n_intervals}")
    elif n_intervals >= 2:
        score += 0.05
        reasons.append("partial_interval_structure")

    # --- Penalty B0: candidate is mid-rest ------------------------------------
    # Both pre and post windows at rest level → candidate is inside a rest /
    # stretch valley, not at a warmup-to-main-set boundary.
    if pre_candidate < 0.55 and post_candidate < 0.55:
        score -= 0.20
        reasons.append("penalty_candidate_mid_rest")

    # --- Signal A6b: sharp rest-to-work transition at candidate boundary ------
    # Pre at rest AND post immediately rising to work level — the clearest
    # possible warmup boundary signal.
    if pre_candidate < 0.55 and post_candidate > 0.75:
        score += 0.15
        reasons.append("rest_to_work_transition")

    # --- Signal A7: sustained block after candidate ---------------------------
    sustained = detect_sustained_main_block(pct_ftp_series, candidate_end_idx, cfg, opening_mean)
    if sustained["found"]:
        score += 0.10
        reasons.append("sustained_block_after_candidate")

    # --- Signal A8: activity type bonus (0.0 outdoor / 0.08 indoor / 0.10 smart_trainer)
    if cfg["activity_type_bonus"] > 0:
        score += cfg["activity_type_bonus"]
        reasons.append("activity_type_bonus")

    # --- Penalty B1: first interval starts very early (< 4 min) --------------
    if first_iv_start is not None and first_iv_start < cfg["min_first_interval_start_s"]:
        score -= 0.30
        reasons.append("penalty_first_interval_too_early")

    # --- Penalty B2: proposed warmup removes a true high-intensity interval ---
    opening_interval_result = _find_intervals_before(pct_ftp_series, candidate_end_idx, cfg)
    if opening_interval_result["structured_before_candidate"]:
        score -= 0.25
        reasons.append("penalty_removes_structured_interval")

    # --- Penalty B3: opening is not lower intensity than after ----------------
    if opening_mean >= after_mean:
        score -= 0.10
        reasons.append("penalty_opening_not_lower_than_after")

    # --- Penalty B4: warmup fraction > 35% of total --------------------------
    if total_duration_s > 0:
        warmup_fraction = candidate_end_idx / total_duration_s
        if warmup_fraction > cfg["max_warmup_fraction_of_total"]:
            score -= 0.15
            reasons.append("penalty_warmup_fraction_too_large")

    # --- Penalty B5: no structural change — uniform stochastic ---------------
    if n_intervals == 0 and not sustained["found"]:
        score -= 0.10
        reasons.append("penalty_no_main_set_detected")

    # --- Penalty B6: detected "main set" followed by a prolonged rest valley --
    # A genuine main set does not have a ~3.5 min rest valley right after it.
    # This pattern means the candidate is mid-warmup; the true main set follows.
    if n_intervals >= cfg["minimum_repeated_intervals"]:
        broad_end = min(n, 1200)
        if candidate_end_idx < broad_end:
            window_seg     = pct_ftp_series[candidate_end_idx:broad_end]
            rest_threshold = cfg["endurance_pct_ftp_threshold"]
            rest_min_s     = 200
            max_rest = cur_rest = 0
            for val in window_seg:
                if val <= rest_threshold:
                    cur_rest += 1
                    if cur_rest > max_rest:
                        max_rest = cur_rest
                else:
                    cur_rest = 0
            if max_rest >= rest_min_s:
                score -= 0.30
                reasons.append("penalty_rest_valley_after_candidate")

    return float(np.clip(score, 0.0, 1.0)), reasons


def _find_intervals_before(
    pct_ftp_series: np.ndarray,
    candidate_end_idx: int,
    cfg: dict,
) -> dict:
    """
    Check whether there is a repeated structured interval pattern (>= 2 intervals)
    that begins entirely before candidate_end_idx, at main-set intensity.

    Short warmup steps / openers (< 0.90 FTP) are not counted as structured
    intervals, so a stepped warmup does not trigger this penalty.
    """
    opening = pct_ftp_series[:candidate_end_idx]
    result  = detect_repeated_intervals(pct_ftp_series, 0, cfg)

    if result["interval_count"] < 2:
        return {"structured_before_candidate": False}

    if result["first_interval_start_s"] is None:
        return {"structured_before_candidate": False}

    # Count work intervals in the opening window that are at main-set intensity.
    # Threshold at 0.90 FTP: warmup openers / steps reach ~0.85 FTP;
    # true main-set work (threshold, VO2) is typically 0.90+ FTP.
    main_set_intensity_floor = 0.90
    work_floor = cfg["interval_work_floor_pct_ftp"]
    min_dur    = cfg["min_interval_duration_s"]

    on = (opening >= work_floor).tolist()
    high_intensity_count = 0
    i = 0
    n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            if (j - i) >= min_dur:
                seg_mean = float(np.mean(opening[i:j]))
                if seg_mean >= main_set_intensity_floor:
                    high_intensity_count += 1
            i = j
        else:
            i += 1

    structured = (
        high_intensity_count >= 2
        and result["repeatability_score"] > 0.3
    )
    return {"structured_before_candidate": structured}


# ============================================================================ #
# Main public function                                                           #
# ============================================================================ #

def detect_warmup(
    power_stream: list,
    ftp: float,
    cadence_stream: list = None,
    hr_stream: list = None,
    activity_type: str = None,
    classification: dict = None,
    cfg: dict = None,
) -> dict:
    """
    Detect whether an activity contains a structured warmup at the start.

    Parameters
    ----------
    power_stream    : watts, one value per second (or regularly sampled)
    ftp             : athlete FTP in watts
    cadence_stream  : optional, same length as power_stream
    hr_stream       : optional, same length as power_stream
    activity_type   : e.g. 'VirtualRide', 'Ride', 'EBikeRide'
    classification  : optional precomputed classification dict
    cfg             : optional config overrides (applied on top of the
                      tier-specific config, not the outdoor default)

    Returns
    -------
    dict with keys:
        warmup_detected         bool
        warmup_end_index        int or None
        warmup_end_s            int or None
        confidence              float
        detection_reason        str
        diagnostics             dict
    """
    # ------------------------------------------------------------------ #
    # Step 0: resolve activity tier and build config                       #
    # ------------------------------------------------------------------ #
    tier = _classify_activity_type(activity_type)
    cfg  = _select_cfg(tier, cfg)

    # ------------------------------------------------------------------ #
    # Guard: insufficient data                                              #
    # ------------------------------------------------------------------ #
    if not power_stream or ftp is None or ftp <= 0:
        return _no_warmup("insufficient_input_data", {})

    raw_power = np.array([p if p is not None else 0.0 for p in power_stream], dtype=float)
    n = len(raw_power)

    if n < cfg["candidate_min_duration_s"] * 2:
        return _no_warmup("activity_too_short", {"total_duration_s": n})

    # ------------------------------------------------------------------ #
    # Preprocess                                                            #
    # ------------------------------------------------------------------ #
    smooth_power = _rolling_mean(raw_power, cfg["smooth_window_s"])
    pct_ftp      = smooth_power / ftp

    # ------------------------------------------------------------------ #
    # Classification hint                                                   #
    # ------------------------------------------------------------------ #
    workout_type = None
    if classification:
        workout_type = (
            classification.get("workout_type")
            or (classification.get("classification") or {}).get("workout_type")
        )

    # ------------------------------------------------------------------ #
    # Step 1: endurance check                                               #
    # ------------------------------------------------------------------ #
    likely_endurance, endurance_score = is_likely_endurance(pct_ftp, cfg)

    if workout_type == "endurance":
        likely_endurance = True
        endurance_score  = max(endurance_score, 0.85)

    diagnostics: dict = {
        "activity_tier":             tier,
        "endurance_likelihood_score": round(endurance_score, 4),
        "is_likely_endurance":        likely_endurance,
        "total_duration_s":           n,
        "opening_mean_pct_ftp":       None,
        "opening_max_pct_ftp":        None,
        "opening_trend_slope":        None,
        "candidate_count":            0,
        "best_candidate_end_s":       None,
        "best_candidate_score":       None,
        "repeated_interval_count_after_candidate": None,
        "post_candidate_repeatability_score":       None,
        "reason_codes":               [],
    }

    if likely_endurance:
        logger.info("detect_warmup() → likely endurance, returning no warmup")
        return _no_warmup("endurance_ride_no_warmup_expected", diagnostics)

    # ------------------------------------------------------------------ #
    # Global guardrail: first substantial work interval before 4 min      #
    # ------------------------------------------------------------------ #
    _guardrail_cfg = dict(cfg)
    _guardrail_cfg["min_interval_duration_s"] = cfg["guardrail_min_interval_duration_s"]
    global_iv = detect_repeated_intervals(pct_ftp, 0, _guardrail_cfg)
    if (
        global_iv["interval_count"] >= cfg["minimum_repeated_intervals"]
        and global_iv["first_interval_start_s"] is not None
        and global_iv["first_interval_start_s"] < cfg["min_first_interval_start_s"]
    ):
        logger.info(
            f"detect_warmup() → first interval at {global_iv['first_interval_start_s']}s "
            f"< {cfg['min_first_interval_start_s']}s, no warmup possible"
        )
        diagnostics["reason_codes"] = ["first_interval_too_early_global"]
        return _no_warmup("first_interval_too_early", diagnostics)

    # ------------------------------------------------------------------ #
    # Step 2: find candidate warmup end-points                              #
    # ------------------------------------------------------------------ #
    candidates = find_main_set_candidates(pct_ftp, cfg)
    diagnostics["candidate_count"] = len(candidates)

    if not candidates:
        return _no_warmup("no_candidates_found", diagnostics)

    # ------------------------------------------------------------------ #
    # Step 3: score each candidate                                          #
    # ------------------------------------------------------------------ #
    best_idx    = None
    best_score  = 0.0
    best_reasons: list = []

    for cand in candidates:
        score, reasons = score_warmup_candidate(
            pct_ftp,
            cand,
            cfg,
            total_duration_s=n,
        )
        if score > best_score:
            best_score   = score
            best_idx     = cand
            best_reasons = reasons

    diagnostics["best_candidate_end_s"]    = best_idx
    diagnostics["best_candidate_score"]    = round(best_score, 4) if best_score else None
    diagnostics["reason_codes"]            = best_reasons

    # ------------------------------------------------------------------ #
    # Step 4: guardrails before accepting                                   #
    # ------------------------------------------------------------------ #
    if best_idx is None or best_score < cfg["minimum_confidence_to_accept"]:
        return _no_warmup("score_below_threshold", diagnostics)

    if "penalty_first_interval_too_early" in best_reasons:
        iv_check = detect_repeated_intervals(pct_ftp, best_idx, cfg)
        first_iv = iv_check.get("first_interval_start_s")
        if first_iv is not None and first_iv < cfg["min_first_interval_start_s"]:
            return _no_warmup("first_interval_too_early", diagnostics)

    if best_idx > cfg["candidate_warmup_max_duration_s"]:
        return _no_warmup("warmup_exceeds_max_duration", diagnostics)

    if n > 0 and (best_idx / n) > cfg["max_warmup_fraction_of_total"]:
        return _no_warmup("warmup_fraction_exceeds_limit", diagnostics)

    # ------------------------------------------------------------------ #
    # Step 5: populate diagnostics                                          #
    # ------------------------------------------------------------------ #
    opening = pct_ftp[:best_idx]
    diagnostics["opening_mean_pct_ftp"]  = round(float(np.mean(opening)), 4)
    diagnostics["opening_max_pct_ftp"]   = round(float(np.max(opening)), 4)
    diagnostics["opening_trend_slope"]   = round(_trend_slope(opening) * len(opening), 4)

    iv_after = detect_repeated_intervals(pct_ftp, best_idx, cfg)
    diagnostics["repeated_interval_count_after_candidate"] = iv_after["interval_count"]
    diagnostics["post_candidate_repeatability_score"]      = round(iv_after["repeatability_score"], 4)
    diagnostics["first_high_intensity_s"]                  = iv_after["first_interval_start_s"]

    slope_total = _trend_slope(opening) * len(opening) if len(opening) > 0 else 0.0
    if slope_total > 0.05:
        diagnostics["opening_trend"] = "rising"
    elif slope_total < -0.05:
        diagnostics["opening_trend"] = "falling"
    else:
        diagnostics["opening_trend"] = "flat"

    diagnostics["main_set_repeatability_score"] = round(iv_after["repeatability_score"], 4)
    diagnostics["post_warmup_drop_detected"] = (
        "post_candidate_power_rise" in best_reasons
        or "main_set_intensity_uplift" in best_reasons
    )

    # ------------------------------------------------------------------ #
    # Step 6: build detection reason string                                 #
    # ------------------------------------------------------------------ #
    reason = _build_reason_string(best_reasons, best_idx, iv_after)

    logger.info(
        f"detect_warmup() → warmup detected end={best_idx}s "
        f"confidence={best_score:.2f} tier={tier} reason={reason}"
    )

    return {
        "warmup_detected":   True,
        "warmup_end_index":  best_idx,
        "warmup_end_s":      best_idx,
        "confidence":        round(best_score, 4),
        "detection_reason":  reason,
        "diagnostics":       diagnostics,
    }


# ============================================================================ #
# Private helpers                                                                #
# ============================================================================ #

def _no_warmup(reason: str, diagnostics: dict) -> dict:
    return {
        "warmup_detected":  False,
        "warmup_end_index": None,
        "warmup_end_s":     None,
        "confidence":       0.0,
        "detection_reason": reason,
        "diagnostics":      diagnostics,
    }


def _build_reason_string(reason_codes: list, warmup_end: int, iv_result: dict) -> str:
    parts = []
    if "stepped_warmup_shape" in reason_codes:
        parts.append("stepped low-to-rising opening segment")
    elif "ramped_warmup_shape" in reason_codes:
        parts.append("ramped low-to-rising opening segment")
    elif "rising_opening_trend" in reason_codes:
        parts.append("rising opening segment")
    else:
        parts.append("low-intensity opening segment")

    n_iv = iv_result.get("interval_count", 0)
    if n_iv >= 3:
        parts.append(f"before {n_iv} repeated main-set intervals")
    elif "sustained_block_after_candidate" in reason_codes:
        parts.append("before sustained main-set block")

    if "activity_type_bonus" in reason_codes:
        parts.append("(indoor)")

    return ", ".join(parts) if parts else "warmup characteristics detected"
