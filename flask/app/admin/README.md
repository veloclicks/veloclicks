# Admin CLI Commands

Administrative CLI commands for batch processing and data operations.

## Prerequisites

The Flask app must be running in Docker:
```bash
docker compose up
```

## Available Commands

### User Information

Display user details by username (email):

```bash
docker compose exec app flask admin user-info --username patrick@veloclicks.com
```

**Output includes:**
- User ID, email, name
- Membership type
- Personal info (sex, date of birth)
- Training metrics (FTP, max/resting heart rate)
- Strava connection status
- Activity count and most recent activity
- **Password is NOT displayed**

### List Activities

List all activities for a user in a specific month with key metrics:

```bash
# List activities for November 2024
docker compose exec app flask admin list-activities --user-id 1 --year 2024 --month 11
```

**Output includes:**
- Activity ID, Date, Name
- Duration (HH:MM:SS)
- TSS (Training Stress Score)
- NP (Normalized Power / Weighted Average Watts)
- Whether power curve data exists
- Summary statistics

**Note:** Year must be 2018 or later.

### Calculate All Metrics

Calculate power metrics (power curve + distribution) and TSS for activities by month/year:

```bash
# For a specific month
docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024 --month 11

# For an entire year
docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024

# Skip activities that already have metrics
docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024 --skip-existing
```

### Calculate Power Metrics Only

Calculate only power curve and power distribution:

```bash
# For a specific month
docker compose exec app flask admin calculate-power --user-id 1 --year 2024 --month 11

# For an entire year
docker compose exec app flask admin calculate-power --user-id 1 --year 2024

# Skip activities that already have power metrics
docker compose exec app flask admin calculate-power --user-id 1 --year 2024 --skip-existing
```

### Calculate TSS Only

Calculate only Training Stress Score (TSS):

```bash
# For a specific month
docker compose exec app flask admin calculate-tss --user-id 1 --year 2024 --month 11

# For an entire year
docker compose exec app flask admin calculate-tss --user-id 1 --year 2024

# Skip activities that already have TSS
docker compose exec app flask admin calculate-tss --user-id 1 --year 2024 --skip-existing
```

## Command Options

### Common Options

- `--user-id` (required): User ID to process activities for
- `--year` (required): Year to process (e.g., 2024)
- `--month` (optional): Specific month to process (1-12). If omitted, processes entire year
- `--skip-existing` (flag): Skip activities that already have calculated metrics

## Output

Each command provides detailed progress output:

```
Starting metrics calculation for user 1, period: 2024-11
--------------------------------------------------------------------------------
Found 15 activities
--------------------------------------------------------------------------------

Activity 16600225412 (2024-11-15): Morning Ride
  [Power] ✓ Calculated
    - Power curve: 7200 data points
    - Time in zones: 7 zones
  [TSS] ✓ Calculated: 145.3

Activity 16589423801 (2024-11-14): Evening Ride
  [Power] No power data available
  [TSS] ✓ Calculated: 78.5

...

================================================================================
SUMMARY
================================================================================
Total activities processed: 15

Power Metrics:
  Success: 12
  Skipped: 2
  Failed:  1

TSS:
  Success: 14
  Skipped: 1
  Failed:  0
================================================================================
```

## Examples

### Backfill all metrics for 2024
```bash
docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024
```

### Process only November 2024, skip existing
```bash
docker compose exec app flask admin calculate-metrics --user-id 1 --year 2024 --month 11 --skip-existing
```

### Calculate only power metrics for Q4 2024
```bash
for month in 10 11 12; do
  docker compose exec app flask admin calculate-power --user-id 1 --year 2024 --month $month
done
```

### Calculate TSS for multiple users
```bash
for user_id in 1 2 3; do
  docker compose exec app flask admin calculate-tss --user-id $user_id --year 2024
done
```

## Troubleshooting

### Container not running
```bash
docker compose up -d
```

### Check logs for errors
```bash
docker compose logs -f app
```

### Database connection issues
Ensure the database is running and accessible:
```bash
docker compose ps
```

### No activities found
Verify the user has activities in the specified period:
```bash
docker compose exec app flask shell
>>> from app.models.strava import Activity
>>> Activity.query.filter_by(user_id=1).count()
```

## Notes

- These commands query activities by `start_date_local` (local activity time)
- Activities are processed in chronological order (oldest first)
- Each calculation saves results to the database immediately
- Failed calculations are logged but don't stop processing of other activities
- Power metrics require power data from Strava streams
- TSS calculation requires heart rate data and user's max/resting heart rate settings
