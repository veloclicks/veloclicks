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
