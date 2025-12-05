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
"""

import click
import logging
import json
from flask.cli import with_appcontext
from datetime import datetime
from sqlalchemy import extract

from app.models import db
from app.models.strava import Activity
from app.strava.activity_utils import calculate_tss, calculate_power_metrics

logger = logging.getLogger(__name__)



@click.group()
def admin():
    """Administrative batch operations."""
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

    # Query user
    user = User.query.filter_by(email=username).first()

    if not user:
        click.echo(f"User not found: '{username}'", err=True)
        return

    # Display user information
    click.echo("=" * 80)
    click.echo("USER INFORMATION")
    click.echo("=" * 80)
    click.echo(f"ID:               {user.id}")
    click.echo(f"Email:            {user.email}")
    click.echo(f"First Name:       {user.firstname or 'Not set'}")
    click.echo(f"Last Name:        {user.lastname or 'Not set'}")
    click.echo(f"Membership Type:  {user.membership_type or 'Not set'}")
    click.echo(f"Sex:              {user.sex or 'Not set'}")
    click.echo(f"Date of Birth:    {user.date_of_birth.strftime('%Y-%m-%d') if user.date_of_birth else 'Not set'}")
    click.echo(f"FTP:              {user.ftp or 'Not set'}")
    click.echo(f"Max Heart Rate:   {user.max_heart_rate or 'Not set'}")
    click.echo(f"Resting HR:       {user.resting_heart_rate or 'Not set'}")
    #click.echo(f"Created:          {user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else 'Unknown'}")
    
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
@click.option('--skip-existing', is_flag=True, default=False, help='Skip activities that already have power metrics')
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
@click.option('--skip-existing', is_flag=True, default=False, help='Skip activities that already have TSS calculated')
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
