"""
Activity analysis: classification and metric extraction.

Single entry point `analyse_activity` that fetches all required data,
delegates to the appropriate analytics modules, and persists results to DB.

mode='structure': classify workout type, persist identification_data.
mode='full':      structure + extract metrics at appropriate frequency,
                  persist metrics_data.
mode='llm':       full + assemble a stripped-down, token-efficient payload
                  ready to send to an LLM for coaching feedback.

AI coaching is handled separately in app.ai_coach.coach.
"""

import json
import logging

from app.models.db import db
from app.models.strava import Activity
from app.models.user import User
from app.analytics import activity_report as activity_report_module
from app.analytics import activity_classifier
from app.analytics.activity_derivations import compute_advanced_metrics
from app.analytics import activity_tss
from app.analytics import activity_power

logger = logging.getLogger(__name__)

#
# Common entry point from cli and insights (ffrom the front end)
#
def analyse_activity(user_id: int, activity_id: int, mode: str = 'structure') -> dict:
    """
    Classify an activity into a type and then extract key metrics that can be used by LLM to interpret to a user in natural language.

    Args:
        user_id:     User ID
        activity_id: Activity ID
        mode:        'structure' — classify and return structured data
                     'full'     — structure + extract metrics at appropriate frequency

    Returns:
        dict with keys:
          success         bool
          error           str (on failure)
          identification  dict  (always present on success)
          metrics      dict  (mode='full' only)
          console_summary dict  (compact subset for console display)
    """
    user = User.query.get(user_id)
    if not user:
        return {'success': False, 'error': f'User {user_id} not found'}

    # get key activity data
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
        # this is the meaty bit - the classifier should try to classify
        classified = activity_classifier.classify_activity(user_id, activity_id)
        classification  = classified['classification']
        evidence        = classified['evidence']
        evidence_detail = classified['evidence_detail']
        workout_type    = classification['workout_type']

        identification = {
            'activity_id':           str(activity_id),
            'activity_name':         activity.name,
            'activity_date':         activity_date,
            'athlete':               {'ftp': ftp, 'max_hr': max_hr},
            'classification':        classification,
            'evidence':              evidence,
            'evidence_detail':       evidence_detail or None,
            'classification_source': 'deterministic',
        }

        activity.identification_data   = json.dumps(identification)
        activity.confirmed_type        = workout_type + (
            f"_{classification['interval_type']}" if classification.get('interval_type') else ''
        )
        activity.classification_source = 'deterministic'
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
    _ensure_base_metrics(activity, user_id, activity_id)
    db.session.refresh(activity)

    # ---------------------------------------------------------------------- #
    # Metric extraction (full mode)                                            #
    # ---------------------------------------------------------------------- #
    try:
        if workout_type in ('threshold', 'vo2'):
            # Per-rep snapshots already computed by _analyse_activity_structure
            metrics_payload = evidence_detail or {}

            # Derive advanced metrics from interval structure + athlete thresholds
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
            # endurance / tempo: 15-min time-series snapshots
            # TODO: make snapshot frequency dependent on duration for tempo
            raw = activity_report_module.generate_activity_report_json(user_id, activity_id)
            metrics_payload = json.loads(raw) if raw else {}

        metrics = {
            'activity_id':    str(activity_id),
            'activity_name':  activity.name,
            'activity_date':  activity_date,
            'confirmed_type': activity.confirmed_type,
            'data':           metrics_payload,
        }

        activity.assessment_data = json.dumps(metrics)
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
        llm_payload = _build_llm_payload(activity, identification, metrics_payload)
        result['llm_payload'] = llm_payload
    except Exception as e:
        logger.error(f'analyse_activity() llm payload assembly failed for {activity_id}: {e}')
        return {'success': False, 'error': f'LLM payload assembly failed: {e}'}

    return result


def _ensure_base_metrics(activity, user_id: int, activity_id: int) -> None:
    """Compute and persist TSS and time-in-zones if not already present."""
    if not activity.tss:
        logger.info(f"_ensure_base_metrics() TSS missing for {activity_id} — computing")
        activity_tss.calculate_tss(user_id, activity_id)

    tiz = activity.time_in_zones
    if not tiz or tiz in ('{}', '[]', ''):
        logger.info(f"_ensure_base_metrics() time_in_zones missing for {activity_id} — computing")
        activity_power.calculate_power_distribution(user_id, activity_id)


def _build_llm_payload(activity, identification: dict, data: dict) -> dict:
    """
    Assemble a stripped-down, token-efficient payload for LLM coaching.

    Includes whole-ride metrics from the Activity model, classification,
    and analytics data with snapshots removed.
    """
    classification = identification.get('classification', {})
    athlete        = identification.get('athlete', {})
    workout_type   = classification.get('workout_type', '')

    secs = int(activity.moving_time or 0)
    duration_str = f"{secs // 3600}h {(secs % 3600) // 60}m"

    # Fields to keep per rep
    REP_KEEP = {'rep_number', 'duration_s', 'avg_power_w', 'avg_hr_bpm', 'hr_at_end_bpm', 'avg_cadence_rpm'}
    WIA_KEEP = {'hr_lag_s', 'cadence_drop_pct'}

    # Fields to drop from execution_summary (covered by natural-language labels or % equivalents)
    ES_DROP = {'avg_interval_power_w', 'session_max_power_w', 'avg_end_hr_bpm_last_rep', 'recovery_power_w'}

    # Flags to drop (LLM doesn't need booleans when it has natural-language summaries)
    FLAGS_DROP = {'power_fade_flag', 'cadence_collapse_flag', 'insufficient_hr_response_flag', 'late_fatigue_flag'}

    payload = {
        'activity': {
            'name':     activity.name,
            'date':     identification.get('activity_date'),
            'type':     activity.type,
            'duration': duration_str,
        },
        'athlete': {
            'ftp_w':      athlete.get('ftp'),
            'max_hr_bpm': athlete.get('max_hr'),
        },
        'whole_ride_metrics': {
            'normalised_power_w': int(round(float(activity.weighted_average_watts))) if activity.weighted_average_watts else None,
            'tss':                round(float(activity.tss), 1)                     if activity.tss                    else None,
        },
        'classification': classification,
    }

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
        # Endurance/tempo: time-series segments
        segments = data.get('intervals', [])
        payload['time_series'] = [
            {
                't_min':       round(seg.get('start_time_s', 0) / 60),
                'avg_power_w': seg.get('avg_power_w'),
                'avg_hr_bpm':  seg.get('avg_hr_bpm'),
            }
            for seg in segments
        ]

    return payload
