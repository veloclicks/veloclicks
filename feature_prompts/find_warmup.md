Feature: detect_warmup(activity)

Purpose
Detect whether an activity contains a warmup period at the start, and if so return the end of the warmup and a confidence score.

This function is intended to prevent warmup data from contaminating analysis of the main workout set.

Inputs
- power stream in seconds or regularly sampled time series
- optional cadence stream
- optional heart rate stream
- athlete FTP in watts
- activity type, if available (e.g. indoor / outdoor / virtual / ride)
- optional precomputed classification if already known

Assumptions
- If a warmup exists, it is always at the start of the activity.
- The function should not try to detect warmups in the middle of the ride.
- The output should be conservative: it is better to return "no warmup detected" than to cut off the first true work interval.
- The function should work for indoor and outdoor rides, but indoor workouts should be treated as much more likely to contain a structured warmup.
- Endurance rides usually do not have a meaningful warmup that should be removed from analysis.

Output
Return an object with:
- warmup_detected: boolean
- warmup_end_index: integer or null
- warmup_end_s: integer or null
- confidence: float between 0 and 1
- detection_reason: short string
- diagnostics: object with intermediate metrics used in scoring

Example output:
{
  "warmup_detected": true,
  "warmup_end_index": 780,
  "warmup_end_s": 780,
  "confidence": 0.87,
  "detection_reason": "structured low-to-rising opening segment before repeated main-set intervals",
  "diagnostics": {
    "first_high_intensity_s": 820,
    "opening_mean_pct_ftp": 0.63,
    "opening_trend": "rising",
    "main_set_repeatability_score": 0.91,
    "post_warmup_drop_detected": true
  }
}

Definitions

1. Endurance ride
An activity should be treated as likely endurance if:
- at least 85 to 90 percent of the total duration is at or below 0.60 FTP, and
- there is no repeated interval structure, and
- there is no sustained block above threshold or repeated work/recovery alternation

For likely endurance rides, default to:
- warmup_detected = false
unless there is extremely strong evidence of a structured warmup followed by a distinct main set.

2. Warmup candidate
A warmup candidate is a segment from the start of the ride that has some or all of these properties:
- relatively low average intensity compared with the later main set
- increasing power trend overall, either ramped or stepped
- low to moderate repeatability
- may contain short openers or brief surges
- ends before the first repeated main set structure begins

3. Main set onset
The main set onset is the earliest point at which one of the following appears:
- at least 3 repeated work intervals of similar duration and similar intensity separated by recoveries, or
- a sustained work block clearly distinct from the opening segment, or
- a stable structured pattern that is more regular and higher intensity than the opening segment

Preprocessing
Before detection:
- smooth power using a rolling mean of 5 to 10 seconds
- express power relative to FTP as pct_ftp = power / ftp
- optionally collapse very short spikes under 10 to 15 seconds so they do not dominate segmentation
- optionally build coarse segments from the smoothed power stream using thresholding, change point detection, or simple plateau detection

Detection strategy
The function should not try to classify the whole ride at once.
Instead:
1. Determine whether the ride is likely endurance.
2. If not endurance, search for the start of the main set.
3. If a main set is found and the opening segment before it looks like a warmup, return that boundary as warmup_end.
4. Otherwise return no warmup.

Scoring signals

A. Signals that increase warmup likelihood
- opening segment average intensity is low to moderate, typically below 0.75 FTP
- opening segment has an upward trend in power
- opening segment looks ramped or stepped
- first repeated main-set pattern starts after the opening segment
- there is a drop or reset in power immediately before the main set starts
- indoor / virtual ride flag is true
- work interval repeatability after the opening segment is high
- the first 8 to 15 minutes differ structurally from the next block

B. Signals that decrease warmup likelihood
- ride is likely endurance
- the first hard interval starts almost immediately
- there is no structural change between opening period and rest of ride
- the whole activity is uniformly stochastic
- there is no repeatable main set after the opening segment
- proposed warmup would remove a true first interval

Indoor vs outdoor guidance
Indoor / virtual rides:
- warmup is common
- search strongly in first 10 to 15 minutes
- ramped and stepped openings are common
- short above-FTP openers may still belong to the warmup if they occur before the main set starts

Outdoor rides:
- warmup is less structured and less common
- do not remove early easy riding unless there is clear evidence of a later structured main set
- be more conservative
- if the ride is stochastic and no clean main set appears, return no warmup

Warmup patterns to recognise

Pattern 1: stepped warmup
Typical example:
- 3 to 5 min around 45 to 60% FTP
- then 2 to 5 min around 60 to 75% FTP
- optionally 30 to 90 sec at or above FTP
- possibly followed by easy spinning
- then main set begins

Pattern 2: ramped warmup
Typical example:
- starts easy
- gradually rises over 5 to 15 min
- may approach FTP or slightly above near the end
- often followed by a reset or short easier section before the main set

Pattern 3: warmup with openers
Typical example:
- easy to moderate start
- 1 to 3 short high-power efforts
- these should still count as warmup if they are not yet part of a repeated interval structure

Main set detection rules

A repeated interval main set may be declared if all or most of these are true:
- at least 3 work bouts
- work bouts are above a meaningful intensity threshold for the workout type
- work durations are similar within a tolerance of about 20 percent
- work powers are similar within a tolerance of about 5 to 10 percent
- recoveries between them are present and somewhat consistent
- the pattern is more regular than the opening segment

A sustained main set may be declared if:
- after the opening segment, there is a long steady block at distinctly higher intensity than the opening segment
- the block is long enough to plausibly be the target work, e.g. threshold / tempo
- the opening segment appears preparatory rather than part of that sustained block

Conservative guard rails
Never detect a warmup if any of these are true:
- proposed warmup is longer than 20 minutes unless confidence is very high
- proposed warmup consumes more than 35 percent of total activity duration
- first true repeated interval appears before minute 4
- ride is classified as endurance and no later structured set exists
- confidence is below a minimum threshold, e.g. 0.60

Suggested thresholds
These are defaults and should be configurable:
- smooth_window_s = 5 to 10
- endurance_pct_ftp_threshold = 0.60
- endurance_fraction_threshold = 0.85
- candidate_warmup_max_duration_s = 1200
- indoor_search_window_s = 900
- minimum_repeated_intervals = 3
- interval_duration_tolerance = 0.20
- interval_power_tolerance = 0.08
- minimum_confidence_to_accept = 0.60

Recommended algorithm
1. Smooth power.
2. Convert to percent FTP.
3. Check likely endurance:
   - if >85 to 90 percent of time is <=0.60 FTP and no repeated intervals, return no warmup.
4. Search the first 10 to 15 minutes for candidate warmup end points.
5. For each candidate end point:
   - score opening segment for warmup characteristics:
     - low/moderate intensity
     - rising trend
     - stepped/ramped shape
   - score following segment for main set characteristics:
     - repeated intervals or distinct sustained block
     - higher regularity than opening
   - apply penalties if the cut would remove a likely true work interval
6. Select the highest scoring candidate.
7. If score exceeds threshold, return that as warmup_end.
8. Otherwise return no warmup.

Implementation guidance
The function should be deterministic.
Do not use an LLM.
Do not rely on textual ride titles.
Use only metrics derived from the activity streams and metadata.

Diagnostics to expose
To make debugging easier, include:
- opening_mean_pct_ftp
- opening_max_pct_ftp
- opening_trend_slope
- candidate_count
- best_candidate_end_s
- best_candidate_score
- repeated_interval_count_after_candidate
- post_candidate_repeatability_score
- endurance_likelihood_score
- reason codes

Testing requirements
Implement unit tests for at least these cases:

1. Indoor VO2 session with 10 min stepped warmup
Expected: warmup detected

2. Indoor threshold session with ramp warmup and short opener
Expected: warmup detected

3. Outdoor endurance ride with easy first 12 min
Expected: no warmup detected

4. Outdoor ride with easy roll-out followed by clear hill repeats
Expected: warmup detected only if later repeats are very clear

5. Indoor workout with first interval beginning very early
Expected: no warmup or only very short warmup

6. Ride with no clear main set and stochastic power
Expected: no warmup detected

7. Warmup containing one or two short surges
Expected: still detect warmup if repeated main set starts later

8. False-positive protection case where first hard interval is the workout
Expected: do not remove it

Design preference
Prefer a scoring-based approach over brittle if/else only logic.
The code should be modular, with helper functions such as:
- is_likely_endurance(...)
- find_main_set_candidates(...)
- score_warmup_candidate(...)
- detect_repeated_intervals(...)
- detect_sustained_main_block(...)

Final requirement
The function should optimise for protecting main-set analysis from warmup contamination while minimising false removal of true work intervals.