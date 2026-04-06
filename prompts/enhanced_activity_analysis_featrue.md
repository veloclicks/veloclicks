Feature Spec: Enhanced Ride Analysis Payload for Coaching / LAG Interpretation

Goal
Improve the ride-analysis API payload so workouts and endurance rides can be compared accurately over time for:
- pacing
- durability
- climbing behaviour
- cadence strategy
- power curve progression
- time-in-zone distribution

Problem
The current payload is too limited for robust analysis because:
- time-series entries do not contain a real elapsed time axis (`t_min` is always 0)
- there is no cadence, elevation, speed, or gradient per point
- there are no max values per segment
- there is no time-in-zone summary
- there is no power-curve summary
- there is no structured split analysis (first half vs second half, climbs vs flats, etc.)

Requirements

1) Add proper time-series data
For each sampled point in the ride, include:
- `t_s` or `elapsed_s`
- `power_w`
- `hr_bpm`
- `cadence_rpm`
- `speed_kph`
- `elevation_m`
- `gradient_pct` (if derivable from GPS/elevation)

Implementation note:
- Downsample to every 15s or 30s to control payload size.

Example:
{
  "time_series": [
    {
      "t_s": 0,
      "power_w": 142,
      "hr_bpm": 118,
      "cadence_rpm": 86,
      "speed_kph": 28.4,
      "elevation_m": 42.1,
      "gradient_pct": 0.3
    }
  ]
}

2) Add segment / split summaries
Include structured summaries for:
- first half vs second half
- first hour / middle / last hour
- quartiles by elapsed time
- detected climb segments
- detected flat segments

For each segment include:
- duration_s
- distance_km
- avg_power_w
- normalized_power_w
- max_power_w
- avg_hr_bpm
- max_hr_bpm
- avg_cadence_rpm
- max_cadence_rpm
- avg_speed_kph
- max_speed_kph
- elevation_gain_m
- avg_gradient_pct (for climbs)

Example:
{
  "segment_summaries": {
    "first_half": {
      "duration_s": 6500,
      "distance_km": 52.1,
      "avg_power_w": 138,
      "normalized_power_w": 145,
      "max_power_w": 412,
      "avg_hr_bpm": 123,
      "max_hr_bpm": 144,
      "avg_cadence_rpm": 84,
      "max_cadence_rpm": 108,
      "avg_speed_kph": 26.7,
      "max_speed_kph": 48.3,
      "elevation_gain_m": 210
    }
  }
}

3) Add whole-ride summary metrics
Add:
- `avg_power_w`
- `normalized_power_w`
- `max_power_w`
- `avg_hr_bpm`
- `max_hr_bpm`
- `avg_cadence_rpm`
- `max_cadence_rpm`
- `avg_speed_kph`
- `max_speed_kph`
- `elevation_gain_m`
- `variability_index`
- `intensity_factor`
- `pw_hr_decoupling_pct` (if computable)
- `tss`

Example:
{
  "whole_ride_metrics": {
    "avg_power_w": 132,
    "normalized_power_w": 145,
    "max_power_w": 511,
    "avg_hr_bpm": 122,
    "max_hr_bpm": 151,
    "avg_cadence_rpm": 84,
    "max_cadence_rpm": 111,
    "avg_speed_kph": 26.3,
    "max_speed_kph": 55.8,
    "elevation_gain_m": 480,
    "variability_index": 1.10,
    "intensity_factor": 0.68,
    "pw_hr_decoupling_pct": 4.2,
    "tss": 168.5
  }
}

4) Add time in zone
Add time and percentage in:
- power zones
- HR zones
- optional cadence bands

Example:
{
  "time_in_power_zones": {
    "z1_s": 1800,
    "z2_s": 7200,
    "z3_s": 2100,
    "z4_s": 600,
    "z5_s": 300
  },
  "time_in_power_zones_pct": {
    "z1_pct": 15.0,
    "z2_pct": 60.0,
    "z3_pct": 17.5,
    "z4_pct": 5.0,
    "z5_pct": 2.5
  },
  "time_in_hr_zones": {
    "z1_s": 900,
    "z2_s": 7800,
    "z3_s": 2400,
    "z4_s": 900
  }
}

5) Add power curve / best efforts
Include best rolling average powers for:
- 15s
- 30s
- 1min
- 3min
- 5min
- 10min
- 20min
- 30min
- 60min

Optional:
- `wkg` values if athlete weight is known

Example:
{
  "power_curve": {
    "15s_w": 720,
    "30s_w": 510,
    "1min_w": 340,
    "3min_w": 275,
    "5min_w": 248,
    "10min_w": 225,
    "20min_w": 205,
    "30min_w": 196,
    "60min_w": 184
  }
}

6) Add climb detection
Detect climb segments using elevation/GPS and include:
- `start_s`
- `end_s`
- `duration_s`
- `distance_km`
- `elevation_gain_m`
- `avg_gradient_pct`
- `avg_power_w`
- `normalized_power_w`
- `avg_hr_bpm`
- `avg_cadence_rpm`
- `avg_speed_kph`

Example:
{
  "climbs": [
    {
      "name": "Unnamed climb 1",
      "start_s": 4120,
      "end_s": 5980,
      "duration_s": 1860,
      "distance_km": 8.2,
      "elevation_gain_m": 410,
      "avg_gradient_pct": 5.0,
      "avg_power_w": 198,
      "normalized_power_w": 204,
      "avg_hr_bpm": 148,
      "avg_cadence_rpm": 78,
      "avg_speed_kph": 15.9
    }
  ]
}

7) Add stoppage / anomaly markers
Detect and annotate:
- pauses/stops
- off-route slow sections
- prolonged zero-power sections
- unusual surges late in ride

Example:
{
  "events": [
    {
      "type": "pause",
      "start_s": 7200,
      "end_s": 7440,
      "duration_s": 240
    },
    {
      "type": "late_surge",
      "start_s": 11800,
      "end_s": 12120,
      "duration_s": 320,
      "avg_power_w": 236
    }
  ]
}

8) Preserve backward compatibility
Do not remove existing summary fields.
Add new top-level sections:
- `time_series`
- `segment_summaries`
- `whole_ride_metrics`
- `time_in_power_zones`
- `time_in_power_zones_pct`
- `time_in_hr_zones`
- `power_curve`
- `climbs`
- `events`

Acceptance Criteria
The payload should allow a coaching/LLM layer to:
- compare two endurance rides meaningfully
- assess pacing drift and decoupling
- compare first half vs second half
- separate flats from climbs
- identify late-ride surges
- analyse cadence behaviour under fatigue
- compare weekly and monthly progression
- reason about whether a ride was true Z2, upper Z2, tempo, or stochastic

Nice-to-Have
- derive `pw_hr_decoupling_pct` automatically
- derive `durability_score`
- expose fueling annotations later
- optionally include route-normalized comparison segments for repeat routes
