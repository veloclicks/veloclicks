import json
import logging
import os
from typing import Optional

import pandas as pd

from app.strava.streams import get_activity_streams, get_activity_laps


# ========================================================================== #
# JSON serialisation                                                           #
# ========================================================================== #

class _NumpyEncoder(json.JSONEncoder):
    """
    JSON encoder that handles numpy scalar types (int64, float64, etc.)
    which are not natively serialisable by the standard library encoder.
    """
    def default(self, obj):
        if hasattr(obj, 'item'):
            return obj.item()
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        return super().default(obj)


# ========================================================================== #
# Within-interval snapshot configuration                                       #
# ========================================================================== #

# Duration band thresholds (seconds)
SHORT_INTERVAL_THRESHOLD_S     = 300    # 5 min
LONG_INTERVAL_THRESHOLD_S      = 1200   # 20 min
VERY_LONG_INTERVAL_THRESHOLD_S = 3600   # 1 hr
ENDURANCE_INTERVAL_THRESHOLD_S = 7200   # 2 hr

# Snapshot frequency per band
SHORT_SNAPSHOT_INTERVAL_S      = 15
MEDIUM_SNAPSHOT_INTERVAL_S     = 30
LONG_SNAPSHOT_INTERVAL_S       = 60
VERY_LONG_SNAPSHOT_INTERVAL_S  = 120    # 2 min
ENDURANCE_SNAPSHOT_INTERVAL_S  = 900    # 15 min

# Minimum snapshots required to compute first/last third derived signals
MIN_SNAPSHOTS_FOR_THIRDS = 6


def _snapshot_interval_s(duration_s: int) -> int:
    """Return appropriate snapshot frequency for a given interval duration."""
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


# ========================================================================== #
# Interval session detection constants                                         #
# ========================================================================== #

MIN_INTERVAL_DURATION_S         = 90
MIN_INTERVAL_COUNT              = 3
MIN_AVG_INTERVAL_DURATION_S     = 60
MAX_DURATION_CV                 = 0.50
MIN_WORK_REST_RATIO             = 0.20


# ========================================================================== #
# File output helper                                                           #
# ========================================================================== #

def _write_json_to_file(json_str: str, activity_id: str, output_dir: str) -> None:
    """
    Write a JSON string to <output_dir>/<activity_id>.json.
    Creates the directory if it does not exist.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"{activity_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logging.info(f"_write_json_to_file() written to {filepath}")
    except Exception as e:
        logging.error(f"_write_json_to_file() failed to write {activity_id}.json: {e}")


# ========================================================================== #
# Endurance / long ride report                                                 #
# ========================================================================== #

def generate_activity_report(user_id: str, activity_id: str) -> Optional[pd.DataFrame]:
    """
    Generate a 15-minute interval performance report for a Strava activity.

    Fetches all key streams and aggregates into snapshot intervals suitable
    for pasting into an LLM for ride analysis.

    Args:
        user_id:     User ID for authentication
        activity_id: Strava activity ID

    Returns:
        DataFrame with one row per 15-minute interval, or None if streams unavailable.
    """
    logging.info(f"generate_activity_report() for user {user_id}, activity {activity_id}")

    stream_types = [
        'time', 'distance', 'altitude', 'velocity_smooth',
        'heartrate', 'cadence', 'watts', 'grade_smooth'
    ]

    streams = get_activity_streams(user_id, activity_id, stream_types=stream_types)
    if not streams:
        logging.error("generate_activity_report() failed to retrieve streams")
        return None

    time_data = streams.get('time', {}).get('data')
    if not time_data:
        logging.error("generate_activity_report() time stream missing - cannot build report")
        return None

    df = pd.DataFrame({'elapsed_s': time_data})

    stream_map = {
        'distance':        ('distance_m',   'distance'),
        'velocity_smooth': ('speed_ms',     'velocity_smooth'),
        'heartrate':       ('hr_bpm',       'heartrate'),
        'cadence':         ('cadence_rpm',  'cadence'),
        'watts':           ('power_w',      'watts'),
        'grade_smooth':    ('gradient_pct', 'grade_smooth'),
        'altitude':        ('altitude_m',   'altitude'),
    }

    for _, (df_col, stream_key) in stream_map.items():
        if stream_key in streams:
            df[df_col] = streams[stream_key]['data']
        else:
            logging.warning(
                f"generate_activity_report() stream '{stream_key}' not available - column will be NaN"
            )
            df[df_col] = float('nan')

    df['speed_kph'] = df['speed_ms'] * 3.6

    if df['power_w'].notna().any():
        max_s = int(df['elapsed_s'].max())
        df_1s = (
            df[['elapsed_s', 'power_w']]
            .set_index('elapsed_s')
            .reindex(range(max_s + 1))
            .interpolate(method='index')
        )
        df_1s['power_w_np'] = df_1s['power_w'].rolling(window=30, min_periods=1).mean()
        df = df.merge(df_1s[['power_w_np']].reset_index(), on='elapsed_s', how='left')
    else:
        df['power_w_np'] = float('nan')

    interval_seconds = 15 * 60
    df['interval_idx'] = (df['elapsed_s'] // interval_seconds).astype(int)

    def norm_power(series: pd.Series) -> float:
        valid = series.dropna()
        if valid.empty:
            return float('nan')
        return (valid ** 4).mean() ** 0.25

    agg = df.groupby('interval_idx').agg(
        avg_power_w     =('power_w',       'mean'),
        norm_power_w    =('power_w_np',    norm_power),
        avg_hr_bpm      =('hr_bpm',        'mean'),
        max_hr_bpm      =('hr_bpm',        'max'),
        avg_cadence_rpm =('cadence_rpm',   'mean'),
        avg_speed_kph   =('speed_kph',     'mean'),
        avg_gradient_pct=('gradient_pct',  'mean'),
        elapsed_start_s =('elapsed_s',     'min'),
    ).reset_index()

    if df['distance_m'].notna().any():
        dist = df.groupby('interval_idx')['distance_m'].agg(['min', 'max'])
        agg['distance_km'] = ((dist['max'] - dist['min']) / 1000).values
    else:
        agg['distance_km'] = float('nan')

    if df['altitude_m'].notna().any():
        def elevation_gain(altitudes: pd.Series) -> float:
            deltas = altitudes.diff().dropna()
            return deltas[deltas > 0].sum()
        elev = df.groupby('interval_idx', group_keys=False)['altitude_m'].apply(elevation_gain)
        agg['elevation_gain_m'] = elev.values
    else:
        agg['elevation_gain_m'] = float('nan')

    def fmt_interval(start_s: float) -> str:
        start_min = int(start_s // 60)
        end_min   = start_min + 15
        return f"{start_min // 60}:{start_min % 60:02d}-{end_min // 60}:{end_min % 60:02d}"

    agg['interval']    = agg['elapsed_start_s'].apply(fmt_interval)
    agg['elapsed_min'] = (agg['elapsed_start_s'] // 60).astype(int)

    round_map = {
        'avg_power_w': 0, 'norm_power_w': 0, 'avg_hr_bpm': 0, 'max_hr_bpm': 0,
        'avg_cadence_rpm': 0, 'avg_speed_kph': 1, 'avg_gradient_pct': 1,
        'distance_km': 2, 'elevation_gain_m': 0,
    }
    for col, decimals in round_map.items():
        if col in agg.columns:
            agg[col] = agg[col].round(decimals)

    cols = [
        'interval', 'elapsed_min', 'distance_km',
        'avg_power_w', 'norm_power_w',
        'avg_hr_bpm', 'max_hr_bpm',
        'avg_cadence_rpm', 'avg_speed_kph',
        'avg_gradient_pct', 'elevation_gain_m',
    ]

    result = agg[cols].copy()
    logging.info(f"generate_activity_report() generated {len(result)} intervals")
    return result


def report_to_json(
    df: pd.DataFrame,
    activity_id: Optional[str] = None,
    pretty: bool = True
) -> str:
    """Serialise an activity report DataFrame to a JSON string."""
    if df is None or df.empty:
        logging.warning("report_to_json() received empty or None DataFrame")
        return ""

    def _whole_ride_np(np_series: pd.Series) -> Optional[float]:
        valid = np_series.dropna()
        if valid.empty:
            return None
        return round(float((valid ** 4).mean() ** 0.25), 0)

    def _safe(val):
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        return val

    intervals = [
        {k: _safe(v) for k, v in row.items()}
        for row in df.to_dict(orient='records')
    ]

    def _col_mean(col, decimals=0):
        if col not in df.columns or df[col].isna().all():
            return None
        return round(float(df[col].mean()), decimals)

    def _col_sum(col, decimals=0):
        if col not in df.columns or df[col].isna().all():
            return None
        return round(float(df[col].sum()), decimals)

    def _col_max(col, decimals=0):
        if col not in df.columns or df[col].isna().all():
            return None
        return round(float(df[col].max()), decimals)

    summary = {
        'total_distance_km':      _col_sum('distance_km', decimals=2),
        'total_elevation_gain_m': _col_sum('elevation_gain_m'),
        'avg_power_w':            _col_mean('avg_power_w'),
        'norm_power_w':           _whole_ride_np(df['norm_power_w']),
        'avg_hr_bpm':             _col_mean('avg_hr_bpm'),
        'max_hr_bpm':             _col_max('max_hr_bpm'),
        'avg_cadence_rpm':        _col_mean('avg_cadence_rpm'),
        'avg_speed_kph':          _col_mean('avg_speed_kph', decimals=1),
    }

    payload = {
        **({"activity_id": str(activity_id)} if activity_id is not None else {}),
        "interval_count": len(df),
        "intervals":      intervals,
        "summary":        summary,
    }

    indent = 2 if pretty else None
    return json.dumps(payload, indent=indent, cls=_NumpyEncoder)


def generate_activity_report_json(
    user_id: str,
    activity_id: str,
    pretty: bool = True,
    output_dir: Optional[str] = None,
) -> str:
    """
    Convenience wrapper: fetch streams, build report, return JSON in one call.

    Args:
        user_id:     User ID for authentication
        activity_id: Strava activity ID
        pretty:      Pretty-print JSON if True
        output_dir:  If provided, writes <activity_id>.json to this directory

    Returns:
        JSON string, or empty string on failure
    """
    df = generate_activity_report(user_id, activity_id)
    if df is None:
        return ""
    result = report_to_json(df, activity_id=activity_id, pretty=pretty)
    if result and output_dir:
        _write_json_to_file(result, activity_id, output_dir)
    return result


# ========================================================================== #
# Interval session detection and characterisation                              #
# ========================================================================== #

def analyse_session_structure(
    user_id: str,
    activity_id: str,
    pretty: bool = True,
    output_dir: Optional[str] = None,
) -> str:
    """
    Analyse whether an activity is a structured interval session and,
    if so, characterise the interval structure. Returns JSON string.

    Args:
        user_id:     User ID for authentication
        activity_id: Strava activity ID
        pretty:      Pretty-print JSON if True
        output_dir:  If provided, writes <activity_id>.json to this directory

    Returns:
        JSON string
    """
    logging.info(f"analyse_session_structure() for user {user_id}, activity {activity_id}")

    result: dict = {"activity_id": str(activity_id)}

    # Step 1: try laps first
    laps = get_activity_laps(user_id, activity_id)
    if laps and _laps_look_like_intervals(laps):
        logging.info("analyse_session_structure() using lap-based detection")
        result.update(_structure_from_laps(laps))
        indent = 2 if pretty else None
        json_str = json.dumps(result, indent=indent, cls=_NumpyEncoder)
        if output_dir:
            _write_json_to_file(json_str, activity_id, output_dir)
        return json_str

    # Step 2: fall back to power stream detection
    logging.info("analyse_session_structure() falling back to power stream detection")
    streams = get_activity_streams(
        user_id, activity_id,
        stream_types=['time', 'watts', 'heartrate', 'cadence']
    )

    if not streams or 'watts' not in streams:
        logging.warning("analyse_session_structure() no power stream available")
        result.update({
            "is_interval_session": False,
            "confidence":          "low",
            "detection_method":    "none",
        })
        indent = 2 if pretty else None
        json_str = json.dumps(result, indent=indent, cls=_NumpyEncoder)
        if output_dir:
            _write_json_to_file(json_str, activity_id, output_dir)
        return json_str

    result.update(_structure_from_power_stream(streams))
    indent = 2 if pretty else None
    json_str = json.dumps(result, indent=indent, cls=_NumpyEncoder)
    if output_dir:
        _write_json_to_file(json_str, activity_id, output_dir)
    return json_str


def _laps_look_like_intervals(laps: list) -> bool:
    if len(laps) < 4:
        return False
    powers    = [lap.get('average_watts', 0) for lap in laps]
    durations = [lap.get('elapsed_time', 0)  for lap in laps]
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
    if not laps:
        return {"is_interval_session": False, "confidence": "low", "detection_method": "laps"}
    powers    = [lap.get('average_watts', 0) for lap in laps]
    max_power = max(powers) if powers else 1
    threshold = max_power * 0.75
    intervals:  list = []
    recoveries: list = []
    rep_num = 1
    for lap in laps:
        avg_w = lap.get('average_watts', 0)
        entry = {
            'duration_s':      lap.get('elapsed_time', 0),
            'avg_power_w':     round(float(avg_w), 0),
            'max_power_w':     round(float(lap.get('max_watts', avg_w)), 0),
            'avg_hr_bpm':      round(float(lap.get('average_heartrate', 0)), 0),
            'max_hr_bpm':      round(float(lap.get('max_heartrate', 0)), 0),
            'avg_cadence_rpm': round(float(lap.get('average_cadence', 0)), 0),
        }
        if avg_w >= threshold:
            entry['rep_number']           = rep_num
            entry['intensity_pct_of_max'] = round(avg_w / max_power * 100, 1)
            intervals.append(entry)
            rep_num += 1
        else:
            if intervals:
                entry['after_rep'] = len(intervals)
            recoveries.append(entry)
    sets    = _group_into_sets(intervals, recoveries, set_gap_s=300)
    summary = _compute_summary(intervals, recoveries)
    return {
        "is_interval_session": True,
        "confidence":          "high",
        "detection_method":    "laps",
        "interval_count":      len(intervals),
        "sets":                sets,
        "summary":             summary,
    }


def _structure_from_power_stream(streams: dict) -> dict:
    power_data = streams['watts']['data']
    time_data  = streams['time']['data']
    hr_data    = streams.get('heartrate', {}).get('data', [None] * len(time_data))
    cad_data   = streams.get('cadence',   {}).get('data', [None] * len(time_data))

    sorted_power = sorted(p for p in power_data if p is not None)
    if not sorted_power:
        return {"is_interval_session": False, "confidence": "low", "detection_method": "power_stream"}

    p95       = sorted_power[int(len(sorted_power) * 0.95)]
    threshold = p95 * 0.80

    intervals, recoveries = _detect_intervals_and_recoveries(
        power_data, time_data, hr_data, cad_data, threshold,
        min_duration_s=MIN_INTERVAL_DURATION_S
    )

    reason = _validate_interval_session(intervals, recoveries)
    if reason:
        logging.info(f"analyse_session_structure() not a structured session: {reason}")
        return {
            "is_interval_session":      False,
            "confidence":               "high",
            "detection_method":         "power_stream",
            "rejection_reason":         reason,
            "candidate_interval_count": len(intervals),
        }

    sets    = _group_into_sets(intervals, recoveries, set_gap_s=300)
    summary = _compute_summary(intervals, recoveries)

    return {
        "is_interval_session": True,
        "confidence":          "high" if len(intervals) >= 4 else "medium",
        "detection_method":    "power_stream",
        "interval_count":      len(intervals),
        "sets":                sets,
        "summary":             summary,
    }


def _validate_interval_session(intervals: list, recoveries: list) -> Optional[str]:
    if len(intervals) < MIN_INTERVAL_COUNT:
        return f"only {len(intervals)} intervals detected (minimum {MIN_INTERVAL_COUNT})"
    durations = [iv.get('duration_s', 0) for iv in intervals]
    avg_dur   = sum(durations) / len(durations)
    if avg_dur < MIN_AVG_INTERVAL_DURATION_S:
        return (
            f"avg interval duration {avg_dur:.0f}s is below minimum "
            f"{MIN_AVG_INTERVAL_DURATION_S}s — likely terrain surges not structured intervals"
        )
    if len(durations) > 1:
        mean_d = avg_dur
        std_d  = (sum((d - mean_d) ** 2 for d in durations) / len(durations)) ** 0.5
        cv     = std_d / mean_d if mean_d > 0 else 1.0
        if cv > MAX_DURATION_CV:
            return (
                f"interval durations too inconsistent (CV={cv:.2f}, max={MAX_DURATION_CV}) "
                f"— likely unstructured ride"
            )
    rest_durs  = [r.get('duration_s', 0) for r in recoveries]
    total_work = sum(durations)
    total_rest = sum(rest_durs)
    if total_rest > 0:
        wtr = total_work / total_rest
        if wtr < MIN_WORK_REST_RATIO:
            return (
                f"work-to-rest ratio {wtr:.2f} below minimum {MIN_WORK_REST_RATIO} "
                f"— too little structured work relative to ride duration"
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
        blocks.append({
            'state':      'on' if state else 'off',
            'start_idx':  i,
            'end_idx':    j - 1,
            'duration_s': duration,
        })
        i = j

    merged: list = []
    for block in blocks:
        if (merged
                and block['state'] == 'off'
                and block['duration_s'] <= merge_gap_s
                and merged[-1]['state'] == 'on'):
            merged[-1]['end_idx']    = block['end_idx']
            merged[-1]['duration_s'] += block['duration_s']
        else:
            merged.append(block)

    merged = [
        b for b in merged
        if b['state'] == 'off' or b['duration_s'] >= min_duration_s
    ]

    def _metrics(block: dict, is_interval: bool) -> dict:
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
            np_val = round(
                float(
                    (pd.Series(p_vals)
                     .rolling(window=window, min_periods=1)
                     .mean() ** 4
                    ).mean() ** 0.25
                ), 0
            )
            result['avg_power_w']  = round(sum(p_vals) / len(p_vals), 0)
            result['max_power_w']  = round(max(p_vals), 0)
            result['norm_power_w'] = np_val
            if is_interval:
                result['intensity_pct_of_max'] = round(max(p_vals) / max_power * 100, 1)

        if h_vals:
            result['avg_hr_bpm']    = round(sum(h_vals) / len(h_vals), 0)
            result['max_hr_bpm']    = round(max(h_vals), 0)
            result['hr_at_end_bpm'] = round(sum(h_vals[-3:]) / len(h_vals[-3:]), 0)

        if c_vals:
            result['avg_cadence_rpm']  = round(sum(c_vals) / len(c_vals), 0)
            result['peak_cadence_rpm'] = round(max(c_vals), 0)

        # ------------------------------------------------------------------ #
        # Within-interval snapshots (intervals only)                          #
        # ------------------------------------------------------------------ #
        if is_interval and t_vals:
            snap_s      = _snapshot_interval_s(block['duration_s'])
            start_t     = t_vals[0]
            end_t       = t_vals[-1]
            snapshots   = []

            bucket_start = start_t
            while bucket_start < end_t:
                bucket_end = bucket_start + snap_s

                # Collect samples in this bucket
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
                    if bp:
                        snap['avg_power_w']   = round(sum(bp) / len(bp), 0)
                    if bh:
                        snap['hr_bpm']        = round(sum(bh) / len(bh), 0)
                    if bc:
                        snap['cadence_rpm']   = round(sum(bc) / len(bc), 0)
                    snapshots.append(snap)

                bucket_start = bucket_end

            result['snapshots'] = snapshots

            # ------------------------------------------------------------------ #
            # Derived signals from snapshots (first/last third comparison)        #
            # ------------------------------------------------------------------ #
            if len(snapshots) >= MIN_SNAPSHOTS_FOR_THIRDS:
                third = len(snapshots) // 3
                first = snapshots[:third]
                last  = snapshots[-third:]

                def _avg_field(snaps, field):
                    vals = [s[field] for s in snaps if field in s]
                    return round(sum(vals) / len(vals), 0) if vals else None

                def _hr_lag(h_vals_local, t_vals_local, max_hr):
                    """Seconds until HR first crosses 90% of rep max HR."""
                    if not h_vals_local or not max_hr:
                        return None
                    target = max_hr * 0.90
                    start  = t_vals_local[0]
                    for t, h in zip(t_vals_local, h_vals_local):
                        if h >= target:
                            return int(t - start)
                    return None

                def _cadence_drop_pct(c_vals_local, avg_cad):
                    """
                    Percentage through the rep when cadence first fell
                    below the rep average. None if it never dropped.
                    """
                    if not c_vals_local or not avg_cad:
                        return None
                    for i, c in enumerate(c_vals_local):
                        if c < avg_cad:
                            return round(i / len(c_vals_local) * 100, 0)
                    return None

                rep_avg_cad = result.get('avg_cadence_rpm')
                rep_max_hr  = result.get('max_hr_bpm')

                result['within_interval_analysis'] = {
                    'power_first_third':    _avg_field(first, 'avg_power_w'),
                    'power_last_third':     _avg_field(last,  'avg_power_w'),
                    'hr_first_third':       _avg_field(first, 'hr_bpm'),
                    'hr_last_third':        _avg_field(last,  'hr_bpm'),
                    'cadence_first_third':  _avg_field(first, 'cadence_rpm'),
                    'cadence_last_third':   _avg_field(last,  'cadence_rpm'),
                    'hr_lag_s':             _hr_lag(h_vals, t_vals, rep_max_hr),
                    'cadence_drop_pct':     _cadence_drop_pct(c_vals, rep_avg_cad),
                }

        return result

    intervals:  list = []
    recoveries: list = []
    rep_num = 1

    for block in merged:
        if block['state'] == 'on':
            m = _metrics(block, is_interval=True)
            m['rep_number'] = rep_num
            intervals.append(m)
            rep_num += 1
        else:
            m = _metrics(block, is_interval=False)
            if intervals:
                m['after_rep'] = len(intervals)
            recoveries.append(m)

    return intervals, recoveries


def _group_into_sets(intervals: list, recoveries: list, set_gap_s: int = 300) -> list:
    if not intervals:
        return []
    sets:               list = []
    current_intervals:  list = [intervals[0]]
    current_recoveries: list = []
    for i, recovery in enumerate(recoveries):
        if recovery['duration_s'] >= set_gap_s:
            sets.append(_build_set(len(sets) + 1, current_intervals, current_recoveries))
            current_intervals  = [intervals[i + 1]] if i + 1 < len(intervals) else []
            current_recoveries = []
        else:
            current_recoveries.append(recovery)
            if i + 1 < len(intervals):
                current_intervals.append(intervals[i + 1])
    if current_intervals:
        sets.append(_build_set(len(sets) + 1, current_intervals, current_recoveries))
    return sets


def _build_set(set_number: int, intervals: list, recoveries: list) -> dict:
    set_max_hr    = max((iv.get('max_hr_bpm',       0) for iv in intervals), default=None)
    set_max_power = max((iv.get('max_power_w',      0) for iv in intervals), default=None)
    set_peak_cad  = max((iv.get('peak_cadence_rpm', 0) for iv in intervals), default=None)
    return {
        'set_number':           set_number,
        'set_max_hr_bpm':       set_max_hr,
        'set_max_power_w':      set_max_power,
        'set_peak_cadence_rpm': set_peak_cad,
        'intervals':            intervals,
        'recoveries':           recoveries,
    }


def _compute_summary(intervals: list, recoveries: list) -> dict:
    if not intervals:
        return {}
    powers    = [iv.get('avg_power_w',     0) for iv in intervals]
    max_pows  = [iv.get('max_power_w',     0) for iv in intervals]
    cadences  = [iv.get('avg_cadence_rpm', 0) for iv in intervals]
    peak_cads = [iv.get('peak_cadence_rpm', 0) for iv in intervals]
    hr_avgs   = [iv.get('avg_hr_bpm')         for iv in intervals]
    hr_maxes  = [iv.get('max_hr_bpm')         for iv in intervals]
    durations = [iv.get('duration_s',      0) for iv in intervals]
    rest_durs = [r.get('duration_s',       0) for r in recoveries]

    valid_max_pows  = [x for x in max_pows  if x is not None]
    valid_hr_maxes  = [x for x in hr_maxes  if x is not None]
    valid_peak_cads = [x for x in peak_cads if x is not None]

    summary: dict = {
        'avg_interval_duration_s':  round(sum(durations) / len(durations), 0),
        'avg_interval_power_w':     round(sum(powers) / len(powers), 0),
        'session_max_power_w':      max(valid_max_pows)  if valid_max_pows  else None,
        'power_decay_w':            round(powers[-1] - powers[0], 0) if len(powers) > 1 else 0,
        'cadence_decay_rpm':        round(cadences[-1] - cadences[0], 0) if len(cadences) > 1 else 0,
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