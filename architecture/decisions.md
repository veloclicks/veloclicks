# Architecture Decision Log

> **These decisions were made in discussions with ChatGPT.** This log records the user's architectural preferences and decisions, alongside proposals that still require validation. It is not a record of implemented changes. Dates refer to when entries were recorded, not necessarily when the underlying discussion began.

## Agreed decisions

| ID | Decision | Rationale / implications | Status |
| --- | --- | --- | --- |
| AD-001 | Organise code by business responsibility, independently of deployment units. | Strava, Analytics, Coach, Auth and other areas are logical modules; they do not each require a Lambda. | Agreed |
| AD-002 | Retain Flask for the existing API. | No compelling reason to rewrite the API in FastAPI. | Agreed |
| AD-003 | Retire Zappa and use AWS SAM for backend deployment. | Simplify and standardise AWS deployments; migration remains to be implemented. | Agreed direction |
| AD-004 | Keep AWS Lambda as the preferred production compute for now, while avoiding Lambda-specific business logic. | Preserve low usage-based running costs and portability to containers or Azure. | Agreed |
| AD-005 | Keep Docker Compose as the primary local development approach. | Local business logic should not require deployment to AWS. | Agreed |
| AD-006 | Keep Auth and Coach as separate Lambda deployments. | Preserve current deployment boundaries; handlers should remain thin. | Agreed |
| AD-007 | Keep Strava OAuth authentication and access/refresh token management within the Strava module, distinct from Veloclicks user authentication. | External Strava authorisation is part of the Strava integration. | Agreed |
| AD-008 | Analytics owns activity classification, interval detection, snapshots, and power metrics including power curve, power zones and TSS. | Deterministic analytics are separate from AI interpretation. | Agreed |
| AD-009 | Avoid wholesale relocation of existing Flask code or splitting every module into its own Lambda. | Prefer incremental changes supported by actual dependencies and performance evidence. | Agreed |

## Proposed implementation choices — not yet finalised

| ID | Proposal | Validation needed | Status |
| --- | --- | --- | --- |
| AP-001 | Host the existing Flask API on a SAM-managed Lambda via a thin WSGI adapter. | Adapter, packaging, routes, database connections, cold starts and cutover. | Proposed |
| AP-002 | Keep Profile, Strava, Analytics and Admin in the same Flask deployment initially. | Verify dependencies and performance before considering further splits. | Proposed |
| AP-003 | Preserve existing PostgreSQL hosting during the deployment migration. | Confirm connection handling and cost. | Proposed |

## How to maintain this log

- Add a new entry when an architectural decision is made or a proposal is explicitly accepted.
- Record reversals or superseding decisions rather than silently deleting history.
- Distinguish **agreed decisions**, **proposals**, and **implemented changes**.
- Update the architecture overview and deployment matrix when a decision changes the target design.
