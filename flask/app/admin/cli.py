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

    # Generate activity report
    docker compose exec flask flask admin activity-report --user-id 1 --activity-id 12345678

    # Analyse interval session structure
    docker compose exec flask flask admin session-structure --user-id 1 --activity-id 12345678
"""

import click
import logging
import json
from flask.cli import with_appcontext
from datetime import datetime
from sqlalchemy import extract

from app.models import db
from app.models.strava import Activity
from app.analytics.activity_tss import calculate_tss
from app.analytics.activity_power import calculate_power_metrics
from app.analytics.activity_report import generate_activity_report_json, analyse_session_structure
from app.profile.tools import get_profile
from app.insights.tools import generate_activity_insights

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
      activity-insights    Generate AI-powered insights for an activity
      activity-report      Generate a JSON activity report with interval data
      session-structure    Analyse whether an activity is a structured interval session

    Use 'flask admin COMMAND --help' for detailed help on each command.
    """
    pass


# --------------------------------------------------------------------------------------
# 
#                                  USER INFO
#
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
    profile = get_profile(user.id)

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
    activities = get_activities_by_period(user_id, year, month)

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
        if activity.power_curve_data:
            try:
                power_data = json.loads(activity.power_curve_data)
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
    activities_with_power_curve = sum(1 for a in activities if a.power_curve_data and len(a.power_curve_data) > 2)

    click.echo(f"With TSS: {activities_with_tss} | With NP: {activities_with_np} | With Power Curve: {activities_with_power_curve}")
    click.echo("=" * 140)


# --------------------------------------------------------------------------------------
#
#                         GET ACTVITIES IN BATCHES
#
# --------------------------------------------------------------------------------------
def get_activities_by_period(user_id: int, year: int, month: int = None):
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
# 
#                          CALCULATE POWER AND TSS METRICS IN BATCH
#
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
    activities = get_activities_by_period(user_id, year, month)

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
        has_power_data = activity.power_curve_data or activity.time_in_zones
        if skip_existing and has_power_data:
            click.echo("  [Power] Skipping (already calculated)")
            power_skipped += 1
        else:
            try:
                result = calculate_power_metrics(user_id, activity.id)
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
                tss = calculate_tss(user_id, activity.id)
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
# 
#                                     POWER
#
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

    activities = get_activities_by_period(user_id, year, month)

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

        has_power_data = activity.power_curve_data or activity.time_in_zones
        if skip_existing and has_power_data:
            click.echo("  Skipping (already calculated)")
            skipped += 1
            continue

        try:
            result = calculate_power_metrics(user_id, activity.id)
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

    activities = get_activities_by_period(user_id, year, month)

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
            tss = calculate_tss(user_id, activity.id)
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
@admin.command('activity-insights')
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

    # Fetch activity
    activity = Activity.query.filter_by(id=activity_id, user_id=user_id).first()
    if not activity:
        click.echo(f"Error: Activity {activity_id} not found for user {user_id}", err=True)
        return

    # Generate insights (CLI runs with admin override)
    print(f"--------> activity_insights generating insights for: {activity_id} with detail_level={detail_level}")
    result = generate_activity_insights(activity, is_admin=True, detail_level=detail_level)

    if result['success']:
        click.echo("\n" + result['insights'])
        click.echo("\n" + "=" * 80)
        if 'token_usage' in result:
            usage = result['token_usage']
            click.echo(f"Token Usage: {usage['total_tokens']:,} total ({usage['input_tokens']:,} in, {usage['output_tokens']:,} out)")
            # Rough cost estimate (as of 2024 pricing)
            cost = (usage['input_tokens'] * 0.003 / 1000) + (usage['output_tokens'] * 0.015 / 1000)
            click.echo(f"Estimated Cost: ${cost:.4f}")
        click.echo("=" * 80)
    else:
        click.echo(f"Error: {result['error']}", err=True)


# --------------------------------------------------------------------------------------
#
#                                  ACTIVITY REPORT
#
# --------------------------------------------------------------------------------------
@admin.command('activity-report')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--activity-id', required=True, type=int, help='Activity ID')
@click.option('--pretty/--no-pretty', default=True, help='Pretty-print JSON output (default: pretty)')
@click.option('--output-dir', default=None, help='Directory to write <activity_id>.json to')
@with_appcontext
def activity_report(user_id, activity_id, pretty, output_dir):
    """
    Generate a JSON activity report with interval and summary data.
    """
    click.echo(f"Generating activity report for user {user_id}, activity {activity_id}...")

    result = generate_activity_report_json(user_id, activity_id, pretty=pretty, output_dir=output_dir)

    if not result:
        click.echo(f"Error: Failed to generate report for activity {activity_id}", err=True)
        return

    click.echo(result)


# --------------------------------------------------------------------------------------
#
#                              SESSION STRUCTURE ANALYSIS
#
# --------------------------------------------------------------------------------------
@admin.command('session-structure')
@click.option('--user-id', required=True, type=int, help='User ID')
@click.option('--activity-id', required=True, type=int, help='Activity ID')
@click.option('--pretty/--no-pretty', default=True, help='Pretty-print JSON output (default: pretty)')
@click.option('--output-dir', default=None, help='Directory to write <activity_id>.json to')
@with_appcontext
def session_structure(user_id, activity_id, pretty, output_dir):
    """
    Analyse whether an activity is a structured interval session and characterise its structure.
    """
    click.echo(f"Analysing session structure for user {user_id}, activity {activity_id}...")

    result = analyse_session_structure(user_id, activity_id, pretty=pretty, output_dir=output_dir)

    if not result:
        click.echo(f"Error: Failed to analyse session structure for activity {activity_id}", err=True)
        return

    click.echo(result)
