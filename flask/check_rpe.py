#!/usr/bin/env python3
"""Quick script to check if RPE values were saved"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.models import db
from app.models.strava import Activity
from app import create_app

# Create app context
app = create_app()

with app.app_context():
    # Get recent activities with RPE values
    activities_with_rpe = Activity.query.filter(
        Activity.rpe.isnot(None)
    ).order_by(Activity.start_date_local.desc()).limit(10).all()

    print(f"\n{'='*80}")
    print(f"Activities with RPE values (last 10):")
    print(f"{'='*80}")

    if not activities_with_rpe:
        print("No activities found with RPE values set.")
    else:
        for activity in activities_with_rpe:
            date_str = activity.start_date_local.strftime('%Y-%m-%d') if activity.start_date_local else 'N/A'
            print(f"ID: {activity.id:12} | Date: {date_str} | Name: {activity.name[:40]:40} | RPE: {activity.rpe}")

    print(f"{'='*80}\n")

    # Count total activities with RPE
    total_with_rpe = Activity.query.filter(Activity.rpe.isnot(None)).count()
    total_activities = Activity.query.count()

    print(f"Total activities with RPE: {total_with_rpe}/{total_activities}")
    print(f"Percentage: {(total_with_rpe/total_activities*100) if total_activities > 0 else 0:.1f}%\n")
