#!/usr/bin/env python3
"""
Test script to verify Anthropic SDK works in AWS Lambda.
Run this via: cd zappa && zappa invoke dev 'scripts/test_lambda_insights.py' --raw

Or use the shell wrapper: ./scripts/test_lambda_insights.sh
"""

from app import create_app
from app.models.strava import Activity
from app.insights.tools import generate_activity_insights

# Configuration - edit these values
USER_ID = 1
ACTIVITY_ID = 16874273830
DETAIL_LEVEL = 'simple'  # or 'detailed'

# Create Flask app context
app = create_app()

with app.app_context():
    print("=" * 80)
    print(f"Testing Anthropic SDK in Lambda")
    print(f"User ID: {USER_ID}, Activity ID: {ACTIVITY_ID}, Detail: {DETAIL_LEVEL}")
    print("=" * 80)

    # Fetch activity
    activity = Activity.query.filter_by(id=ACTIVITY_ID, user_id=USER_ID).first()
    if not activity:
        print(f"ERROR: Activity {ACTIVITY_ID} not found for user {USER_ID}")
        exit(1)

    print(f"Found activity: {activity.name}")
    print(f"Date: {activity.start_date_local}")
    print("-" * 80)

    # Generate insights
    result = generate_activity_insights(activity, is_admin=True, detail_level=DETAIL_LEVEL)

    if result['success']:
        print("\nINSIGHTS:")
        print(result['insights'])
        print("\n" + "=" * 80)
        if 'token_usage' in result:
            usage = result['token_usage']
            print(f"Token Usage: {usage['total_tokens']:,} total ({usage['input_tokens']:,} in, {usage['output_tokens']:,} out)")
        print("=" * 80)
        print("✓ SUCCESS - Anthropic SDK is working in Lambda!")
    else:
        print(f"✗ FAILED: {result['error']}")
        exit(1)
