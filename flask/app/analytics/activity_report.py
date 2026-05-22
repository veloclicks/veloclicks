"""
Endurance ride reporting: generates time-series snapshots for analysis.

For interval session structure and classification, see activity_classifier.py.
"""

import json
import logging
import os
from typing import Optional

import pandas as pd

from app.strava.service import get_activity_streams


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
# Endurance / long ride report                                                   #
# ============================================================================ #

def generate_activity_report(user_id: str, activity_id: str) -> Optional[pd.DataFrame]:
    """
    Generate a 15-minute interval performance report for a Strava activity.

    Returns a DataFrame with one row per 15-minute interval, or None if
    streams are unavailable.
    """
    logging.info(f"generate_activity_report() for user {user_id}, activity {activity_id}")

    stream_types = [
        'time', 'distance', 'altitude', 'velocity_smooth',
        'heartrate', 'cadence', 'watts', 'grade_smooth', 'moving'
    ]
    streams = get_activity_streams(user_id, activity_id, stream_types=stream_types)
    if not streams:
        logging.error("generate_activity_report() failed to retrieve streams")
        return None

    time_data = streams.get('time', {}).get('data')
    if not time_data:
        logging.error("generate_activity_report() time stream missing")
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
        'moving':          ('moving',       'moving'),
    }
    for _, (df_col, stream_key) in stream_map.items():
        if stream_key in streams:
            df[df_col] = streams[stream_key]['data']
        else:
            df[df_col] = float('nan')

    # Strava occasionally emits duplicate timestamps; drop after all streams are loaded
    # so every column is the same length when we deduplicate.
    df = df[~df['elapsed_s'].duplicated(keep='last')]

    df['speed_kph'] = df['speed_ms'] * 3.6

    # Treat zero power as no data — power meters send 0 for dropouts, not null
    if 'power_w' in df.columns:
        df['power_w_valid'] = df['power_w'].where(df['power_w'] > 0)
    else:
        df['power_w_valid'] = float('nan')

    # Same for HR — 0 bpm is physiologically impossible, treat as missing
    if 'hr_bpm' in df.columns:
        df['hr_bpm_valid'] = df['hr_bpm'].where(df['hr_bpm'] > 0)
    else:
        df['hr_bpm_valid'] = float('nan')

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
        avg_power_w      = ('power_w',       'mean'),
        max_power_w      = ('power_w',       'max'),
        norm_power_w     = ('power_w_np',    norm_power),
        power_data_s     = ('power_w_valid',  'count'),
        avg_hr_bpm       = ('hr_bpm',        'mean'),
        max_hr_bpm       = ('hr_bpm',        'max'),
        hr_data_s        = ('hr_bpm_valid',   'count'),
        avg_cadence_rpm  = ('cadence_rpm',   'mean'),
        avg_speed_kph    = ('speed_kph',     'mean'),
        avg_gradient_pct = ('gradient_pct',  'mean'),
        elapsed_start_s  = ('elapsed_s',     'min'),
        moving_time_s    = ('moving',        'sum'),
    ).reset_index()

    # moving_time_s: null if Strava didn't provide the stream (sum of all-NaN = 0, indistinguishable from stopped)
    if 'moving' not in streams:
        agg['moving_time_s'] = float('nan')

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
        'avg_power_w': 0, 'max_power_w': 0, 'norm_power_w': 0,
        'avg_hr_bpm': 0, 'max_hr_bpm': 0,
        'avg_cadence_rpm': 0, 'avg_speed_kph': 1, 'avg_gradient_pct': 1,
        'distance_km': 2, 'elevation_gain_m': 0,
        'moving_time_s': 0, 'power_data_s': 0, 'hr_data_s': 0,
    }
    for col, decimals in round_map.items():
        if col in agg.columns:
            agg[col] = agg[col].round(decimals)

    cols = [
        'interval', 'elapsed_min', 'distance_km', 'moving_time_s',
        'avg_power_w', 'max_power_w', 'norm_power_w', 'power_data_s',
        'avg_hr_bpm', 'max_hr_bpm', 'hr_data_s',
        'avg_cadence_rpm', 'avg_speed_kph',
        'avg_gradient_pct', 'elevation_gain_m',
    ]
    result = agg[cols].copy()
    logging.info(f"generate_activity_report() generated {len(result)} intervals")
    return result


def report_to_json(
    df:          pd.DataFrame,
    activity_id: Optional[str] = None,
    pretty:      bool = True,
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

    intervals = [{k: _safe(v) for k, v in row.items()} for row in df.to_dict(orient='records')]

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
    user_id:     str,
    activity_id: str,
    pretty:      bool = True,
    output_dir:  Optional[str] = None,
) -> str:
    """Fetch streams, build report, return JSON. Optionally write to file."""
    df = generate_activity_report(user_id, activity_id)
    if df is None:
        return ""
    result = report_to_json(df, activity_id=activity_id, pretty=pretty)
    if result and output_dir:
        try:
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"{activity_id}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)
        except Exception as e:
            logging.error(f"generate_activity_report_json() failed to write file: {e}")
    return result
