# August 2026

# Overview
## Veloclicks purpose
- Veloclicks is a hobby project that Patrick has been working on over the years to build a sports data analytics platform. Essentially, registered users who are assumed to be keen cyclists with strava accounts, can use the platform to retrieve and analyse their cycling activities from strava. Typical metrics retrieved include time, duration, distance, speed, heart rate, power.
- Veloclicks provides an easier and more powerful interface for athletes to view their activities
- Veloclicks also provides some AI-enabled features including LLM feedback on activities

## Features
- Authentication
- Strava authentication
- Import strava activities
- Search activities
- Activity Detail
- Power analysis
- AI review of activity
- CLI interfaces

## Technology Stack

### Application
- Front End : Next.js integrates with the flask solely through API calls
- Core/Business : Python and Flask, exposes APIs to the front end
- Database : Postgres with SQLAlchemy ORM

### Platform
#### Local Env
- Docker container in development

### Production Environment
- Front End deployed to Vercel — `https://veloclicks-prod.vercel.app`
- Zappa wrapper in production deployed to AWS lambda (covers the core Flask app only)
- AI coach is a separate AWS Lambda (`veloclicks-coach`), deployed independently via AWS SAM (`aws/lambdas/template.yaml`) and invoked from Flask over boto3 — not part of the Zappa deployment
- Auth is mid-migration from Flask routes to a dedicated `veloclicks-auth` Lambda (`aws/lambdas/auth/`, also SAM-deployed). Flask still serves `/register` and `/login` directly for now — not yet cut over

## Key Folders
- flask <-- has all python code organised into modules
- frontend <-- next.js front end
- aws/lambda_layers <-- Contains libs that can be deployed to AWS to reduce lambda size
- aws/lambdas <-- Has some lambdas as Patrick migrates towards that

# Project Rules

Migrated from a legacy `.claudecode/prompts.md` (not read by current tooling — folded in here 2026-08-29 so it's actually honored).

- **Frontend never accesses the database directly.** Always through Flask's API, or the auth lambda's own API for login. This is an app architecture rule, not a restriction on debugging — direct `psql`/`docker exec` DB inspection during development is fine and expected.
- **Explain reasoning before showing code or making changes.**
- **Keep it simple.** Only implement exactly what's requested — no unrequested validation, error handling, or "improvements." Don't over-engineer or design for hypothetical future requirements.
- **Flask container commands run via Docker exec** — container name `vc_flask`, e.g. `docker exec vc_flask flask admin list-activities --user-id 1 --year 2024 --month 11`.
- **Never include Claude/AI attribution in commit messages.** No "🤖 Generated with Claude Code" line, no "Co-Authored-By: Claude" trailer. This overrides the default commit template.

# Backlog

Agreed order of work, 2026-03-25, with Patrick's current priorities (Aug 2026) placed at the top. Push back if Patrick goes off-piste. (Re-verify against current code before treating as current state — most of this list is from March and hasn't been fully re-checked since.)

## Priorities (current)
1. Move to more lambdas to reduce startup time, cost and increase responsiveness for prod
2. Move away from Zappa in production because it is too error prone — prefer Lambda as much as possible, but wary of breaking everything
3. Improve activity page features — showing a proper power graph
4. Expose data as an MCP server
5. Switch local lambda dev/test to `sam local start-api` / `sam local invoke` (reading `aws/lambdas/template.yaml`) instead of the current Docker Compose + hand-rolled `local_server.py` shim for auth. **Flagged: this is a best-practice/consistency improvement, not a pragmatic necessity** — the current setup works and lets everything come up with one `docker compose up`. The real risk it addresses is drift: `local_server.py` hand-builds the API Gateway event shape, and if that drifts from what API Gateway actually sends, bugs only surface after deploying to prod.

## Housekeeping
6. ✅ Remove Celery — strip `celery_init_app()`, `test_broker_connection()`, dead files
7. ✅ Persist activity coach feedback — `ActivityInsight` model, cached on first call, returned on subsequent calls
8. Warmup detector: monotonic power signal — if detected intervals have monotonically increasing power across reps, treat as warmup steps not main set. More principled than current rest-valley proxies.

## AI Coach — Core Features (MVP)
9. AI Coach - Create training plan — objectives, phases, weeks, target sessions; set via coach prompts
10. AI Coach - Activity insight against plan — every activity assessed against the plan + recent history, not just in isolation
11. AI Coach - Workout recommendation — "next session" suggestion based on how today went vs the plan

## Onboarding / Registration
12. Strava-first registration — replace Register with "Analyse with Strava" → OAuth → pull profile, registration becomes "just add a password"
13. Background activity sync on register — after OAuth, pull last 10-15 activities in the background so user lands in a populated dashboard
14. Background activity sync on login — on each login, sync any new activities since last sync in the background

## General
15. UI polish — easier navigation, activity detail page improvements

## Analytics — Future
16. Climb detection — detect sustained positive-gradient segments from the elevation/GPS stream and attach per-climb metrics (start/end time, duration, distance, elevation gain, avg gradient, avg power, NP, avg HR, avg cadence, avg speed) to the activity payload. Goal: let the coach separate climbing performance from flat riding, track climbing fitness over time, and flag pacing differences on climbs vs flats.
17. Force-recompute analytics via API — add `?force=true` query param to `GET /ai-coach/activity/<id>/summary` that clears cached `ActivityAnalytics` fields (`power_curve_data`, `time_in_zones`) and recomputes everything fresh. Useful after algorithm changes without needing CLI access.
18. Stoppage and anomaly markers — detect and annotate pauses (extended zero/near-zero power), prolonged coasting sections, and late-ride surges in the activity payload. Scope to pauses and zero-power runs first; late surges (sustained above-average power in final 20% of ride) as a second pass. Goal: prevent pauses from skewing pacing/decoupling metrics and let the coach flag unusual effort distribution.
