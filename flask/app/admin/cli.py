"""
Flask CLI commands for administrative batch operations.

Usage:
    docker compose exec app flask admin <command> [options]

Examples:
    # List activities for a month
    docker compose exec app flask admin list-activities --user-id 1 --year 2024 --month 11

    # Calculate metrics for all activities in a specific month
    docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024 --month 11

    # Calculate metrics for entire year
    docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024

    # Calculate only TSS for a month
    docker compose exec app flask admin calculate-tss --user-id 1 --year 2024 --month 11

    # Calculate only power metrics for a month
    docker compose exec app flask admin calculate-power --user-id 1 --year 2024 --month 11

    # Analyse an activity (structure: classify + assess; full: structure + AI coaching)
    docker compose exec flask flask admin analyse-activity --user-id 1 --activity-id 12345678
    docker compose exec flask flask admin analyse-activity --user-id 1 --activity-id 12345678 --mode full
"""

import click
import logging
import json
import os
from flask.cli import with_appcontext
from datetime import datetime
from sqlalchemy import extract

from app.models import db
from app.models.strava import Activity
from app.models.analytics import ActivityAnalytics
from app.models.ai_coach import ActivityInsight
from app.analytics import activity_tss, activity_power, activity_report as activity_report_module
from app.analytics import activity_analyser
from app.analytics.activity_warmup_finder import detect_warmup
from app.profile import tools as profile_tools
from app.ai_coach.routes import _get_lambda_client
from app.strava.streams import get_activity_streams

logger = logging.getLogger(__name__)



@click.group()
def admin():
    """
    Administrative batch operations for VeloClicks.

    Available commands:
      user-info            Display user information by username (email)
      list-activities      List activities for a user in a specific month
      calculate-metrics    Calculate all metrics (power + TSS) for activities
      calculate-power      Calculate only power metrics (curve + zones)
      calculate-tss        Calculate only TSS for activities
      analyse-activity     Classify and assess an activity (mode=structure|full)
      activity-coach-insights    Generate AI coaching feedback for an activity

    Use 'flask admin COMMAND --help' for detailed help on each command.
    """
    pass


# --------------------------------------------------------------------------
# helper: get activities for a period of time
# --------------------------------------------------------------------------
def _get_activities_by_period(user_id: int, year: int, month: int = None):
    """
    Get activities for a user by year and optionally month.

    Args:
        user_id: User ID
        year: Year (e.g., 2024)
        month: Optional month (1-12)

    Returns:
        List of Activity objects
    """
    query = Activity.query.filter_by(user_id=user_id)

    # Filter by year
    query = query.filter(extract('year', Activity.start_date_local) == year)

    # Filter by month if provided
    if month:
        query = query.filter(extract('month', Activity.start_date_local) == month)

    # Order by date ascending
    activities = query.order_by(Activity.start_date_local.asc()).all()

    return activities


# --------------------------------------------------------------------------------------
#   USER INFO
# --------------------------------------------------------------------------------------
@admin.command('user-info')
@click.option('--username', required=True, help='Username (email) to look up')
@with_appcontext
def user_info(username):
    """
    Display user information by username (email).
    """
    from app.models.user import User

    # Query user to get user_id
    user = User.query.filter_by(email=username).first()

    if not user:
        click.echo(f"User not found: '{username}'", err=True)
        return

    # Get profile data using reusable tool
    profile = profile_tools.get_profile(user.id)

    if not profile:
        click.echo(f"Error retrieving profile for user {user.id}", err=True)
        return

    # Display user information
    click.echo("=" * 80)
    click.echo("USER INFORMATION")
    click.echo("=" * 80)
    click.echo(f"ID:               {user.id}")
    click.echo(f"Email:            {profile['email']}")
    click.echo(f"Username:         {profile['username']}")
    click.echo(f"First Name:       {profile['firstname'] or 'Not set'}")
    click.echo(f"Last Name:        {profile['lastname'] or 'Not set'}")
    click.echo(f"Membership Type:  {user.membership_type or 'Not set'}")
    click.echo(f"Sex:              {profile['sex'] or 'Not set'}")
    click.echo(f"Date of Birth:    {profile['date_of_birth'] or 'Not set'}")
    click.echo(f"FTP:              {profile['ftp'] or 'Not set'}")
    click.echo(f"Max Heart Rate:   {profile['max_heart_rate'] or 'Not set'}")
    click.echo(f"Resting HR:       {profile['resting_heart_rate'] or 'Not set'}")

    click.echo("=" * 80)


# --------------------------------------------------------------------------
# list activities
# --------------------------------------------------------------------------
@admin.command('list-activities')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--year', required=True, type=int, help='Year (2018 or later)')
@click.option('--month', required=True, type=int, help='Month (1-12)')
@with_appcontext
def list_activities(user_id, year, month):
    """
    List all activities for a user in a specific month with key metrics.

    Displays: Activity ID, Date, Name, Duration, TSS, NP (Normalized Power),
    and whether power curve data exists.
    """
    # Validate year
    if year < 2018:
        click.echo("Error: Year must be 2018 or later", err=True)
        return

    # Validate month
    if month < 1 or month > 12:
        click.echo("Error: Month must be between 1 and 12", err=True)
        return

    period_str = f"{year}-{month:02d}"
    click.echo("=" * 140)
    click.echo(f"ACTIVITIES FOR USER {user_id} - {period_str}")
    click.echo("=" * 140)

    # Get activities
    activities = _get_activities_by_period(user_id, year, month)

    if not activities:
        click.echo(f"No activities found for user {user_id} in {period_str}")
        return

    # Print header
    click.echo(f"{'ID':<15} {'Date':<12} {'Duration':<10} {'TSS':<8} {'NP':<8} {'Power Curve':<12} {'Name':<50}")
    click.echo("-" * 140)

    # Print each activity
    for activity in activities:
        # Format date
        activity_date = activity.start_date_local.strftime('%Y-%m-%d')

        # Format duration (convert seconds to HH:MM:SS)
        duration_seconds = int(activity.moving_time) if activity.moving_time else 0
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # TSS
        tss_str = f"{activity.tss:.1f}" if activity.tss is not None and activity.tss > 0 else "-"

        # Normalized Power (weighted_average_watts)
        np_str = f"{int(activity.weighted_average_watts)}W" if activity.weighted_average_watts else "-"

        # Check if power curve exists
        has_power_curve = False
        analytics = ActivityAnalytics.query.filter_by(activity_id=activity.id).first()
        if analytics and analytics.power_curve_data:
            try:
                power_data = json.loads(analytics.power_curve_data)
                has_power_curve = len(power_data) > 0
            except:
                pass
        power_curve_str = "Yes" if has_power_curve else "No"

        # Truncate name if too long
        name = activity.name[:47] + "..." if len(activity.name) > 50 else activity.name

        click.echo(f"{activity.id:<15} {activity_date:<12} {duration_str:<10} {tss_str:<8} {np_str:<8} {power_curve_str:<12} {name:<50}")

    # Summary
    click.echo("-" * 140)
    click.echo(f"Total activities: {len(activities)}")

    # Calculate summary stats
    activities_with_tss = sum(1 for a in activities if a.tss is not None and a.tss > 0)
    activities_with_np = sum(1 for a in activities if a.weighted_average_watts is not None)
    analytics_map = {a.activity_id: a for a in ActivityAnalytics.query.filter(ActivityAnalytics.activity_id.in_([a.id for a in activities])).all()}
    activities_with_power_curve = sum(1 for a in activities if analytics_map.get(a.id) and analytics_map[a.id].power_curve_data and len(analytics_map[a.id].power_curve_data) > 2)

    click.echo(f"With TSS: {activities_with_tss} | With NP: {activities_with_np} | With Power Curve: {activities_with_power_curve}")
    click.echo("=" * 140)


# --------------------------------------------------------------------------------------
#                          CALCULATE POWER AND TSS METRICS IN BATCH
# --------------------------------------------------------------------------------------
@admin.command('calculate-metrics')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--year', required=True, type=int, help='Year (e.g., 2024)')
@click.option('--month', type=int, help='Optional month (1-12)')
@click.option('--skip-existing', is_flag=True, default=False, help='Skip activities that already have metrics calculated')
@with_appcontext
def calculate_metrics(user_id, year, month, skip_existing):
    """
    Calculate all metrics (power curve, power distribution, TSS) for activities.

    This command calculates:
    - Power curve (max average power for various durations)
    - Power distribution (time spent in each power zone)
    - TSS (Training Stress Score based on heart rate)
    """
    period_str = f"{year}-{month:02d}" if month else str(year)
    click.echo(f"Starting metrics calculation for user {user_id}, period: {period_str}")
    click.echo(f"Skip existing: {skip_existing}")
    click.echo("-" * 80)

    # Get activities
    activities = _get_activities_by_period(user_id, year, month)

    if not activities:
        click.echo(f"No activities found for user {user_id} in {period_str}")
        return

    click.echo(f"Found {len(activities)} activities")
    click.echo("-" * 80)

    # Counters
    processed = 0
    skipped = 0
    power_success = 0
    power_skipped = 0
    power_failed = 0
    tss_success = 0
    tss_skipped = 0
    tss_failed = 0

    for activity in activities:
        activity_date = activity.start_date_local.strftime('%Y-%m-%d')
        click.echo(f"\nActivity {activity.id} ({activity_date}): {activity.name}")

        # Calculate power metrics
        _analytics = ActivityAnalytics.query.filter_by(activity_id=activity.id).first()
        has_power_data = _analytics and (_analytics.power_curve_data or _analytics.time_in_zones)
        if skip_existing and has_power_data:
            click.echo("  [Power] Skipping (already calculated)")
            power_skipped += 1
        else:
            try:
                result = activity_power.calculate_power_metrics(user_id, activity.id)
                if result['power_curve'] or result['time_in_zones']:
                    click.echo(f"  [Power] ✓ Calculated")
                    if result['power_curve']:
                        click.echo(f"    - Power curve: {len(result['power_curve'])} data points")
                    if result['time_in_zones']:
                        click.echo(f"    - Time in zones: {len(result['time_in_zones'])} zones")
                    power_success += 1
                else:
                    click.echo("  [Power] No power data available")
                    power_skipped += 1
            except Exception as e:
                click.echo(f"  [Power] ✗ Failed: {str(e)}", err=True)
                power_failed += 1

        # Calculate TSS
        has_tss = activity.tss is not None and activity.tss > 0
        if skip_existing and has_tss:
            click.echo("  [TSS] Skipping (already calculated)")
            tss_skipped += 1
        else:
            try:
                tss = activity_tss.calculate_tss(user_id, activity.id)
                if tss is not None:
                    if tss > 0:
                        click.echo(f"  [TSS] ✓ Calculated: {tss}")
                        tss_success += 1
                    else:
                        click.echo("  [TSS] No heart rate data available")
                        tss_skipped += 1
                else:
                    click.echo("  [TSS] ✗ Failed (check logs)")
                    tss_failed += 1
            except Exception as e:
                click.echo(f"  [TSS] ✗ Failed: {str(e)}", err=True)
                tss_failed += 1

        processed += 1

    # Summary
    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Total activities processed: {processed}")
    click.echo(f"\nPower Metrics:")
    click.echo(f"  Success: {power_success}")
    click.echo(f"  Skipped: {power_skipped}")
    click.echo(f"  Failed:  {power_failed}")
    click.echo(f"\nTSS:")
    click.echo(f"  Success: {tss_success}")
    click.echo(f"  Skipped: {tss_skipped}")
    click.echo(f"  Failed:  {tss_failed}")
    click.echo("=" * 80)



# --------------------------------------------------------------------------------------
#  POWER
# --------------------------------------------------------------------------------------
@admin.command('calculate-power')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--year', required=True, type=int, help='Year (e.g., 2024)')
@click.option('--month', type=int, help='Optional month (1-12)')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip activities that already have power metrics')
@with_appcontext
def calculate_power(user_id, year, month, skip_existing):
    """
    Calculate power metrics (power curve and distribution) for activities.
    """
    period_str = f"{year}-{month:02d}" if month else str(year)
    click.echo(f"Starting power metrics calculation for user {user_id}, period: {period_str}")
    click.echo("-" * 80)

    activities = _get_activities_by_period(user_id, year, month)

    if not activities:
        click.echo(f"No activities found for user {user_id} in {period_str}")
        return

    click.echo(f"Found {len(activities)} activities")
    click.echo("-" * 80)

    success = 0
    skipped = 0
    failed = 0

    for activity in activities:
        activity_date = activity.start_date_local.strftime('%Y-%m-%d')
        click.echo(f"\nActivity {activity.id} ({activity_date}): {activity.name}")

        _analytics = ActivityAnalytics.query.filter_by(activity_id=activity.id).first()
        has_power_data = _analytics and (_analytics.power_curve_data or _analytics.time_in_zones)
        if skip_existing and has_power_data:
            click.echo("  Skipping (already calculated)")
            skipped += 1
            continue

        try:
            result = activity_power.calculate_power_metrics(user_id, activity.id)
            if result['power_curve'] or result['time_in_zones']:
                click.echo(f"  ✓ Success")
                if result['power_curve']:
                    click.echo(f"    - Power curve: {len(result['power_curve'])} data points")
                if result['time_in_zones']:
                    click.echo(f"    - Time in zones: {len(result['time_in_zones'])} zones")
                success += 1
            else:
                click.echo("  No power data available")
                skipped += 1
        except Exception as e:
            click.echo(f"  ✗ Failed: {str(e)}", err=True)
            failed += 1

    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Success: {success}")
    click.echo(f"Skipped: {skipped}")
    click.echo(f"Failed:  {failed}")
    click.echo("=" * 80)


# --------------------------------------------------------------------------------------
# 
#                                     TSS
#
# --------------------------------------------------------------------------------------
@admin.command('calculate-tss')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--year', required=True, type=int, help='Year (e.g., 2024)')
@click.option('--month', type=int, help='Optional month (1-12)')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip activities that already have TSS calculated')
@with_appcontext
def calculate_tss_command(user_id, year, month, skip_existing):
    """
    Calculate TSS (Training Stress Score) for activities.
    """
    period_str = f"{year}-{month:02d}" if month else str(year)
    click.echo(f"Starting TSS calculation for user {user_id}, period: {period_str}")
    click.echo("-" * 80)

    activities = _get_activities_by_period(user_id, year, month)

    if not activities:
        click.echo(f"No activities found for user {user_id} in {period_str}")
        return

    click.echo(f"Found {len(activities)} activities")
    click.echo("-" * 80)

    success = 0
    skipped = 0
    failed = 0

    for activity in activities:
        activity_date = activity.start_date_local.strftime('%Y-%m-%d')
        click.echo(f"\nActivity {activity.id} ({activity_date}): {activity.name}")

        has_tss = activity.tss is not None and activity.tss > 0
        if skip_existing and has_tss:
            click.echo(f"  Skipping (already calculated: TSS={activity.tss})")
            skipped += 1
            continue

        try:
            tss = activity_tss.calculate_tss(user_id, activity.id)
            if tss is not None:
                if tss > 0:
                    click.echo(f"  ✓ Success: TSS={tss}")
                    success += 1
                else:
                    click.echo("  No heart rate data available")
                    skipped += 1
            else:
                click.echo("  ✗ Failed (check logs)")
                failed += 1
        except Exception as e:
            click.echo(f"  ✗ Failed: {str(e)}", err=True)
            failed += 1

    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Success: {success}")
    click.echo(f"Skipped: {skipped}")
    click.echo(f"Failed:  {failed}")
    click.echo("=" * 80)


# --------------------------------------------------------------------------------------
#
#                                  AI INSIGHTS
#
# --------------------------------------------------------------------------------------
@admin.command('activity-coach-insights')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--activity-id', required=True, type=int, help='Activity ID')
@click.option('--detail-level', type=click.Choice(['simple', 'detailed']), default='simple', help='Level of detail: simple (quick, default) or detailed (comprehensive)')
@with_appcontext
def activity_insights(user_id, activity_id, detail_level):
    """
    Generate AI-powered insights for an activity (CLI command).
    """
    click.echo("=" * 80)
    click.echo(f"ACTIVITY INSIGHTS - User: {user_id}, Activity: {activity_id}, Detail: {detail_level}")
    click.echo("=" * 80)

    # Return cached insight if already generated
    insight = ActivityInsight.query.filter_by(
        activity_id=activity_id, user_id=user_id, insight_type='ACTIVITY_INSIGHT',
    ).first()
    if insight:
        click.echo("\n[Cached]\n" + insight.coach_insight)
        click.echo("=" * 80)
        return

    analysis = activity_analyser.analyse_activity(user_id, activity_id, mode='llm')
    if not analysis['success']:
        click.echo(f"Error: {analysis['error']}", err=True)
        return

    llm_payload = analysis.get('llm_payload')
    if not llm_payload:
        click.echo("Error: Failed to assemble activity data", err=True)
        return

    function_name = os.environ.get('COACH_LAMBDA_NAME', 'veloclicks-coach')
    client = _get_lambda_client()
    response = client.invoke(
        FunctionName=function_name,
        Payload=json.dumps({'llm_payload': llm_payload, 'detail_level': detail_level}),
    )
    result = json.loads(response['Payload'].read())

    if not result.get('success'):
        click.echo(f"Error: {result.get('error')}", err=True)
        return

    insight = ActivityInsight(
        activity_id=activity_id,
        user_id=user_id,
        insight_type='ACTIVITY_INSIGHT',
        coach_insight=result['coaching'],
    )
    db.session.add(insight)
    db.session.commit()

    click.echo("\n" + result['coaching'])
    click.echo("\n" + "=" * 80)
    if 'token_usage' in result:
        usage = result['token_usage']
        click.echo(f"Token Usage: {usage['total_tokens']:,} total ({usage['input_tokens']:,} in, {usage['output_tokens']:,} out)")
        cost = (usage['input_tokens'] * 0.003 / 1000) + (usage['output_tokens'] * 0.015 / 1000)
        click.echo(f"Estimated Cost: ${cost:.4f}")
    click.echo("=" * 80)


# --------------------------------------------------------------------------------------
#
#                              DETECT WARMUP
#
# --------------------------------------------------------------------------------------
@admin.command('detect-warmup')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--activity-id', required=True, type=int, help='Activity ID')
@with_appcontext
def detect_warmup_cmd(user_id, activity_id):
    """
    Detect whether an activity contains a warmup period at the start.
    """
    click.echo("=" * 80)
    click.echo(f"DETECT WARMUP - User: {user_id}, Activity: {activity_id}")
    click.echo("=" * 80)

    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        click.echo(f"Error: Activity {activity_id} not found for user {user_id}", err=True)
        return

    from app.models.user import User
    user = User.query.get(user_id)
    if not user or not user.ftp:
        click.echo("Error: User not found or FTP not set", err=True)
        return

    streams = get_activity_streams(user_id, activity_id, stream_types=['watts', 'cadence', 'heartrate'])
    if not streams or 'watts' not in streams:
        click.echo("Error: Power stream not available for this activity", err=True)
        return

    result = detect_warmup(
        power_stream=streams['watts']['data'],
        ftp=float(user.ftp),
        cadence_stream=streams.get('cadence', {}).get('data'),
        hr_stream=streams.get('heartrate', {}).get('data'),
        activity_type=activity.type,
    )

    date_str = activity.start_date_local.strftime('%d %b %Y') if activity.start_date_local else 'unknown'
    duration_s = int(activity.moving_time or 0)
    duration_str = f"{duration_s // 3600}h {(duration_s % 3600) // 60}m"
    click.echo(f"\nActivity:         {activity.name}")
    click.echo(f"Date:             {date_str}")
    click.echo(f"Duration:         {duration_str}")
    click.echo(f"\nWarmup detected:  {result['warmup_detected']}")
    click.echo(f"Confidence:       {result['confidence']:.2f}")
    click.echo(f"Reason:           {result['detection_reason']}")
    if result['warmup_detected']:
        mins = result['warmup_end_s'] // 60
        secs = result['warmup_end_s'] % 60
        click.echo(f"Warmup ends at:   {mins}m {secs}s (index {result['warmup_end_index']})")
    click.echo(f"\nDiagnostics:")
    for k, v in result['diagnostics'].items():
        click.echo(f"  {k}: {v}")
    click.echo("=" * 80)


# --------------------------------------------------------------------------------------
#
#                              ANALYSE ACTIVITY
#
# --------------------------------------------------------------------------------------
@admin.command('analyse-activity')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.argument('activity_id', nargs=-1, type=int, required=True)
@click.option('--mode', type=click.Choice(['structure', 'full', 'llm']), default='structure',
              help='structure: classify only (default); full: classify + extract metrics; llm: full + token-efficient LLM payload')
@click.option('--pretty/--no-pretty', default=True, help='Pretty-print JSON output (default: pretty)')
@click.option('--output-dir', default=None, help='Directory to write output files to')
@with_appcontext
def analyse_activity(user_id, activity_id, mode, pretty, output_dir):
    """
    Analyse one or more activities.

    mode=structure (default): classify workout type, persist to DB.
    mode=full: classify + extract metrics at appropriate frequency, persist to DB.
    """
    import os
    indent = 2 if pretty else None

    for act_id in activity_id:
        click.echo(f"\nAnalysing activity {act_id} (mode={mode})...")

        # analyse the activity
        result = activity_analyser.analyse_activity(user_id, act_id, mode=mode)

        if not result['success']:
            click.echo(f"  Error: {result['error']}", err=True)
            continue
        
        # output to console
        if mode == 'llm':
            click.echo(json.dumps(result['llm_payload'], indent=indent))
        else:
            click.echo(json.dumps(result['console_summary'], indent=indent))
            if mode == 'full' and result.get('metrics'):
                click.echo(json.dumps(result['metrics'], indent=indent))

        # output to file if asked
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            identification = result['identification']
            date_prefix    = identification.get('activity_date', '000000').replace('-', '')[2:]

            if mode == 'llm':
                llm_path = os.path.join(output_dir, f"{date_prefix}_{act_id}_llm_payload.json")
                with open(llm_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(result['llm_payload'], indent=indent))
                click.echo(f"  LLM payload written to {llm_path}", err=True)
            else:
                id_path = os.path.join(output_dir, f"{date_prefix}_{act_id}_identification.json")
                with open(id_path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(identification, indent=indent))
                click.echo(f"  Identification written to {id_path}", err=True)

                if result.get('metrics'):
                    ass_path = os.path.join(output_dir, f"{date_prefix}_{act_id}_metrics.json")
                    with open(ass_path, 'w', encoding='utf-8') as f:
                        f.write(json.dumps(result['metrics'], indent=indent))
                    click.echo(f"  Metrics written to {ass_path}", err=True)
