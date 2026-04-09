"""
Activity analysis: classification and metric extraction.

Single entry point `analyse_activity` that fetches all required data,
delegates to the appropriate analytics modules, and persists results to DB.

mode='structure': classify workout type, persist classification_data.
mode='full':      structure + extract metrics at appropriate frequency,
                  persist execution_data.
mode='llm':       full + assemble a stripped-down, token-efficient payload
                  ready to send to an LLM for coaching feedback.

AI coaching is handled separately in app.ai_coach.
"""

import json
import logging

from app.models.db import db
from app.models.strava import Activity
from app.models.analytics import ActivityAnalytics
from app.models.user import User
from app.analytics import activity_report as activity_report_module
from app.analytics import activity_classifier
from app.analytics.activity_derivations import compute_advanced_metrics
from app.analytics import activity_tss
from app.analytics import activity_power

logger = logging.getLogger(__name__)


def _get_or_create_analytics(activity_id, user_id):
    """Get or create an ActivityAnalytics record for the given activity."""
    analytics = ActivityAnalytics.query.filter_by(activity_id=activity_id).first()
    if not analytics:
        analytics = ActivityAnalytics(activity_id=activity_id, user_id=user_id)
        db.session.add(analytics)
    return analytics


def analyse_activity(user_id: int, activity_id: int, mode: str = 'structure') -> dict:
    """
    Classify an activity into a type and then extract key metrics that can be used by LLM to interpret to a user in natural language.

    Args:
        user_id:     User ID
        activity_id: Activity ID
        mode:        'structure' — classify and return structured data
                     'full'     — structure + extract metrics at appropriate frequency
                     'llm'      — full + assemble token-efficient LLM payload

    Returns:
        dict with keys:
          success         bool
          error           str (on failure)
          identification  dict  (always present on success)
          metrics         dict  (mode='full' only)
          console_summary dict  (compact subset for console display)
    """
    user = User.query.get(user_id)
    if not user:
        return {'success': False, 'error': f'User {user_id} not found'}

    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        return {'success': False, 'error': f'Activity {activity_id} not found for user {user_id}'}

    ftp    = float(user.ftp)            if user.ftp            else None
    max_hr = float(user.max_heart_rate) if user.max_heart_rate else None
    activity_date = activity.start_date_local.strftime('%Y-%m-%d') if activity.start_date_local else None

    # ---------------------------------------------------------------------- #
    # Classification                                                           #
    # ---------------------------------------------------------------------- #
    try:
        classified      = activity_classifier.classify_activity(user_id, activity_id)
        classification  = classified['classification']
        evidence        = classified['evidence']
        evidence_detail = classified['evidence_detail']
        workout_type    = classification['workout_type']

        identification = {
            'activity_id':     str(activity_id),
            'activity_name':   activity.name,
            'activity_date':   activity_date,
            'athlete':         {'ftp': ftp, 'max_hr': max_hr},
            'classification':  classification,
            'evidence':        evidence,
            'evidence_detail': evidence_detail or None,
        }

        analytics = _get_or_create_analytics(activity_id, user_id)
        analytics.classification_data = json.dumps(identification)
        db.session.commit()

    except Exception as e:
        logger.error(f'analyse_activity() classification failed for {activity_id}: {e}')
        return {'success': False, 'error': f'Classification failed: {e}'}

    console_summary_keys = ['activity_id', 'activity_name', 'activity_date', 'athlete', 'classification', 'evidence']
    console_summary = {k: identification[k] for k in console_summary_keys if k in identification}

    result = {
        'success':         True,
        'identification':  identification,
        'console_summary': console_summary,
    }

    if mode == 'structure':
        return result

    # ---------------------------------------------------------------------- #
    # Ensure base metrics are computed (full / llm mode)                       #
    # ---------------------------------------------------------------------- #
    _ensure_base_metrics(activity, analytics, user_id, activity_id)
    db.session.refresh(activity)
    db.session.refresh(analytics)

    # ---------------------------------------------------------------------- #
    # Metric extraction (full mode)                                            #
    # ---------------------------------------------------------------------- #
    try:
        if workout_type in ('threshold', 'vo2'):
            metrics_payload = evidence_detail or {}

            sets       = metrics_payload.get('sets', [])
            intervals  = [iv for s in sets for iv in s.get('intervals',  [])]
            recoveries = [r  for s in sets for r  in s.get('recoveries', [])]
            summary    = metrics_payload.get('summary', {})
            if intervals and summary:
                advanced = compute_advanced_metrics(
                    intervals      = intervals,
                    recoveries     = recoveries,
                    summary        = summary,
                    workout_type   = workout_type,
                    interval_type  = classification.get('interval_type'),
                    ftp            = ftp,
                    max_hr         = max_hr,
                )
                metrics_payload = {**metrics_payload, **advanced}
        else:
            raw = activity_report_module.generate_activity_report_json(user_id, activity_id)
            metrics_payload = json.loads(raw) if raw else {}

        metrics = {
            'activity_id':   str(activity_id),
            'activity_name': activity.name,
            'activity_date': activity_date,
            'data':          metrics_payload,
        }

        analytics.execution_data = json.dumps(metrics)
        db.session.commit()

        result['metrics'] = metrics

    except Exception as e:
        logger.error(f'analyse_activity() metric extraction failed for {activity_id}: {e}')
        return {'success': False, 'error': f'Metric extraction failed: {e}'}

    if mode == 'full':
        return result

    # ---------------------------------------------------------------------- #
    # LLM payload assembly (llm mode)                                          #
    # ---------------------------------------------------------------------- #
    try:
        db.session.refresh(analytics)
        llm_payload = _build_llm_payload(activity, analytics, user_id, identification, metrics_payload)
        result['llm_payload'] = llm_payload
    except Exception as e:
        logger.error(f'analyse_activity() llm payload assembly failed for {activity_id}: {e}')
        return {'success': False, 'error': f'LLM payload assembly failed: {e}'}

    return result


def _ensure_base_metrics(activity, analytics, user_id: int, activity_id: int) -> None:
    """Compute and persist TSS, time-in-zones, and power curve if not already present."""
    if not activity.tss:
        logger.info(f"_ensure_base_metrics() TSS missing for {activity_id} — computing")
        activity_tss.calculate_tss(user_id, activity_id)

    tiz = analytics.time_in_zones
    if not tiz or tiz in ('{}', '[]', ''):
        logger.info(f"_ensure_base_metrics() time_in_zones missing for {activity_id} — computing")
        activity_power.calculate_power_distribution(user_id, activity_id)

    pc = analytics.power_curve_data
    if not pc or pc in ('{}', '[]', ''):
        logger.info(f"_ensure_base_metrics() power_curve missing for {activity_id} — computing")
        activity_power.calculate_power_curve(user_id, activity_id)


def _duration_label(seconds: int) -> str:
    """Convert a duration in seconds to a readable label: 15 → '15s', 300 → '5min', 3600 → '1hr', 5400 → '90min'."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600 or seconds % 3600 != 0:
        return f"{seconds // 60}min"
    else:
        return f"{seconds // 3600}hr"


def _zones_with_pct(zones_dict: dict) -> tuple:
    """Return (zones_s dict, zones_pct dict) from a {zone_name: seconds} dict."""
    total = sum(v for v in zones_dict.values() if isinstance(v, (int, float)))
    pct = {
        k: round(v / total * 100, 1) if total > 0 else 0.0
        for k, v in zones_dict.items()
    }
    return zones_dict, pct


def _pw_hr_decoupling(segments: list) -> float | None:
    """
    Aerobic decoupling: difference in Pw:HR ratio between first and second half.
    Positive = HR drifted up relative to power (fatigue / heat / dehydration).
    """
    valid = [s for s in segments if s.get('avg_power_w') and s.get('avg_hr_bpm')]
    if len(valid) < 4:
        return None
    mid = len(valid) // 2
    first, second = valid[:mid], valid[mid:]

    def _ratio(segs):
        p = sum(s['avg_power_w'] for s in segs) / len(segs)
        h = sum(s['avg_hr_bpm'] for s in segs) / len(segs)
        return p / h if h > 0 else None

    r1, r2 = _ratio(first), _ratio(second)
    if r1 and r2 and r1 > 0:
        return round((r1 - r2) / r1 * 100, 1)
    return None


def _build_llm_payload(activity, analytics, user_id: int, identification: dict, data: dict) -> dict:
    """
    Assemble a stripped-down, token-efficient payload for LLM coaching.
    """
    classification = identification.get('classification', {})
    athlete        = identification.get('athlete', {})
    workout_type   = classification.get('workout_type', '')
    ftp            = athlete.get('ftp')

    secs = int(activity.elapsed_time or activity.moving_time or 0)
    duration_str = f"{secs // 3600}h {(secs % 3600) // 60}m"

    # ------------------------------------------------------------------ #
    # Whole-ride metrics                                                    #
    # ------------------------------------------------------------------ #
    np_w   = float(activity.weighted_average_watts) if activity.weighted_average_watts else None
    avg_w  = float(activity.average_watts)          if activity.average_watts          else None
    vi     = round(np_w / avg_w, 3)                 if np_w and avg_w and avg_w > 0   else None
    if_val = round(np_w / ftp, 3)                   if np_w and ftp and ftp > 0       else None

    def _ms_to_kph(ms):
        return round(float(ms) * 3.6, 1) if ms is not None else None

    def _int_or_none(val):
        return int(round(float(val))) if val is not None else None

    whole_ride_metrics = {
        'activity_duration_s': int(activity.elapsed_time) if activity.elapsed_time else secs,
        'moving_time_s':       int(activity.moving_time) if activity.moving_time else None,
        'power_data_s':        None,  # filled from segments below (endurance) or left null (intervals)
        'hr_data_s':           None,  # filled from segments below (endurance) or left null (intervals)
        'avg_power_w':        _int_or_none(activity.average_watts),
        'normalised_power_w': _int_or_none(activity.weighted_average_watts),
        'max_power_w':        _int_or_none(activity.max_watts),
        'avg_hr_bpm':         _int_or_none(activity.average_heartrate),
        'max_hr_bpm':         _int_or_none(activity.max_heartrate),
        'avg_cadence_rpm':    _int_or_none(activity.average_cadence),
        'avg_speed_kph':      _ms_to_kph(activity.average_speed),
        'max_speed_kph':      _ms_to_kph(activity.max_speed),
        'elevation_gain_m':   _int_or_none(activity.total_elevation_gain),
        'variability_index':  vi,
        'intensity_factor':   if_val,
        'tss':                round(float(activity.tss), 1) if activity.tss else None,
    }

    payload = {
        'activity': {
            'name':     activity.name,
            'date':     identification.get('activity_date'),
            'type':     activity.type,
            'duration': duration_str,
        },
        'athlete': {
            'ftp_w':      ftp,
            'max_hr_bpm': athlete.get('max_hr'),
        },
        'whole_ride_metrics': whole_ride_metrics,
        'classification':     classification,
    }

    # ------------------------------------------------------------------ #
    # Power curve                                                           #
    # ------------------------------------------------------------------ #
    raw_pc = analytics.power_curve_data
    if raw_pc and raw_pc not in ('{}', '[]', ''):
        try:
            pc_dict = json.loads(raw_pc)
            # Keys are stored as strings; convert to int for the filter function
            pc_int  = {int(k): v for k, v in pc_dict.items()}
            key_pc  = activity_power.get_key_power_curve_durations(pc_int)
            payload['power_curve'] = [
                {'duration': _duration_label(k), 'watts': v}
                for k, v in sorted(key_pc.items())
            ]
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Time in power zones (+ percentages)                                   #
    # ------------------------------------------------------------------ #
    raw_tiz = analytics.time_in_zones
    if raw_tiz and raw_tiz not in ('{}', '[]', ''):
        try:
            tiz_dict = json.loads(raw_tiz)
            tiz_s, tiz_pct = _zones_with_pct(tiz_dict)
            payload['time_in_power_zones_s']   = tiz_s
            payload['time_in_power_zones_pct'] = tiz_pct
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Time in HR zones                                                      #
    # ------------------------------------------------------------------ #
    hr_zones = activity_power.calculate_hr_distribution(user_id, activity.id)
    if hr_zones:
        hr_s, hr_pct = _zones_with_pct(hr_zones)
        payload['time_in_hr_zones_s']   = hr_s
        payload['time_in_hr_zones_pct'] = hr_pct

    # ------------------------------------------------------------------ #
    # Interval session or endurance time-series                             #
    # ------------------------------------------------------------------ #
    REP_KEEP   = {'rep_number', 'duration_s', 'avg_power_w', 'avg_hr_bpm', 'hr_at_end_bpm', 'avg_cadence_rpm'}
    WIA_KEEP   = {'hr_lag_s', 'cadence_drop_pct'}
    ES_DROP    = {'avg_interval_power_w', 'session_max_power_w', 'avg_end_hr_bpm_last_rep', 'recovery_power_w'}
    FLAGS_DROP = {'power_fade_flag', 'cadence_collapse_flag', 'insufficient_hr_response_flag', 'late_fatigue_flag'}

    if workout_type in ('threshold', 'vo2'):
        reps = []
        for s in data.get('sets', []):
            for iv in s.get('intervals', []):
                rep = {k: v for k, v in iv.items() if k in REP_KEEP}
                wia = iv.get('within_interval_analysis', {})
                if wia:
                    rep['within_interval_analysis'] = {k: v for k, v in wia.items() if k in WIA_KEEP}
                reps.append(rep)

        raw_es    = data.get('execution_summary') or {}
        raw_flags = data.get('flags') or {}

        payload['interval_session'] = {
            'reps':               reps,
            'execution_summary':  {k: v for k, v in raw_es.items()    if k not in ES_DROP},
            'benefit_assessment': data.get('benefit_assessment'),
            'flags':              {k: v for k, v in raw_flags.items() if k not in FLAGS_DROP},
        }
    else:
        segments = data.get('intervals', [])
        payload['time_series'] = [
            {
                't_min':            seg.get('elapsed_min'),
                'moving_time_s':    seg.get('moving_time_s'),
                'avg_power_w':      seg.get('avg_power_w'),
                'max_power_w':      seg.get('max_power_w'),
                'norm_power_w':     seg.get('norm_power_w'),
                'power_data_s':     seg.get('power_data_s'),
                'avg_hr_bpm':       seg.get('avg_hr_bpm'),
                'max_hr_bpm':       seg.get('max_hr_bpm'),
                'hr_data_s':        seg.get('hr_data_s'),
                'avg_cadence_rpm':  seg.get('avg_cadence_rpm'),
                'avg_speed_kph':    seg.get('avg_speed_kph'),
                'avg_gradient_pct': seg.get('avg_gradient_pct'),
                'elevation_gain_m': seg.get('elevation_gain_m'),
            }
            for seg in segments
        ]
        whole_ride_metrics['pw_hr_decoupling_pct'] = _pw_hr_decoupling(segments)
        whole_ride_metrics['power_data_s']         = sum(s.get('power_data_s') or 0 for s in segments)
        whole_ride_metrics['hr_data_s']            = sum(s.get('hr_data_s')    or 0 for s in segments)

    return payload
