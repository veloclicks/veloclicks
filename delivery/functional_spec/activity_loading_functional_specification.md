# Veloclicks — Progressive activity loading

**Functional specification | v0.1 | 24 November 2026**

## 1. Objective

Display recent activities immediately on login, prioritise recent Strava imports, and retrieve remaining history in the background without leaving synchronisation gaps.

## 2. Business scenarios

| ID | Scenario | Agreed behaviour |
|---|---|---|
| BS01 | Regular returning user | Display cached JSON immediately. Retrieve remaining stored activities and automatically synchronise with Strava concurrently. Update the UI as new activities are persisted. Refresh JSON asynchronously if its contents change. If no activities change, retain the existing JSON and record successful synchronisation. |
| BS02 | New user | Automatically import the previous 30 days of activities. Persist and display recent activities without waiting for the full historical import. Generate JSON asynchronously. Import remaining entitled history in the background, newest first. |
| BS03 | Extended period without synchronisation | Display cached JSON immediately. Prioritise automatic synchronisation of the previous 30 days. Fill missing periods and remaining entitled history in the background. Retrieve stored historical activities concurrently. |
| BS04 | Strava authorisation expired or revoked | Display cached JSON and retrieve remaining stored activities. If authorisation cannot be refreshed automatically, prompt the user to reconnect. Take no further automatic action following the prompt. Disable Sync while authorisation is unavailable. |

## 3. Common functional requirements

| ID | Requirement |
|---|---|
| FR01 | Maintain a private, per-user JSON snapshot containing up to the latest 50 entitled activities. |
| FR02 | Automatic synchronisation on login looks back a maximum of 30 days. |
| FR03 | Manual synchronisation retrieves activities since the last successful sync, capped at one year. Any remaining gaps are handled by background synchronisation. |
| FR04 | Background synchronisation fills missing periods and imports remaining entitled history. |
| FR05 | Prioritise recent activities over older activities. |
| FR06 | Update the UI progressively after activities are persisted. Merge cached, stored and newly imported activities without duplicates, ordered newest first. |
| FR07 | Regenerate JSON asynchronously whenever the latest 50 entitled activities change. |
| FR08 | JSON regeneration must never delay the UI update. |
| FR09 | Disable the Sync button throughout any Strava synchronisation, including background synchronisation. Display a synchronising status and re-enable the button when synchronisation completes or fails, provided authorisation remains valid. |
| FR10 | Prevent concurrent Strava synchronisation requests for the same user, including across browser tabs. Historical DB retrieval and JSON regeneration do not disable the Sync button. |
| FR11 | Observe Strava API rate limits. No additional proactive rate-limit management is planned for this release; observe actual usage. |
| FR12 | Background synchronisation must be resumable. |
| FR13 | Basic users have access to a rolling 12 months of activity history. Apply the entitlement to activity retrieval and display, including the JSON snapshot. Premium users have full history access. |
| FR14 | Do not physically delete older activities solely because they fall outside a Basic user's entitlement. |

## 4. Synchronisation coverage

Introduce a `sync_history` table with `user_id`, `from_date`, `to_date` and `completed_at`.

- Record a period only after its activities have been successfully retrieved and persisted, including periods containing no activities.
- Identify gaps from the union of completed periods, rather than from the date of the latest activity or a single last-sync timestamp.
- Consolidate overlapping or adjacent completed periods where appropriate.
- Resume incomplete historical imports without treating uncompleted periods as covered.
- Automatic and manual synchronisation retain their respective lookback limits; background synchronisation fills outstanding gaps within the user's entitlement.

## 5. Existing user transition

There is currently only one user. Existing activity history is known to contain gaps, including in 2026.

1. Initialise synchronisation coverage as empty; do not infer completeness from stored activities.
2. Seed the JSON snapshot from the latest 50 entitled activities already in the DB before the first login using the new flow.
3. Display that snapshot immediately on login.
4. Automatically synchronise the previous 30 days and retrieve remaining stored activities concurrently.
5. Import remaining entitled history in the background, newest first, inserting missing activities without duplicating existing ones.
6. Record successfully synchronised periods and refresh the UI and JSON under the common requirements.

## 6. Implementation notes and outstanding details

- The current standard sync endpoint caps lookback at 30 days; the existing initial OAuth import also covers 30 days. Manual sync and background coverage will require changes.
- The precise interpretation of the manual last-sync timestamp when gaps remain, and the scheduling and persistence mechanism for asynchronous work, remain implementation design decisions.
- Premium full-history access and retention of older Basic-user data are the working assumptions; verify against existing entitlement enforcement.
- Potential Basic-tier AI Coach restrictions are deferred; no coach changes are specified.
- No implementation or deployment is authorised by this document alone.
