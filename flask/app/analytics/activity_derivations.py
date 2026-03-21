"""
Metric derivation from raw Strava activity stream data.

Functions here take raw power/HR/cadence streams or already-extracted
interval/recovery lists and compute derived metrics. No classification
or detection logic lives here.
"""

import json
import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================ #
# JSON serialisation helper                                                      #
# ============================================================================ #

class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'item'):
            return obj.item()
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        return super().default(obj)


# ============================================================================ #
# Snapshot frequency                                                             #
# ============================================================================ #

SHORT_INTERVAL_THRESHOLD_S     = 300
LONG_INTERVAL_THRESHOLD_S      = 1200
VERY_LONG_INTERVAL_THRESHOLD_S = 3600
ENDURANCE_INTERVAL_THRESHOLD_S = 7200

SHORT_SNAPSHOT_INTERVAL_S      = 15
MEDIUM_SNAPSHOT_INTERVAL_S     = 30
LONG_SNAPSHOT_INTERVAL_S       = 60
VERY_LONG_SNAPSHOT_INTERVAL_S  = 120
ENDURANCE_SNAPSHOT_INTERVAL_S  = 900

MIN_SNAPSHOTS_FOR_THIRDS = 6


def snapshot_interval_s(duration_s: int) -> int:
    """Return the appropriate snapshot bucket size for a given interval duration."""
    if duration_s < SHORT_INTERVAL_THRESHOLD_S:
        return SHORT_SNAPSHOT_INTERVAL_S
    elif duration_s < LONG_INTERVAL_THRESHOLD_S:
        return MEDIUM_SNAPSHOT_INTERVAL_S
    elif duration_s < VERY_LONG_INTERVAL_THRESHOLD_S:
        return LONG_SNAPSHOT_INTERVAL_S
    elif duration_s < ENDURANCE_INTERVAL_THRESHOLD_S:
        return VERY_LONG_SNAPSHOT_INTERVAL_S
    else:
        return ENDURANCE_SNAPSHOT_INTERVAL_S


# ============================================================================ #
# Per-interval metric extraction                                                 #
# ============================================================================ #

def compute_interval_metrics(
    block:       dict,
    power_data:  list,
    time_data:   list,
    hr_data:     list,
    cad_data:    list,
    max_power:   float,
    is_interval: bool,
) -> dict:
    """
    Derive metrics for a single interval or recovery block from raw streams.

    Args:
        block:       dict with start_idx, end_idx, duration_s
        power_data:  full-ride power stream
        time_data:   full-ride time stream
        hr_data:     full-ride HR stream
        cad_data:    full-ride cadence stream
        max_power:   ride-level max power (used for intensity_pct_of_max)
        is_interval: True for work intervals, False for recoveries

    Returns:
        dict with avg/max/norm power, HR, cadence, snapshots, within_interval_analysis
    """
    s = block['start_idx']
    e = block['end_idx'] + 1

    p_vals = [x for x in power_data[s:e] if x is not None]
    h_vals = [x for x in hr_data[s:e]    if x is not None]
    c_vals = [x for x in cad_data[s:e]   if x is not None]
    t_vals = time_data[s:e]

    result: dict = {
        'start_s':    time_data[block['start_idx']],
        'end_s':      time_data[block['end_idx']],
        'duration_s': block['duration_s'],
    }

    if p_vals:
        window = min(30, len(p_vals))
        np_val = round(float(
            (pd.Series(p_vals).rolling(window=window, min_periods=1).mean() ** 4).mean() ** 0.25
        ), 0)
        result['avg_power_w']  = round(sum(p_vals) / len(p_vals), 0)
        result['max_power_w']  = round(max(p_vals), 0)
        result['norm_power_w'] = np_val
        if is_interval and max_power:
            result['intensity_pct_of_max'] = round(max(p_vals) / max_power * 100, 1)

    if h_vals:
        result['avg_hr_bpm']    = round(sum(h_vals) / len(h_vals), 0)
        result['max_hr_bpm']    = round(max(h_vals), 0)
        result['hr_at_end_bpm'] = round(sum(h_vals[-3:]) / len(h_vals[-3:]), 0)

    if c_vals:
        result['avg_cadence_rpm']  = round(sum(c_vals) / len(c_vals), 0)
        result['peak_cadence_rpm'] = round(max(c_vals), 0)

    if is_interval and t_vals:
        snap_s       = snapshot_interval_s(block['duration_s'])
        start_t      = t_vals[0]
        end_t        = t_vals[-1]
        snapshots    = []
        bucket_start = start_t
        while bucket_start < end_t:
            bucket_end = bucket_start + snap_s
            bp, bh, bc = [], [], []
            for idx, t in enumerate(t_vals):
                if bucket_start <= t < bucket_end:
                    if idx < len(p_vals) and p_vals[idx] is not None:
                        bp.append(p_vals[idx])
                    if idx < len(h_vals) and h_vals[idx] is not None:
                        bh.append(h_vals[idx])
                    if idx < len(c_vals) and c_vals[idx] is not None:
                        bc.append(c_vals[idx])
            if bp or bh or bc:
                snap: dict = {'t_s': int(bucket_start - start_t)}
                if bp: snap['avg_power_w'] = round(sum(bp) / len(bp), 0)
                if bh: snap['hr_bpm']      = round(sum(bh) / len(bh), 0)
                if bc: snap['cadence_rpm'] = round(sum(bc) / len(bc), 0)
                snapshots.append(snap)
            bucket_start = bucket_end
        result['snapshots'] = snapshots

        if len(snapshots) >= MIN_SNAPSHOTS_FOR_THIRDS:
            third = len(snapshots) // 3
            first = snapshots[:third]
            last  = snapshots[-third:]

            def _avg_field(snaps, field):
                vals = [s[field] for s in snaps if field in s]
                return round(sum(vals) / len(vals), 0) if vals else None

            def _hr_lag(h_vals_local, t_vals_local, max_hr_bpm):
                if not h_vals_local or not max_hr_bpm:
                    return None
                target = max_hr_bpm * 0.90
                start  = t_vals_local[0]
                for t, h in zip(t_vals_local, h_vals_local):
                    if h >= target:
                        return int(t - start)
                return None

            def _cadence_drop_pct(c_vals_local, avg_cad):
                if not c_vals_local or not avg_cad:
                    return None
                for i, c in enumerate(c_vals_local):
                    if c < avg_cad:
                        return round(i / len(c_vals_local) * 100, 0)
                return None

            result['within_interval_analysis'] = {
                'power_first_third':   _avg_field(first, 'avg_power_w'),
                'power_last_third':    _avg_field(last,  'avg_power_w'),
                'hr_first_third':      _avg_field(first, 'hr_bpm'),
                'hr_last_third':       _avg_field(last,  'hr_bpm'),
                'cadence_first_third': _avg_field(first, 'cadence_rpm'),
                'cadence_last_third':  _avg_field(last,  'cadence_rpm'),
                'hr_lag_s':            _hr_lag(h_vals, t_vals, result.get('max_hr_bpm')),
                'cadence_drop_pct':    _cadence_drop_pct(c_vals, result.get('avg_cadence_rpm')),
            }

    return result


# ============================================================================ #
# Cross-rep summary                                                              #
# ============================================================================ #

def compute_interval_summary(intervals: list, recoveries: list) -> dict:
    """
    Aggregate per-rep metrics across all intervals and recoveries.

    Args:
        intervals:   list of interval dicts (from compute_interval_metrics)
        recoveries:  list of recovery dicts (from compute_interval_metrics)

    Returns:
        dict with avg/max/decay fields across the session
    """
    if not intervals:
        return {}

    powers    = [iv.get('avg_power_w',      0) for iv in intervals]
    max_pows  = [iv.get('max_power_w',      0) for iv in intervals]
    cadences  = [iv.get('avg_cadence_rpm',  0) for iv in intervals]
    peak_cads = [iv.get('peak_cadence_rpm', 0) for iv in intervals]
    hr_avgs   = [iv.get('avg_hr_bpm')          for iv in intervals]
    hr_maxes  = [iv.get('max_hr_bpm')          for iv in intervals]
    durations = [iv.get('duration_s',       0) for iv in intervals]
    rest_durs = [r.get('duration_s',        0) for r in recoveries]

    valid_max_pows  = [x for x in max_pows  if x is not None]
    valid_hr_maxes  = [x for x in hr_maxes  if x is not None]
    valid_peak_cads = [x for x in peak_cads if x is not None]

    summary: dict = {
        'avg_interval_duration_s':  round(sum(durations) / len(durations), 0),
        'avg_interval_power_w':     round(sum(powers) / len(powers), 0),
        'session_max_power_w':      max(valid_max_pows)  if valid_max_pows  else None,
        'power_decay_w':            round(powers[-1] - powers[0], 0)     if len(powers) > 1    else 0,
        'cadence_decay_rpm':        round(cadences[-1] - cadences[0], 0) if len(cadences) > 1  else 0,
        'avg_hr_progression':       hr_avgs,
        'max_hr_progression':       hr_maxes,
        'avg_cadence_progression':  cadences,
        'peak_cadence_progression': peak_cads,
        'session_max_hr_bpm':       max(valid_hr_maxes)  if valid_hr_maxes  else None,
        'session_peak_cadence_rpm': max(valid_peak_cads) if valid_peak_cads else None,
    }

    if rest_durs:
        total_rest = sum(rest_durs)
        summary['avg_rest_duration_s'] = round(total_rest / len(rest_durs), 0)
        summary['work_to_rest_ratio']  = round(sum(durations) / total_rest, 2) if total_rest > 0 else None
    else:
        summary['avg_rest_duration_s'] = None
        summary['work_to_rest_ratio']  = None

    return summary


# ============================================================================ #
# Advanced metrics                                                               #
# ============================================================================ #

# Power pacing thresholds (decay as % of avg interval power)
POWER_PACING_VERY_STEADY_PCT = 3
POWER_PACING_STEADY_PCT      = 6
POWER_PACING_FADING_PCT      = 12

# Flag thresholds
POWER_FADE_FLAG_PCT          = 8    # power_decay as % of avg — beyond this is a flag
CADENCE_COLLAPSE_RPM         = 5    # absolute cadence drop in rpm
HR_RESPONSE_MIN_PCT          = 85   # session max HR must reach this % of max to count as adequate

# Trend detection: % change between first and last third of a progression list
TREND_RISING_PCT             = 3
TREND_DECLINING_PCT          = -3

# Recovery HR drop thresholds (interval end HR minus recovery avg HR)
RECOVERY_DROP_FAST_BPM       = 20
RECOVERY_DROP_ADEQUATE_BPM   = 10

# Benefit lookup by workout_type → interval_type
_BENEFIT_LOOKUP = {
    ('vo2',       'type_ii'): ('VO2max stimulus',        'aerobic power and repeatability'),
    ('vo2',       'type_i'):  ('VO2max stimulus',        'aerobic capacity'),
    ('vo2',       None):      ('VO2max stimulus',        'aerobic power'),
    ('threshold', 'type_i'):  ('FTP development',        'lactate threshold adaptation'),
    ('threshold', 'type_ii'): ('lactate threshold',      'high-intensity repeatability'),
    ('threshold', None):      ('FTP development',        'lactate threshold adaptation'),
    ('tempo',     None):      ('lactate clearance',      'aerobic efficiency'),
    ('endurance', None):      ('aerobic base development', 'fat oxidation'),
}


def _progression_trend(values: list) -> str:
    """Return 'rising', 'stable', or 'declining' for a list of per-rep values."""
    valid = [v for v in (values or []) if v is not None]
    if len(valid) < 2:
        return 'stable'
    third     = max(1, len(valid) // 3)
    first_avg = sum(valid[:third]) / third
    last_avg  = sum(valid[-third:]) / third
    if first_avg == 0:
        return 'stable'
    pct = (last_avg - first_avg) / first_avg * 100
    if pct > TREND_RISING_PCT:
        return 'rising'
    if pct < TREND_DECLINING_PCT:
        return 'declining'
    return 'stable'


def compute_advanced_metrics(
    intervals:      list,
    recoveries:     list,
    summary:        dict,
    workout_type:   str,
    interval_type:  str,
    ftp:            float,
    max_hr:         float,
) -> dict:
    """
    Derive higher-level metrics from interval summary + athlete thresholds.

    Args:
        intervals:     per-rep interval dicts (from compute_interval_metrics)
        recoveries:    per-rep recovery dicts
        summary:       output of compute_interval_summary
        workout_type:  e.g. 'vo2', 'threshold', 'tempo', 'endurance'
        interval_type: e.g. 'type_i', 'type_ii', or None
        ftp:           athlete FTP in watts
        max_hr:        athlete max HR in bpm

    Returns:
        dict with execution_summary, benefit_assessment, flags
    """
    avg_power   = summary.get('avg_interval_power_w', 0)
    power_decay = summary.get('power_decay_w', 0)           # last - first rep (negative = fade)
    cad_decay   = summary.get('cadence_decay_rpm', 0)
    max_hr_sess = summary.get('session_max_hr_bpm')

    # --- execution_summary ---------------------------------------------------

    # Power pacing label from decay magnitude
    if avg_power and avg_power > 0:
        decay_pct = abs(power_decay) / avg_power * 100
    else:
        decay_pct = 0

    if power_decay >= 0 or decay_pct < POWER_PACING_VERY_STEADY_PCT:
        power_pacing = 'very steady'
    elif decay_pct < POWER_PACING_STEADY_PCT:
        power_pacing = 'steady'
    elif decay_pct < POWER_PACING_FADING_PCT:
        power_pacing = 'fading'
    else:
        power_pacing = 'significant fade'

    # HR progression label
    hr_trend = _progression_trend(summary.get('avg_hr_progression', []))
    hr_progression_label = {
        'rising':   'progressive rise across reps',
        'stable':   'stable',
        'declining': 'peaked early',
    }[hr_trend]

    # Cadence trend label
    cad_trend = _progression_trend(summary.get('avg_cadence_progression', []))
    cadence_trend_label = {
        'rising':    'stable to slightly improving',
        'stable':    'stable',
        'declining': 'declining',
    }[cad_trend]

    # Recovery power: avg of inter-rep recovery blocks
    inter_rep_recoveries = [r for r in recoveries if 'after_rep' in r]
    rec_powers = [r.get('avg_power_w', 0) for r in inter_rep_recoveries if r.get('avg_power_w')]
    recovery_power_w = round(sum(rec_powers) / len(rec_powers), 0) if rec_powers else None

    # Recovery HR drop: avg(interval hr_at_end_bpm) - avg(recovery avg_hr_bpm)
    interval_end_hrs = [iv.get('hr_at_end_bpm') for iv in intervals if iv.get('hr_at_end_bpm')]
    rec_avg_hrs      = [r.get('avg_hr_bpm')     for r in inter_rep_recoveries if r.get('avg_hr_bpm')]
    if interval_end_hrs and rec_avg_hrs:
        avg_end_hr = sum(interval_end_hrs) / len(interval_end_hrs)
        avg_rec_hr = sum(rec_avg_hrs) / len(rec_avg_hrs)
        hr_drop    = avg_end_hr - avg_rec_hr
        if hr_drop >= RECOVERY_DROP_FAST_BPM:
            recovery_hr_drop = 'fast'
        elif hr_drop >= RECOVERY_DROP_ADEQUATE_BPM:
            recovery_hr_drop = 'adequate'
        else:
            recovery_hr_drop = 'slow'
    else:
        recovery_hr_drop = None

    # Max HR % of athlete max
    session_max_hr_pct = round(max_hr_sess / max_hr * 100, 1) if (max_hr_sess and max_hr) else None

    execution_summary = {
        'interval_count':             len(intervals),
        'avg_interval_duration_s':    summary.get('avg_interval_duration_s'),
        'avg_interval_power_w':       avg_power,
        'avg_interval_power_pct_ftp': round(avg_power / ftp * 100, 1) if (avg_power and ftp) else None,
        'power_pacing':               power_pacing,
        'power_decay_w':              power_decay,
        'session_max_power_w':        summary.get('session_max_power_w'),
        'session_max_hr_bpm':         max_hr_sess,
        'session_max_hr_pct':         session_max_hr_pct,
        'hr_progression':             hr_progression_label,
        'avg_end_hr_bpm_last_rep':    intervals[-1].get('hr_at_end_bpm') if intervals else None,
        'cadence_trend':              cadence_trend_label,
        'cadence_decay_rpm':          cad_decay,
        'recovery_power_w':           recovery_power_w,
        'recovery_hr_drop_pattern':   recovery_hr_drop,
        'work_to_rest_ratio':         summary.get('work_to_rest_ratio'),
    }

    # --- flags ----------------------------------------------------------------

    power_fade_flag      = decay_pct > POWER_FADE_FLAG_PCT and power_decay < 0
    cadence_collapse_flag = cad_decay < -CADENCE_COLLAPSE_RPM
    insufficient_hr_flag = (session_max_hr_pct is not None
                            and session_max_hr_pct < HR_RESPONSE_MIN_PCT
                            and workout_type in ('vo2', 'threshold'))

    # Late fatigue: last 2 reps both show power AND cadence below session avg
    late_fatigue_flag = False
    if len(intervals) >= 3:
        last_two = intervals[-2:]
        avg_cad  = summary.get('avg_cadence_progression')
        session_avg_cad = (sum(avg_cad) / len(avg_cad)) if avg_cad else None
        if all(
            iv.get('avg_power_w', avg_power) < avg_power
            and (session_avg_cad is None or iv.get('avg_cadence_rpm', session_avg_cad) < session_avg_cad)
            for iv in last_two
        ):
            late_fatigue_flag = True

    completed_as_intended = not power_fade_flag and not cadence_collapse_flag

    flags = {
        'completed_as_intended':          completed_as_intended,
        'power_fade_flag':                power_fade_flag,
        'cadence_collapse_flag':          cadence_collapse_flag,
        'insufficient_hr_response_flag':  insufficient_hr_flag,
        'late_fatigue_flag':              late_fatigue_flag,
    }

    # --- benefit_assessment ---------------------------------------------------

    key = (workout_type, interval_type)
    primary, secondary = _BENEFIT_LOOKUP.get(key) or _BENEFIT_LOOKUP.get((workout_type, None), ('aerobic development', 'fitness'))

    limiting_parts = []
    if hr_trend == 'rising':
        limiting_parts.append('cardiovascular strain rose progressively but remained controlled')
    if power_fade_flag:
        limiting_parts.append('power output declined across reps')
    if cadence_collapse_flag:
        limiting_parts.append('neuromuscular fatigue evident in cadence')
    if insufficient_hr_flag:
        limiting_parts.append('HR response was lower than expected for this intensity')
    limiting_factor = '; '.join(limiting_parts) if limiting_parts else 'none identified'

    benefit_assessment = {
        'primary_benefit':   primary,
        'secondary_benefit': secondary,
        'limiting_factor':   limiting_factor,
    }

    return {
        'execution_summary':  execution_summary,
        'benefit_assessment': benefit_assessment,
        'flags':              flags,
    }
