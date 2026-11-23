# Task proposal — Load the first activity page before older rides

**Date:** 2026-11-23  
**Status:** Approved for implementation
**Approved by:** Patrick, 2026-11-23 at 19:49 GMT (Europe/London)

## Problem

The Training Activities page can take a while to show rides after login. It renders up to 50 rows per page, but it only applies that limit after downloading and parsing the full list. For the selected date range, Flask currently queries all matching activities for the authenticated user, serialises them into one response, and sends them to the browser. The query reads stored PostgreSQL data. It does not sync with Strava.

Relevant code:

- `frontend/src/app/activities/page.js` fetches the full list, then filters, sorts and paginates it in the browser.
- `flask/app/strava/routes.py` handles `GET /strava/activities/`.
- `flask/app/strava/service.py` orders the database results by start date and calls `.all()`.

The production smoke account returned two rides in 0.19 seconds. That does not establish where the delay comes from for a large history. Measure database, API and browser time to first visible rows with a representative dataset before attributing the observed delay to response size. Consider cold and warm Lambda invocations.

## Proposed approach

1. Add opt-in cursor pagination to the existing authenticated Flask endpoint. The Activities page requests up to 50 of the newest stored rides in the selected range. Apply the limit in PostgreSQL. The response includes the activities and a next cursor only when more rows exist. An account with 12 matching rides gets 12 rows and no continuation request.
2. Order by start date and activity ID, both descending, so activities with the same start date have a stable order. Use both fields for the cursor boundary. Scope every request to the authenticated user and the same date selection. Review the query plan before deciding whether a composite index is needed.
3. Display the first batch immediately. The browser then follows the cursor in the background, appending older rides to memory until it reaches the end. Each batch is a request to the existing Flask API on Zappa and invokes that Lambda. No worker or Strava sync is needed.
4. Keep search, filters, and display pagination in the browser. Search the full set loaded so far, then show 50 matching rows per page. Indicate that older activities are still loading and that matches can increase. Typing and switching between loaded pages do not cause a reload or initiate search requests.
5. Cancel or ignore requests from a superseded year selection, refresh or session. Keep the first batch visible if a later batch fails, and allow that batch to be retried without refetching the first page. Show a definitive empty state only when the relevant load has completed successfully.
6. Preserve the existing array response for callers that omit pagination, including Visualizations and AI Insights. Keep the current date-filter behaviour and response fields for those callers.

## What to verify

- The first API response is bounded to 50 rows and the first page renders before a delayed continuation returns. Cover accounts with 0, fewer than 50, exactly 50, and 500 matching rides.
- With 500 rides and 73 names containing `threshold`, the completed search shows 50 matches on page 1 and 23 on page 2, with no extra fetch triggered by typing or paging. Before all batches arrive, the UI clearly identifies incomplete results.
- Identical start timestamps do not cause omitted or duplicated rows. An invalid cursor is rejected and cannot expose another user's rides.
- Changing years, refreshing after sync, or changing sessions while a batch is in flight cannot append stale results. A failed continuation preserves loaded rides.
- The existing unpaginated callers and demo mode still work.
- Compare first-page latency and request count against the current full-list path. Review whether 50-row continuation batches are a good tradeoff for Lambda invocations and total loading time.

## Implementation and verification

Implemented locally. Production rollout is pending. Apply the index migration and deploy Flask before publishing the frontend that requests cursor pages.

- Four targeted Flask tests passed. They cover 0, 12, 50, and 500 rides, tied timestamps, cursor invalidation, the rolling date range, and the legacy response.
- A local Chrome regression check with synthetic responses verified that the first page appears while a continuation is delayed, a retry resumes from the failed cursor, and a year change discards a stale response. Searching 500 loaded rides for `threshold` produced 73 matches across two display pages with no search or paging requests.
- On local PostgreSQL, a 50,000-row synthetic table with 500 rides for the test user scanned the table before the index. With the index, the first-page query used a backward index scan. Execution took 0.051 ms for the first batch versus 0.219 ms for the full indexed list in this run.
- In a local Flask test-client benchmark with 500 synthetic rides, median response time was 3.29 ms for the first 50 versus 21.40 ms for all 500. The response sizes were 32,745 and 299,895 bytes. These checks exclude network and Lambda cold-start time.
- Loading all 500 rides takes ten successful requests instead of one. Review that invocation tradeoff against production first-page latency before tuning the continuation batch size.
- The broader Flask suite still has one unrelated coaching prompt assertion failure, reproduced on the unchanged baseline.

## Production follow-up — 2026-11-23

The index migration and paginated Flask API were deployed to production, followed by the Activities UI on Vercel in commit `6b7d99d`. The original rollout note above records the earlier local state. Production returned the new paginated response, but Patrick still reported an intermittent wait for the first 50 rides after login.

- A fresh Chrome session using Patrick’s account reproduced the delay. The first rows appeared 22.5 seconds after sign-in. Login returned after 4.3 seconds, the activities request started 180 ms later, the response took 17.9 seconds, and rows appeared within 60 ms of the response. Two later sessions showed the first rows after 3.2 seconds and 1.4 seconds.
- Activity-list requests go through API Gateway to `veloclicks-dev`, the Zappa-managed Flask Lambda. Login uses the separate Auth Lambda. The first activity request can therefore hit an execution environment that has yet to initialise Zappa and Flask.
- After enabling API Gateway access logs, an exact request-ID match for a slow production `/health` request showed 16.8 seconds at Gateway, 0.82 seconds of Lambda runtime initialisation, 15.3 seconds in Zappa startup before it processed the event, and about 3 ms handling the request. The health route does not query PostgreSQL. Existing startup markers place Flask configuration completion 11.8 seconds after Zappa began, with another 3.5 seconds before the handler processed the event. The largest startup phase is still unresolved among archive loading, imports and SSM lookups. This confirms startup can cause a delay of the observed size. Gateway logging was unavailable for the original slow login, so the health trace cannot establish the cause of that specific browser request.
- Production Flask Gateway access logs are enabled in CloudWatch at `/aws/apigateway/veloclicks-dev-access`, with seven-day retention. The logs include request IDs and response and integration times. They omit credentials, headers, query strings and payloads.

## Proposed follow-up — Standalone Activities read Lambda

Build and benchmark a small standalone Lambda for the **read-only paginated activity list** before deciding on a production switch. Keep the current Flask endpoint available for rollback, legacy array callers, and local development. Keep activity details, coaching, Strava sync, and the existing Auth endpoint on their current paths.

- **Prototype approach A (approved for testing):** Leave the existing Flask-SQLAlchemy `Activity(db.Model)` unchanged. The standalone Lambda must not import the Flask model or initialise Flask. Query the existing `vc_strava_activity` PostgreSQL table using plain SQLAlchemy Core with a standalone engine/connection and the existing composite index. Extract or reuse framework-independent cursor rules, date selection, authentication verification, and response serialization where practical; avoid duplicating security-sensitive logic. A separate lightweight table definition or explicit column selection is acceptable for the prototype, but document any schema/serialization duplication and test response parity against Flask. Do not refactor the full ORM or introduce a generic persistence framework for this experiment.
- Reuse the shared access-token verifier and production signing configuration. Keep owner scoping, date selection, cursor validation, bounded responses, and API status and JSON contracts. Verify that a user cannot read another user’s rows or use their cursor.
- Use a thin serverless HTTP adapter and preserve the UI’s first-batch and background loading behaviour. Measure cold and warm service time and end-to-end browser time to the first visible rows against the current Zappa path, with the same representative history. Check PostgreSQL connection reuse, continuation behaviour, and request counts.
- Review the deployment boundary and frontend URL or routing change before switching production traffic. Preserve a way to point the frontend back to Flask if needed. The original approval above covers the progressive loading change. The standalone Lambda is a new proposal and has not been implemented or deployed.

## Review feedback — 2026-11-23: Approve Option A prototype

Patrick approved **testing Option A** for the standalone Activities read Lambda, **not** a production cutover.

- Keep the existing Flask `Activity(db.Model)` and existing Flask endpoint unchanged. Use SQLAlchemy Core directly against `vc_strava_activity` from the standalone Lambda, without importing `flask.app.models`, Flask-SQLAlchemy, or anything that triggers Flask/Zappa startup.
- Keep the implementation deliberately small: read-only paginated list, bounded query, same ordering and signed cursor semantics, authenticated user scoping, date range and JSON response. Reuse shared framework-independent utilities where possible; test that the Lambda and Flask responses match, including nulls, numeric rounding, timestamps and pagination edge cases.
- Package only required dependencies. Verify that authentication and database configuration do not introduce their own costly startup imports or synchronous lookups. Keep secrets and cursor signing compatible with the existing API.
- Benchmark cold and warm requests and first-visible-rows time against Zappa, including connection establishment and follow-on page requests. The objective is to remove the observed ~15-second Zappa startup overhead, not to redesign the whole database layer.
- Do **not** change frontend routing or production traffic until the prototype's results have been reviewed. Preserve the existing endpoint as fallback.

## Option A prototype results — 2026-11-23

Implemented the read-only API Gateway handler in `aws/lambdas/activities/` and a separate `aws/lambdas/template.activities-prototype.yaml` for an isolated benchmark. The existing Flask activity route, ORM model, production SAM stack template, and frontend routing are unchanged. The prototype requires an explicit `limit` from 1 to 50. Existing array callers stay on Flask.

- The SQLAlchemy Core table projection, value formatting, date-window parser and cursor codec intentionally mirror the Flask implementation for this experiment. The parity tests guard these duplicated contracts. Both adapters use the same JWT verifier. The lightweight adapter imports neither Flask, SQLAlchemy, the PostgreSQL driver, nor password hashing until needed. The connection pool is opened lazily and reused. The database URL and signing key are supplied via environment variables, with no runtime SSM lookups.
- Fourteen targeted tests and fifteen subtests passed. Coverage includes bidirectional cursor exchange, equal timestamps, dates and nulls, numeric rounding, full histories, the rolling date window, cross-user cursor rejection and access-token compatibility.
- The isolated SAM host build passed with Linux x86_64 wheels. The installed SAM builder could not resolve the latest transitive greenlet wheel, so the prototype pins a compatible wheel. The unpacked package is approximately 18 MiB.
- Five fresh local Linux Python processes per adapter queried the same 500 synthetic rides in an isolated PostgreSQL schema. Both retrieved all 500 in ten pages. Median timings are below.

| Phase | Standalone prototype | Flask |
| --- | ---: | ---: |
| Process imports and app or engine setup | 587 ms | 2,193 ms |
| First PostgreSQL connection | 26 ms | 27 ms |
| First page after connecting | 17 ms | 36 ms |
| Warm first page | 7 ms | 8 ms |
| Remaining nine pages | 76 ms | 100 ms |

These local results exclude Lambda runtime initialisation, Zappa’s S3 archive load, production SSM and database network latency, API Gateway, and browser rendering. The previous production Zappa timings above are the baseline for an isolated AWS and browser comparison. The prototype has not been deployed to AWS, and no production traffic has moved. Review the local results before authorising an AWS benchmark endpoint or deciding on a cutover.

## Production cutover — 2026-11-23

Patrick authorised moving production activity-list traffic to the standalone Lambda and reserved the rollback decision. The stack `veloclicks-activities-prod` serves `https://1m4c74owqj.execute-api.eu-west-2.amazonaws.com/Prod`. It uses a separate stack and a PostgreSQL connection configured read-only. No Zappa or Auth/Coach redeployment is needed. The dedicated endpoint accepts CORS from `veloclicks-prod.vercel.app`.

Before switching the frontend, an authenticated production comparison matched the first page and signed cursor against Flask and verified continuation in both directions, CORS, and unauthorized rejection. One first-request comparison measured 7.0 seconds on the new endpoint and 17.3 seconds on Zappa. A warm standalone first page took 0.22 seconds. These are individual samples.

The canonical production frontend uses the standalone endpoint for paginated activities. Local and demo use the existing Flask API. The optional `NEXT_PUBLIC_ACTIVITIES_API_URL` setting can override the list URL. To roll back traffic if Patrick decides, restore the previous Vercel production deployment or point that variable at the Flask base URL and redeploy the frontend. Leave the Flask endpoint available and keep the new stack intact during a traffic rollback.
