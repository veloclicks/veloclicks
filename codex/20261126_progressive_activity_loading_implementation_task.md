# Task: Complete progressive activity loading

**Date:** 26 November 2026
**Status:** Ready for implementation
**Target:** main

## Objective and authoritative inputs

Complete the implementation of all four business scenarios and FR01–FR14 in:
- [Functional specification](../delivery/functional_spec/activity_loading_functional_specification.md)
- [Architecture principles](../delivery/architecture/principles.md)
- [Application architecture](../delivery/architecture/application_architecture.md)
- [Architecture decisions](../delivery/architecture/decisions.md)

Read these documents and inspect the current repository before editing. Do not silently change agreed requirements. The owner has authorised implementation on main, but will perform production deployment separately.

## Starting point

Commit dba07543ff2a64701e1edb8aa5d98d4f7c61bd35 adds the SyncHistory ORM model, Alembic migration c4a8d1e7b920, pure interval gap calculation and four unexecuted tests. Review, correct if necessary, and reuse this work. No service integration, snapshot caching, worker or frontend changes have been completed.

Existing paginated Activities API is a standalone SAM Lambda using SQLAlchemy Core. Existing Strava sync is in Flask/Zappa using SQLAlchemy ORM. Cold first-page latency is dominated by lazy SQLAlchemy imports and engine setup (~6.5 seconds of ~6.9 seconds); warm pages take tens of milliseconds. Do not introduce another database access technology.

## Implementation work

1. **Coverage and synchronisation service**
   - Integrate successful interval recording into the existing Strava domain service. Record empty successful windows; never record failed or partially retrieved windows. Use consistent UTC boundaries and verify Strava after/before semantics to avoid boundary gaps.
   - Use coverage union to determine missing periods. Process bounded windows newest first; make retries idempotent. Existing stored activities are not evidence of complete coverage.
   - Automatic recent sync: maximum 30 days. Manual: since last successful recent sync, maximum one year; remaining gaps handled by background work. Do not let historical backfill advance the recent-sync watermark.
   - Enforce per-user concurrency across tabs and all sync entry points, including OAuth and legacy endpoints. Persist job state, recover abandoned work safely, distinguish authorization failure from transient/API failure. Stop automatic action after reconnect prompt. No proactive rate-limit management beyond respecting API limits and handling failures.
   - Verify premium full-history boundary (do not silently assume existing 2020 constant is full history). Basic rolling 12 months, no physical deletion.

2. **Asynchronous execution**
   - Select and document a durable, resumable scheduling mechanism compatible with AWS and local Docker. Do not rely on threads continuing after a Lambda response. Prefer bounded jobs with durable continuation and retry handling; do not rely on the browser remaining open for true background execution.
   - Keep business logic in reusable domain services; isolate AWS-specific adapters and wiring. Avoid duplicating Flask and Lambda business logic. Document concurrency, failure recovery and operational implications.

3. **Private JSON snapshot**
   - Maintain up to 50 newest entitled activities per user. Use authenticated lightweight retrieval that avoids database/SQLAlchemy startup on the normal cache-hit path; evaluate private S3 with appropriate access controls. Ensure authorization, membership changes and rolling entitlement expiry cannot expose stale unauthorized data.
   - Reuse existing activity serialization contract. Regenerate asynchronously only when snapshot contents change, including relevant activity edits (e.g. RPE/analytics) and entitlement changes. Ensure concurrent regeneration cannot overwrite newer state. Handle missing or corrupt cache gracefully.
   - Provide idempotent seed operation for existing user before enabling the new login flow. No public objects or cross-user access. Never log tokens or secrets.

4. **Frontend**
   - On login display cached JSON immediately; retrieve remaining stored activities and start automatic Strava sync concurrently. Merge cached, DB and newly persisted rows by ID, newest first, without gaps or duplicates. Preserve selected filters, existing cursor contract and existing consumers (Visualizations and AI Insights).
   - Update progressively after persistence without waiting for snapshot regeneration. Handle races, stale requests, logout/account changes, missing cache and failed sync.
   - Sync button disabled throughout any Strava sync, including background sync; display status and re-enable on completion/failure if authorization valid. Prompt reconnect and stop automatic action on authorization failure. DB retrieval and snapshot regeneration alone must not disable Sync.

5. **Entitlements and deployment**
   - Apply Basic rolling 12-month access consistently to standalone and Flask activity retrieval, snapshot, historical sync and relevant activity detail access; premium full history. Do not change AI Coach tier policy.
   - Update SAM/Zappa/local Docker configuration as needed, least-privilege IAM, private storage, observability and safe timeout/retry configuration. Preserve existing CORS and authentication.
   - Update deployment documentation with migration, snapshot seeding, backend and frontend rollout ordering, rollback, verification and exact safe commands. Never pass literal UsePreviousValue as a SAM parameter value. Existing Activities stack is veloclicks-activities-prod in eu-west-2; verify actual configuration before deployment. Do not deploy production or expose secrets.

## Repository starting points

- flask/app/strava/{service,routes,strava_client,utils,constants,coverage}.py
- flask/app/models/{user,strava,sync_history,__init__}.py
- flask/app/migrations/versions/c4a8d1e7b920_sync_history.py
- aws/lambdas/activities/{handler,activity_list}.py
- aws/lambdas/template.activities-prototype.yaml and template.yaml
- frontend/src/app/activities/page.js
- frontend/src/contexts/AuthContext.js
- frontend/src/app/profile/strava-connect/page.js
- frontend/src/app/sync/strava/page.js
- flask/tests/test_sync_coverage.py and existing activity pagination/Lambda tests
- docs/cheat_sheet.md and local Docker/Zappa configuration

Inspect actual paths and current implementation; this list is not exhaustive.

## Acceptance and testing

- Test BS01–BS04 and trace every FR01–FR14 to implementation and tests.
- Cover empty/overlapping/adjacent intervals, boundaries, failed pagination, partial persistence, interrupted/resumed jobs, concurrent requests, no-change snapshot, snapshot invalidation, user isolation, tier changes and expired/revoked tokens.
- Verify legacy activity list consumers, pagination and ordering, UI merge races, status and reconnect behavior.
- Test migration upgrade/downgrade and local Docker execution without Lambda emulation. Run relevant backend and frontend tests and validate infrastructure templates.
- Measure cold and warm login-to-first-rows latency and demonstrate cache-hit path avoids DB startup; report actual measurements, not estimates. Production measurements may remain a post-deployment owner action.
- Report test commands, results, untested cases, decisions, changed files and deployment instructions. Do not declare completion with unresolved requirements; explicitly identify any blockers.
- Historical late uploads, Strava edits/deletions reconciliation and AI Coach entitlement changes are outside this task.

## Delivery

Implement the entire feature, not just the next incremental step. Work in coherent commits, validate the integrated result, and leave main ready for the owner's controlled rollout. Coordinate frontend activation with backend migration and cache seeding (use a disabled-by-default rollout mechanism if necessary because main pushes may trigger Vercel deployment). Do not deploy production.
