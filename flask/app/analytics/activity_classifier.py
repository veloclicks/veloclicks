"""
Workout classification and interval session detection.

Classification hierarchy:
  1. Power-based (NP % FTP) — primary
  2. HR-based (avg HR % max HR) — fallback when no power data

Workout types: endurance | tempo | threshold | vo2

Interval types (for threshold and vo2 sessions):
  Type I  — few long sustained efforts (e.g. 2x20min at threshold)
  Type II — multiple short repeats in sets (e.g. 3x(2min on / 1min off))

Interval detection pipeline:
  _analyse_activity_structure() → lap-based or power-stream detection
    → _detect_intervals_and_recoveries()
    → _strip_fringe_intervals()
    → _validate_interval_session()
    → _group_into_sets() + compute_summary()
"""

import json
import logging
from typing import Optional

from app.strava.service import get_activity_streams, get_activity_laps
from app.analytics.activity_derivations import (
    _NumpyEncoder,
    compute_interval_metrics,
    compute_interval_summary,
)

logger = logging.getLogger(__name__)


# ============================================================================ #
# Workout type classification — tunable constants                                #
# ============================================================================ #

# Power zone boundaries (NP as fraction of FTP)
POWER_ENDURANCE_MAX  = 0.75
POWER_TEMPO_MAX      = 0.90
POWER_THRESHOLD_MAX  = 1.05

# HR zone boundaries (avg HR as fraction of max HR)
HR_ENDURANCE_MAX     = 0.75
HR_TEMPO_MAX         = 0.85
HR_THRESHOLD_MAX     = 0.92

# Interval type boundaries
TYPE_I_MIN_DURATION_S  = 480   # avg >= 8 min → Type I
TYPE_I_MAX_COUNT       = 5
TYPE_II_MAX_DURATION_S = 300   # avg < 5 min → Type II

INTERVAL_THRESHOLD_FLOOR = 0.85
INTERVAL_VO2_FLOOR       = 1.05


# ============================================================================ #
# Interval session detection — tunable constants                                 #
# ============================================================================ #

MIN_INTERVAL_DURATION_S         = 20
MIN_INTERVAL_COUNT              = 3
MIN_AVG_INTERVAL_DURATION_S     = 20
LONG_INTERVAL_MIN_DURATION_S    = 360  # avg >= 6 min → only 2 reps needed

INDOOR_WARMUP_S                 = 600
LONG_OUTDOOR_RIDE_S             = 10800

POWER_DIP_MERGE_S               = 90
POWER_DIP_MERGE_FLOOR           = 0.65

WARMUP_POWER_RATIO              = 0.92
WARMUP_DURATION_RATIO           = 0.40
MIN_POWER_CONTRAST_RATIO        = 1.30

BIMODAL_WARMUP_STRIP_S          = 300
BIMODAL_BIN_W                   = 10
BIMODAL_MIN_SEPARATION_W        = 50
BIMODAL_MIN_VALLEY_DEPTH        = 0.35


# ============================================================================ #
# Public API                                                                     #
# ============================================================================ #

def classify_activity(user_id: int, activity_id: int) -> dict:
    """
    Classify an activity: fetch athlete + activity data, detect interval structure,
    then label workout type.

    Returns:
        {
            'classification':  dict  (workout_type, interval_type, method, confidence, detail)
            'evidence':        dict  (compact interval detection fields)
            'evidence_detail': dict  (sets, summary, intervals — verbose per-rep data)
        }
    """
    import json as _json
    from app.models.user import User
    from app.models.strava import Activity

    EVIDENCE_DETAIL_KEYS = {'sets', 'summary', 'intervals'}

    # Fetch athlete thresholds needed for zone boundary comparisons
    user     = User.query.get(user_id)
    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()

    ftp        = float(user.ftp)            if user and user.ftp            else None
    max_hr     = float(user.max_heart_rate) if user and user.max_heart_rate else None
    np_watts   = float(activity.weighted_average_watts) if activity and activity.weighted_average_watts else None
    avg_hr_bpm = float(activity.average_heartrate)      if activity and activity.average_heartrate      else None
    is_indoor  = activity.type == 'VirtualRide'         if activity                                     else False
    moving_time_s = float(activity.moving_time)         if activity and activity.moving_time            else None

    # Detect interval structure from power stream or laps.
    # This must run before classification so we can use avg interval power
    # rather than whole-ride NP, which is suppressed by warm-up and rest periods
    # and would systematically underclassify interval sessions (e.g. VO2 looks like tempo).
    raw = _analyse_activity_structure(
        user_id, activity_id,
        is_indoor=is_indoor, moving_time_s=moving_time_s,
    )
    structure = _json.loads(raw) if raw else {}

    interval_summary = None
    if structure.get('is_interval_session') and structure.get('summary'):
        interval_summary = structure['summary']
        interval_summary['interval_count'] = structure.get('interval_count', 0)

    # Label the workout type by comparing a power (or HR) ratio against fixed zone boundaries.
    # Priority: interval power > whole-ride NP > avg HR (HR is a fallback when no power data).
    workout_type, method, confidence, detail = _classify_type(
        np_watts, avg_hr_bpm, ftp, max_hr, interval_summary
    )

    # For threshold/vo2 sessions, further distinguish interval structure:
    # Type I = few long sustained efforts (e.g. 2x20min); Type II = short repeats (e.g. 8x3min)
    interval_type = None
    if workout_type in ('threshold', 'vo2') and interval_summary:
        interval_type = _classify_interval_type(interval_summary)

    logger.info(
        f"classify_activity() → {workout_type}"
        + (f" / {interval_type}" if interval_type else "")
        + f" (method={method}, confidence={confidence})"
    )

    classification = {
        'workout_type':          workout_type,
        'interval_type':         interval_type,
        'classification_method': method,
        'confidence':            confidence,
        'detail':                detail,
    }

    evidence        = {k: v for k, v in structure.items() if k not in EVIDENCE_DETAIL_KEYS}
    evidence_detail = {k: v for k, v in structure.items() if k     in EVIDENCE_DETAIL_KEYS}

    return {
        'classification':  classification,
        'evidence':        evidence,
        'evidence_detail': evidence_detail or None,
    }


def _analyse_activity_structure(
    user_id:       str,
    activity_id:   str,
    is_indoor:     bool = False,
    moving_time_s: Optional[float] = None,
) -> str:
    """
    Detect whether an activity is a structured interval session and characterise
    its interval structure. Returns a JSON string.

    Args:
        user_id:       User ID for authentication
        activity_id:   Strava activity ID
        is_indoor:     True for VirtualRide / trainer activities
        moving_time_s: Activity moving time in seconds

    Returns:
        JSON string
    """
    logger.info(f"_analyse_activity_structure() user={user_id} activity={activity_id}")

    result: dict = {"activity_id": str(activity_id)}

    laps = get_activity_laps(user_id, activity_id)
    if laps and len(laps) >= 4:
        lap_structure = _structure_from_laps(laps)
        if lap_structure.get('is_interval_session'):
            logger.info("_analyse_activity_structure() using lap-based detection")
            result.update(lap_structure)
            return json.dumps(result, cls=_NumpyEncoder)

    logger.info("_analyse_activity_structure() falling back to power stream detection")
    streams = get_activity_streams(
        user_id, activity_id,
        stream_types=['time', 'watts', 'heartrate', 'cadence']
    )

    if not streams or 'watts' not in streams:
        logger.warning("_analyse_activity_structure() no power stream available")
        result.update({
            "is_interval_session": False,
            "confidence":          "low",
            "detection_method":    "none",
        })
        return json.dumps(result, cls=_NumpyEncoder)

    result.update(_structure_from_power_stream(
        streams, is_indoor=is_indoor, moving_time_s=moving_time_s
    ))
    return json.dumps(result, cls=_NumpyEncoder)


# ============================================================================ #
# Workout type — internal helpers                                                 #
# ============================================================================ #

def _classify_type(
    np_watts:         Optional[float],
    avg_hr_bpm:       Optional[float],
    ftp:              Optional[float],
    max_hr:           Optional[float],
    interval_summary: Optional[dict] = None,
) -> tuple:
    """Returns (workout_type, method, confidence, detail)."""
    if ftp and ftp > 0:
        interval_power = interval_summary.get('avg_interval_power_w') if interval_summary else None

        if interval_power and interval_power > 0:
            ratio = interval_power / ftp
            method, confidence = 'power_interval', 'high'
            label = f"avg interval power {interval_power:.0f}W is {ratio:.0%} of FTP"
        elif np_watts and np_watts > 0:
            ratio = np_watts / ftp
            method, confidence = 'power', 'high'
            label = f"whole-ride NP {np_watts:.0f}W is {ratio:.0%} of FTP"
        else:
            ratio = None

        if ratio is not None:
            if ratio <= POWER_ENDURANCE_MAX:
                return ('endurance', method, confidence, f"{label} — endurance zone")
            if ratio <= POWER_TEMPO_MAX:
                return ('tempo', method, confidence, f"{label} — tempo zone")
            if ratio <= POWER_THRESHOLD_MAX:
                return ('threshold', method, confidence, f"{label} — threshold zone")
            return ('vo2', method, confidence, f"{label} — VO2 / above threshold")

    if avg_hr_bpm and max_hr and max_hr > 0:
        ratio      = avg_hr_bpm / max_hr
        method     = 'hr'
        confidence = 'medium'
        if ratio <= HR_ENDURANCE_MAX:
            return ('endurance', method, confidence,
                    f"Avg HR {avg_hr_bpm:.0f}bpm is {ratio:.0%} of max — endurance zone")
        if ratio <= HR_TEMPO_MAX:
            return ('tempo', method, confidence,
                    f"Avg HR {avg_hr_bpm:.0f}bpm is {ratio:.0%} of max — tempo zone")
        if ratio <= HR_THRESHOLD_MAX:
            return ('threshold', method, confidence,
                    f"Avg HR {avg_hr_bpm:.0f}bpm is {ratio:.0%} of max — threshold zone")
        return ('vo2', method, confidence,
                f"Avg HR {avg_hr_bpm:.0f}bpm is {ratio:.0%} of max — VO2 zone")

    return ('endurance', 'unknown', 'low',
            "Insufficient data (no power or HR) — defaulting to endurance")


def _classify_interval_type(interval_summary: dict) -> Optional[str]:
    avg_duration   = interval_summary.get('avg_interval_duration_s', 0)
    interval_count = interval_summary.get('interval_count', 0)

    if avg_duration >= TYPE_I_MIN_DURATION_S and interval_count <= TYPE_I_MAX_COUNT:
        logger.info(f"_classify_interval_type() → type_i (avg {avg_duration:.0f}s, {interval_count} intervals)")
        return 'type_i'

    if avg_duration < TYPE_II_MAX_DURATION_S or interval_count > TYPE_I_MAX_COUNT:
        logger.info(f"_classify_interval_type() → type_ii (avg {avg_duration:.0f}s, {interval_count} intervals)")
        return 'type_ii'

    logger.info(f"_classify_interval_type() → type_i (borderline, avg {avg_duration:.0f}s, {interval_count} intervals)")
    return 'type_i'


# ============================================================================ #
# Interval detection — internal helpers                                          #
# ============================================================================ #

def _laps_look_like_intervals(laps: list) -> bool:
    if len(laps) < 4:
        return False
    powers    = [lap.get('average_watts', 0) for lap in laps]
    durations = [lap.get('elapsed_time',  0) for lap in laps]
    alternating_count = sum(
        1 for i in range(2, len(powers))
        if (powers[i] > powers[i - 1]) != (powers[i - 1] > powers[i - 2])
    )
    alternating = alternating_count > len(powers) * 0.4
    mean_dur = sum(durations) / len(durations) if durations else 0
    if mean_dur > 0:
        consistent_count    = sum(1 for d in durations if abs(d - mean_dur) < mean_dur * 0.3)
        duration_consistent = consistent_count > len(durations) * 0.6
    else:
        duration_consistent = False
    return alternating and duration_consistent


def _structure_from_laps(laps: list) -> dict:
    """Reconstruct work bouts from consecutive high-power laps.

    TrainerRoad frequently records one effort as multiple laps (e.g. an
    over/under or a two-stage VO2 rep). A sustained low-power recovery, not a
    lap boundary, separates repetitions. The last substantial low-power
    recovery before the repeated work also separates stepped warmups.
    """
    if not laps:
        return {"is_interval_session": False, "confidence": "low", "detection_method": "laps"}

    powers = [float(lap.get('average_watts') or 0) for lap in laps]
    max_power = max(powers, default=0)
    if max_power <= 0:
        return {"is_interval_session": False, "confidence": "low", "detection_method": "laps"}

    # Only a clearly low-power recovery can separate efforts. This also
    # prevents adjacent 44s/74s VO2 stages from becoming separate reps.
    recovery_floor = max_power * 0.60
    work_floor = max_power * 0.70
    # A substantial early recovery marks the end of the warmup. The rule
    # requires subsequent repeated work, so it does not discard the first
    # interval of sessions that begin immediately with work.
    start = 0
    elapsed = 0
    for i, lap in enumerate(laps[:-2]):
        elapsed += float(lap.get('elapsed_time') or 0)
        if elapsed > 1500:
            break
        if (float(lap.get('elapsed_time') or 0) >= 180
                and powers[i] < recovery_floor
                and sum(p >= work_floor for p in powers[i + 1:]) >= 3):
            # Use the last qualifying warm-up recovery, not the first:
            # a stepped warm-up can include several low-power stages.
            start = i + 1

    intervals, recoveries = [], []
    current = []
    pending_recovery = []
    def aggregate(parts):
        duration = sum(float(p.get('elapsed_time') or 0) for p in parts)
        if not duration:
            return None
        def weighted(key):
            samples = [(float(p[key]), float(p.get('elapsed_time') or 0))
                       for p in parts if p.get(key) is not None]
            total = sum(d for _, d in samples)
            return round(sum(v * d for v, d in samples) / total, 0) if total else 0
        return {
            'duration_s': duration,
            'avg_power_w': weighted('average_watts'),
            'max_power_w': max((float(p.get('max_watts') or p.get('average_watts') or 0)
                                for p in parts), default=None),
            'avg_hr_bpm': weighted('average_heartrate'),
            'max_hr_bpm': max((float(p.get('max_heartrate') or 0) for p in parts), default=None),
            'avg_cadence_rpm': weighted('average_cadence'),
        }

    for lap in laps[start:]:
        power = float(lap.get('average_watts') or 0)
        if power >= work_floor:
            if pending_recovery and current:
                # A short transition between high-power laps is not a rest.
                if sum(float(x.get('elapsed_time') or 0) for x in pending_recovery) >= 45:
                    entry = aggregate(current)
                    if entry:
                        entry['rep_number'] = len(intervals) + 1
                        intervals.append(entry)
                    recovery = aggregate(pending_recovery)
                    if recovery:
                        recovery['after_rep'] = len(intervals)
                        recoveries.append(recovery)
                    current = []
                else:
                    current.extend(pending_recovery)
                pending_recovery = []
            current.append(lap)
        elif current:
            pending_recovery.append(lap)
    if current:
        entry = aggregate(current)
        if entry:
            entry['rep_number'] = len(intervals) + 1
            intervals.append(entry)

    reason = _validate_interval_session(intervals, recoveries)
    if reason:
        return {"is_interval_session": False, "confidence": "medium",
                "detection_method": "laps", "interval_rejection_reason": reason,
                "intervals_detected": len(intervals)}
    return {
        "is_interval_session": True,
        "confidence": "medium",
        "detection_method": "laps",
        "interval_count": len(intervals),
        "sets": _group_into_sets(intervals, recoveries, set_gap_s=300),
        "summary": compute_interval_summary(intervals, recoveries),
    }


def _structure_from_power_stream(
    streams:       dict,
    is_indoor:     bool = False,
    moving_time_s: Optional[float] = None,
) -> dict:
    power_data = streams['watts']['data']
    time_data  = streams['time']['data']
    hr_data    = streams.get('heartrate', {}).get('data', [None] * len(time_data))
    cad_data   = streams.get('cadence',   {}).get('data', [None] * len(time_data))

    if not is_indoor and moving_time_s and moving_time_s > LONG_OUTDOOR_RIDE_S:
        logger.info(
            f"_structure_from_power_stream() outdoor ride {moving_time_s/3600:.1f}h "
            f"> {LONG_OUTDOOR_RIDE_S/3600:.0f}h — skipping interval detection"
        )
        return {
            "is_interval_session":       False,
            "confidence":                "high",
            "detection_method":          "power_stream",
            "interval_rejection_reason": f"outdoor ride {moving_time_s/3600:.1f}h — assumed endurance",
        }

    sorted_power = sorted(p for p in power_data if p is not None)
    if not sorted_power:
        return {"is_interval_session": False, "confidence": "low", "detection_method": "power_stream"}

    p95       = sorted_power[int(len(sorted_power) * 0.95)]
    threshold = p95 * 0.80

    intervals, recoveries = _detect_intervals_and_recoveries(
        power_data, time_data, hr_data, cad_data, threshold,
        min_duration_s=MIN_INTERVAL_DURATION_S
    )

    if is_indoor and time_data:
        # Do not use a fixed ten-minute cutoff: trainer warm-ups often contain
        # ramp steps beyond ten minutes that cross the power detection threshold.
        intervals, recoveries = _exclude_indoor_warmup(
            intervals, recoveries, ride_start_s=time_data[0]
        )

    _strip_fringe_intervals(intervals, recoveries)

    reason = _validate_interval_session(intervals, recoveries)
    if reason:
        logger.info(f"_analyse_activity_structure() not a structured session: {reason}")
        return {
            "is_interval_session":       False,
            "confidence":                "high",
            "detection_method":          "power_stream",
            "interval_rejection_reason": reason,
            "intervals_detected":        len(intervals),
        }

    sets    = _group_into_sets(intervals, recoveries, set_gap_s=300)
    summary = compute_interval_summary(intervals, recoveries)

    return {
        "is_interval_session": True,
        "confidence":          "high" if len(intervals) >= 4 else "medium",
        "detection_method":    "power_stream",
        "interval_count":      len(intervals),
        "sets":                sets,
        "summary":             summary,
    }



def _exclude_indoor_warmup(intervals: list, recoveries: list, ride_start_s: float) -> tuple:
    """Exclude an early ramp effort only when later repetitions establish a pattern.

    Conservative by design: an early effort is retained if there is insufficient
    evidence that it differs from the main work. Never discard a genuine first
    interval simply because it occurs in the first ten minutes.
    """
    if len(intervals) < 3:
        return intervals, recoveries

    remaining = list(intervals)
    while len(remaining) >= 3:
        first = remaining[0]
        later = remaining[1:]
        # A warm-up candidate must start within the first 25 minutes.
        if first.get('start_s', float('inf')) - ride_start_s > 1500:
            break
        powers = sorted(iv.get('avg_power_w', 0) for iv in later)
        durations = sorted(iv.get('duration_s', 0) for iv in later)
        typical_power = powers[len(powers) // 2]
        typical_duration = durations[len(durations) // 2]
        if not typical_power or not typical_duration:
            break
        # Ramp steps are normally shorter or materially easier than the
        # repeated main efforts. Require two later comparable repetitions.
        comparable = sum(
            abs(iv.get('avg_power_w', 0) - typical_power) <= typical_power * 0.12
            and abs(iv.get('duration_s', 0) - typical_duration) <= typical_duration * 0.30
            for iv in later
        )
        is_ramp_step = (
            first.get('avg_power_w', 0) < typical_power * 0.90
            or first.get('duration_s', 0) < typical_duration * 0.45
        )
        if comparable < 2 or not is_ramp_step:
            break
        logger.info("_exclude_indoor_warmup() excluded early ramp effort at %ss",
                    first.get('start_s'))
        remaining.pop(0)

    removed = len(intervals) - len(remaining)
    if not removed:
        return intervals, recoveries

    for index, iv in enumerate(remaining, 1):
        iv['rep_number'] = index
    # Recovery entries are still useful for the time series, but only
    # recoveries between retained work intervals belong to interval analysis.
    kept_recoveries = []
    for recovery in recoveries:
        after = recovery.get('after_rep')
        if after is None or after <= removed or after >= len(intervals):
            continue
        r = dict(recovery)
        r['after_rep'] = after - removed
        kept_recoveries.append(r)
    return remaining, kept_recoveries


def _validate_interval_session(intervals: list, recoveries: list) -> Optional[str]:
    if not intervals:
        return "no intervals detected"

    durations = [iv.get('duration_s', 0) for iv in intervals]
    avg_dur   = sum(durations) / len(durations)

    min_count = 2 if avg_dur >= LONG_INTERVAL_MIN_DURATION_S else MIN_INTERVAL_COUNT
    if len(intervals) < min_count:
        return f"only {len(intervals)} intervals detected (minimum {min_count})"

    if avg_dur < MIN_AVG_INTERVAL_DURATION_S:
        return f"avg interval duration {avg_dur:.0f}s is below minimum {MIN_AVG_INTERVAL_DURATION_S}s"

    inter_rep     = [r for r in recoveries if 'after_rep' in r]
    avg_iv_power  = sum(iv.get('avg_power_w', 0) for iv in intervals) / len(intervals)
    avg_rec_power = (sum(r.get('avg_power_w', 0) for r in inter_rep) / len(inter_rep)
                     if inter_rep else 0)
    if avg_rec_power > 0:
        contrast = avg_iv_power / avg_rec_power
        if contrast < MIN_POWER_CONTRAST_RATIO:
            return (
                f"insufficient power contrast (interval {avg_iv_power:.0f}W vs "
                f"recovery {avg_rec_power:.0f}W, ratio {contrast:.2f}) — likely unstructured ride"
            )

    return None


def _detect_intervals_and_recoveries(
    power_data:     list,
    time_data:      list,
    hr_data:        list,
    cad_data:       list,
    threshold:      float,
    min_duration_s: int = MIN_INTERVAL_DURATION_S,
    merge_gap_s:    int = 10,
) -> tuple:
    max_power   = max((p for p in power_data if p is not None), default=1)
    on_interval = [p is not None and p >= threshold for p in power_data]

    blocks: list = []
    i = 0
    while i < len(on_interval):
        state = on_interval[i]
        j = i
        while j < len(on_interval) and on_interval[j] == state:
            j += 1
        duration = time_data[min(j, len(time_data) - 1)] - time_data[i]
        p_vals   = [x for x in power_data[i:j] if x is not None]
        avg_p    = sum(p_vals) / len(p_vals) if p_vals else 0.0
        blocks.append({
            'state':      'on' if state else 'off',
            'start_idx':  i,
            'end_idx':    j - 1,
            'duration_s': duration,
            'avg_power':  avg_p,
        })
        i = j

    merged: list = []
    for block in blocks:
        if not merged:
            merged.append(dict(block))
            continue
        prev = merged[-1]
        if block['state'] == 'off' and prev['state'] == 'on':
            power_dip = (block['duration_s'] <= POWER_DIP_MERGE_S
                         and block['avg_power'] >= threshold * POWER_DIP_MERGE_FLOOR)
            if block['duration_s'] <= merge_gap_s or power_dip:
                prev['end_idx']        = block['end_idx']
                prev['duration_s']    += block['duration_s']
                prev['_pending_merge'] = True
            else:
                merged.append(dict(block))
        elif block['state'] == 'on' and prev.get('_pending_merge'):
            prev['end_idx']     = block['end_idx']
            prev['duration_s'] += block['duration_s']
            prev.pop('_pending_merge')
        else:
            b = dict(block)
            b.pop('_pending_merge', None)
            merged.append(b)

    merged = [
        b for b in merged
        if b['state'] == 'off' or b['duration_s'] >= min_duration_s
    ]

    intervals:  list = []
    recoveries: list = []
    rep_num = 1
    for block in merged:
        if block['state'] == 'on':
            m = compute_interval_metrics(block, power_data, time_data, hr_data, cad_data, max_power, is_interval=True)
            m['rep_number'] = rep_num
            intervals.append(m)
            rep_num += 1
        else:
            m = compute_interval_metrics(block, power_data, time_data, hr_data, cad_data, max_power, is_interval=False)
            if intervals:
                m['after_rep'] = len(intervals)
            recoveries.append(m)

    return intervals, recoveries


def _strip_fringe_intervals(intervals: list, recoveries: list) -> None:
    def _medians(ivs):
        powers    = sorted(iv.get('avg_power_w', 0) for iv in ivs)
        durations = sorted(iv.get('duration_s',  0) for iv in ivs)
        med_p = powers[len(powers) // 2]       if powers    else 0
        med_d = durations[len(durations) // 2] if durations else 0
        return med_p, med_d

    def _is_fringe(iv, med_p, med_d):
        low_power  = med_p > 0 and iv.get('avg_power_w', 0) < med_p * WARMUP_POWER_RATIO
        very_short = med_d > 0 and iv.get('duration_s',  0) < med_d * WARMUP_DURATION_RATIO
        return low_power or very_short

    def _drop_first(intervals, recoveries):
        med_p, med_d = _medians(intervals[1:])
        first = intervals[0]
        if _is_fringe(first, med_p, med_d):
            logger.info(
                f"_strip_fringe_intervals() dropping warmup rep 1: "
                f"{first.get('avg_power_w',0):.0f}W/{first.get('duration_s',0):.0f}s "
                f"vs median {med_p:.0f}W/{med_d:.0f}s"
            )
            intervals.pop(0)
            for i, iv in enumerate(intervals):
                iv['rep_number'] = i + 1
            for r in recoveries:
                if r.get('after_rep') == 1:
                    del r['after_rep']
                elif 'after_rep' in r:
                    r['after_rep'] -= 1
            return True
        return False

    def _drop_last(intervals, recoveries):
        med_p, med_d = _medians(intervals[:-1])
        last = intervals[-1]
        if _is_fringe(last, med_p, med_d):
            logger.info(
                f"_strip_fringe_intervals() dropping cooldown rep {len(intervals)}: "
                f"{last.get('avg_power_w',0):.0f}W/{last.get('duration_s',0):.0f}s "
                f"vs median {med_p:.0f}W/{med_d:.0f}s"
            )
            intervals.pop()
            return True
        return False

    if len(intervals) >= 3:
        _drop_first(intervals, recoveries)
    if len(intervals) >= 3:
        _drop_last(intervals, recoveries)


def _group_into_sets(intervals: list, recoveries: list, set_gap_s: int = 300) -> list:
    """Group by recovery.after_rep, never by the recovery list index.

    Leading/trailing recovery blocks do not belong to a work set.
    """
    if not intervals:
        return []
    gaps = {r.get('after_rep'): r for r in recoveries
            if isinstance(r.get('after_rep'), int)
            and 1 <= r['after_rep'] < len(intervals)}
    sets = []
    work = [intervals[0]]
    rests = []
    for rep in range(1, len(intervals)):
        recovery = gaps.get(rep)
        if recovery and recovery.get('duration_s', 0) >= set_gap_s:
            sets.append(_build_set(len(sets) + 1, work, rests))
            work, rests = [], []
        elif recovery:
            rests.append(recovery)
        work.append(intervals[rep])
    if work:
        sets.append(_build_set(len(sets) + 1, work, rests))
    return sets


def _build_set(set_number: int, intervals: list, recoveries: list) -> dict:
    set_max_hr    = max((iv.get('max_hr_bpm') or 0 for iv in intervals), default=None)
    set_max_power = max((iv.get('max_power_w') or 0 for iv in intervals), default=None)
    set_peak_cad  = max((iv.get('peak_cadence_rpm') or 0 for iv in intervals), default=None)
    return {
        'set_number':           set_number,
        'set_max_hr_bpm':       set_max_hr,
        'set_max_power_w':      set_max_power,
        'set_peak_cadence_rpm': set_peak_cad,
        'intervals':            intervals,
        'recoveries':           recoveries,
    }


def _detect_bimodal_power(power_data: list, time_data: list) -> dict:
    """Reference implementation — not currently used as a detection gate."""
    if not power_data or not time_data:
        return {'is_bimodal': False}
    start_t  = time_data[0]
    cutoff   = start_t + BIMODAL_WARMUP_STRIP_S
    filtered = [p for p, t in zip(power_data, time_data) if p is not None and p > 0 and t >= cutoff]
    if len(filtered) < 60:
        return {'is_bimodal': False}
    min_b   = int(min(filtered) // BIMODAL_BIN_W) * BIMODAL_BIN_W
    max_b   = int(max(filtered) // BIMODAL_BIN_W) * BIMODAL_BIN_W
    buckets = list(range(min_b, max_b + BIMODAL_BIN_W, BIMODAL_BIN_W))
    counts  = {b: 0 for b in buckets}
    for p in filtered:
        counts[int(p // BIMODAL_BIN_W) * BIMODAL_BIN_W] += 1
    hist     = [counts[b] for b in buckets]
    smoothed = [sum(hist[max(0, i-1): i+2]) / len(hist[max(0, i-1): i+2]) for i in range(len(hist))]
    peaks    = [(buckets[i], smoothed[i]) for i in range(1, len(smoothed) - 1)
                if smoothed[i] > smoothed[i-1] and smoothed[i] > smoothed[i+1]]
    if len(peaks) < 2:
        return {'is_bimodal': False, 'peaks_found': len(peaks)}
    top2        = sorted(peaks, key=lambda x: x[1], reverse=True)[:2]
    lower_peak, upper_peak = sorted(top2, key=lambda x: x[0])
    separation  = upper_peak[0] - lower_peak[0]
    if separation < BIMODAL_MIN_SEPARATION_W:
        return {'is_bimodal': False, 'lower_peak_w': lower_peak[0], 'upper_peak_w': upper_peak[0]}
    between     = [smoothed[i] for i, b in enumerate(buckets) if lower_peak[0] < b < upper_peak[0]]
    if not between:
        return {'is_bimodal': False}
    valley      = min(between)
    valley_depth = 1.0 - (valley / lower_peak[1]) if lower_peak[1] > 0 else 0.0
    return {
        'is_bimodal':        valley_depth >= BIMODAL_MIN_VALLEY_DEPTH,
        'lower_peak_w':      lower_peak[0],
        'upper_peak_w':      upper_peak[0],
        'peak_separation_w': separation,
        'valley_depth_pct':  round(valley_depth * 100, 1),
    }
