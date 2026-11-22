# Veloclicks — Proposed Architecture

**Decision record:** [Architecture Decision Log](decisions.md) — current decisions made with ChatGPT; implementation proposals remain in this document.

**Status:** Proposal for discussion; not an implemented design or migration commitment.

## Goals (in priority order)

1. **Portable application logic:** Avoid tight coupling to AWS Lambda or any other hosting platform.
2. **Low running cost:** Prefer pay-per-use compute where it makes sense; account for API Gateway, PostgreSQL, networking and logs as well as Lambda charges.
3. **Fast startup and response:** Keep entry points and deployment packages lean; measure cold starts before splitting services.
4. **Easy local development:** Keep Docker Compose as the primary development workflow.
5. **Clear module responsibilities:** Consistent patterns and naming without unnecessary layers or abstractions.

## Guiding principle

> Veloclicks is a Python application that happens to run on AWS Lambda, not an AWS Lambda application.

**Organise code by responsibility; choose deployment boundaries separately.** Flask is welcome as an HTTP framework. Zappa is to be retired. AWS SAM is the preferred AWS deployment tool for now, but application logic must not depend on SAM, Lambda event formats or AWS SDKs.

## Module deployment matrix — As-Is vs To-Be

| Module | Features | Local deployment | Production (As-Is) | Production (To-Be) |
| --- | --- | --- | --- | --- |
| **Frontend** | UI, dashboards, activity visualisation | Next.js (`npm run dev`) | Vercel | Vercel |
| **Auth** | Veloclicks login, registration, token management | SAM local / Docker | AWS Lambda / SAM | AWS Lambda / SAM |
| **Profile** | User settings, FTP, training zones | Flask / Docker | Flask / Zappa / Lambda | Flask / SAM / Lambda |
| **Strava** | OAuth authentication, access/refresh tokens, activity synchronisation, stream retrieval | Flask / Docker | Flask / Zappa / Lambda | Flask / SAM / Lambda |
| **Analytics** | Activity classification, interval detection, granular snapshots, power metrics (power curve, power zones, TSS), activity summaries | Flask / Docker | Flask / Zappa / Lambda | Flask / SAM / Lambda |
| **Coach** | AI coaching, activity interpretation, training recommendations | Docker | AWS Lambda / SAM | AWS Lambda / SAM |
| **Admin** | Administration, maintenance | Flask / Docker | Flask / Zappa / Lambda | Flask / SAM / Lambda |
| **Database** | PostgreSQL, user and activity data | PostgreSQL / Docker | Existing PostgreSQL hosting | Existing PostgreSQL hosting |

**Note:** The To-Be column is a proposal. The Flask modules currently run through Zappa; the proposed migration replaces Zappa with SAM without necessarily splitting the Flask application into separate functions.

## Current architecture (as documented)

- **Frontend:** Next.js on Vercel; Git push triggers deployment.
- **Core API:** Flask packaged for AWS Lambda using Zappa (remote stage named `dev`).
- **Auth:** Standalone Lambda deployed using SAM; frontend login calls its API Gateway endpoint.
- **Coach:** Standalone Lambda deployed using SAM; invoked by the Flask API.
- **Data:** PostgreSQL via SQLAlchemy.
- **Local:** Docker Compose runs PostgreSQL, Flask and the Coach Lambda runtime; SAM local runs the Auth API; Next.js runs separately.

See `docs/cheat_sheet.md` for the actual commands and current endpoints.

## Logical responsibilities

| Area | Owns | Does not own |
| --- | --- | --- |
| **Strava** | Strava API integration, activity import/synchronisation and external-data normalisation | Training analysis or coaching decisions |
| **Analytics** | Deterministic activity classification, interval detection, snapshots and derived metrics | HTTP/Lambda event handling or LLM inference |
| **Coach** | Preparing coaching requests from analysed data and generating interpretations | Recomputing analytics or fetching raw Strava streams |
| **Auth** | Authentication and token handling | Cycling analysis |
| **Profile / Admin** | Their existing Flask application operations | Unrelated analytics or coaching |

These are **logical modules**, not necessarily separate deployable Lambdas.

## Code organisation rules

- **Keep the existing `flask/app/` structure** for Flask routes, SQLAlchemy models, persistence and other Flask-specific functionality. Do not move code merely because it is deterministic or to satisfy a directory convention.
- **Entry points are thin:** Flask routes and Lambda handlers translate requests/responses, invoke ordinary Python functions and perform minimal environment-specific wiring.
- **No domain logic in Lambda-specific files.** A Lambda handler should be replaceable by an Azure Functions handler, Flask route or CLI without rewriting business rules.
- **Extract a shared Python module only when needed** by another execution environment or when it removes a real framework dependency. Such modules must be importable and testable without starting Flask.
- **Keep infrastructure integrations at boundaries:** AWS SDK calls, Lambda invocation, provider-specific configuration and LLM clients should not leak into deterministic domain calculations.
- **Prefer consistent naming:** `routes.py` for Flask HTTP entry points, `service.py` for application orchestration where useful, `*_client.py` for external API access, and descriptive names for specialist algorithms. Not every module needs every layer.
- **Preserve existing API and JSON contracts** during initial restructuring; test before changing formats.

## Proposed deployment approach

| Component | Near-term approach |
| --- | --- |
| Next.js frontend | Keep Vercel |
| Flask API | Replace Zappa with a SAM-managed Lambda using a thin WSGI adapter, initially preserving existing Flask routes |
| Auth | Currently a standalone SAM Lambda; review whether to retain this boundary; keep business logic separate from its handler |
| Coach | Currently a standalone SAM Lambda; review whether to retain this boundary; keep coaching implementation separate from its handler |
| Strava / Analytics | Keep logical module boundaries; do **not** split into additional Lambdas without a measured benefit |
| Local development | Preserve Docker Compose; minimise the need to simulate Lambda locally for ordinary application logic |

A SAM-managed Flask Lambda **removes Zappa but does not automatically remove Flask cold-start overhead**. Splitting functions is an optimisation decision, not a prerequisite for clean code. A future Azure or container deployment should require replacing adapters and deployment configuration, not rewriting domain logic.

## Migration sequence

1. **Inventory the existing modules:** Document the purpose, dependencies and overlaps of every file in `flask/app/strava/`, `flask/app/analytics/`, `flask/app/ai_coach/`, and the Auth/Coach Lambda directories.
2. **Agree module responsibilities and conventions:** Decide which code remains Flask-specific and which genuinely needs to be independent.
3. **Separate Lambda entry points from application logic:** Prioritise Auth and Coach; verify standalone imports/tests do not initialise Flask.
4. **Replace the Zappa deployment:** Deploy the existing Flask API through SAM and a minimal WSGI adapter; verify all routes, environment variables, database connections and response contracts.
5. **Retire Zappa only after cutover:** Switch consumers to the new API endpoint, verify behaviour and logs, then remove the old deployment.
6. **Optimise only with evidence:** Measure package sizes, cold starts, latency and operating costs before introducing more Lambdas.

## Open decisions / validation

- Exact module/file responsibility matrix and dependency audit.
- Which Flask services are coupled to Flask application context or SQLAlchemy session handling.
- SAM packaging and WSGI adapter choice for the Flask API.
- API Gateway routing, frontend configuration and migration/cutover plan.
- How local Docker and SAM workflows should coexist with minimal friction.
- Baseline and target cold-start latency, total cost and PostgreSQL connection behaviour.

**Out of scope for this proposal:** A wholesale move from Flask to FastAPI, a blanket move of `flask/app/` into `core/`, one Lambda per module, or a general-purpose cloud abstraction framework.
