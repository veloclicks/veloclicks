# Domain Model

## Core Concepts

**Activity**
A recorded cycling session imported from Strava containing metadata, timestamps, distance, duration, power, heart rate, cadence, elevation, and stream data.

**Athlete**
The rider whose data is being analysed, with threshold values (FTP, max HR) and profile information.

**FTP (Functional Threshold Power)**
The power output sustainable for approximately one hour. Used as the anchor for intensity normalisation and zone-based reasoning.

**Zones**
Intensity bands relative to FTP or heart rate, used to categorise and interpret workouts.

**Workout**
A cycling session with identifiable training intent. May be structured (programmed intervals) or inferred (detected patterns in outdoor rides).

**Classification**
Session type determined by intensity distribution and patterns: endurance, threshold, VO2-oriented, mixed, race-like, or unstructured intervals.

## Analysis Output

**Deterministic Findings**
Structured conclusions derived from explicit logic: interval count and duration, intensity relative to FTP, warmup/warmdown presence, time-in-zone, classification.

**Narrative Assessment**
Human-readable coaching interpretation generated from deterministic findings, including execution quality, training stimulus assessment, and commentary.

**Confidence**
Measure of how strongly a finding or classification is supported by available data.

## Heart Rate Zones

Heart rate zones are intensity bands relative to maximum heart rate, used for training prescription and workout classification.

### 5-Zone Model
- **Zone 1 (Recovery)**: <60% max HR — Very light effort, recovery rides
- **Zone 2 (Endurance)**: 60-70% max HR — Sustainable aerobic work, base building
- **Zone 3 (Tempo)**: 70-80% max HR — Steady work, muscular endurance
- **Zone 4 (Threshold)**: 80-90% max HR — Hard sustained effort, lactate threshold
- **Zone 5 (VO2max)**: 90-100% max HR — Very hard, maximum aerobic power

## Power Zones

Power zones are intensity bands normalized to Functional Threshold Power (FTP), providing objective, physiologically-grounded intensity classification independent of fitness level or heart rate variability.

### 7-Zone Model
- **Zone 1 (Active Recovery)**: <55% FTP — Very light pedaling, recovery between hard efforts
- **Zone 2 (Endurance)**: 55-75% FTP — Sustainable aerobic work, long steady rides
- **Zone 3 (Tempo)**: 75-90% FTP — Moderately hard sustained effort, muscular endurance
- **Zone 4 (Threshold)**: 90-105% FTP — Hard effort at or near lactate threshold, 40min-1hr efforts
- **Zone 5a (VO2max)**: 105-120% FTP — Hard interval work, 3-8min efforts, aerobic power development
- **Zone 5b (Anaerobic)**: 120-150% FTP — Very hard short intervals, 30sec-3min, anaerobic capacity
- **Zone 6 (Neuromuscular Power)**: 150%+ FTP — Maximal sprints and explosive efforts, <30sec

## Zone Usage in Analysis

Zones are used throughout the analysis pipeline for:
- Classifying workout intensity distribution
- Quantifying training stimulus
- Detecting structured intervals and efforts
- Comparing training sessions to athlete goals and periodization plans