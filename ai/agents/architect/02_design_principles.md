# Design Principles

## Code Organisation

- Clear module boundaries between domains
- `routes.py` — API entry points only, no business logic, no direct DB access
- `service.py` — Domain business logic and orchestration; the public API of the domain to be accessed from routes.py or other domain services
- `utils.py` — Pure helper functions only (string formatting, date math, coordinate geometry, etc.); no DB access, no HTTP calls
- Database models live in the central `models/` folder, not within domain folders — never define models inside a domain

## Domain Boundaries

- Each domain accessible from the frontend (auth, strava, profile) has its own `routes.py` and `service.py`
- No direct database access from `routes.py` — always go through `service.py`
- Cross-domain calls go through `service.py` exports — other domains import services, not implementation details

## Deployment

- Pragmatic choices over unnecessary complexity
- Prefer serverless (Lambda) for isolated, stateless workloads — but apply Lambda-specific optimisations (lazy imports, minimal cold-start paths) only to Lambda functions, not to Flask app code
