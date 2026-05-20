# Design Principles

## Code Organization
- Clear module boundaries
- Explicit schemas and contracts

## Analysis Approach for LLM integration
- Deterministic analysis outside the LLM where possible
- LLM used for narrative interpretation on top

## Deployment
- Pragmatic choices over unnecessary complexity
- Prefer serverless (Lambda) for workloads where it makes sense

# Design Principles

## Code Organization
- Clear module boundaries between domains
- routes.py: API entry points only, no business logic
- tools.py: Reusable domain services and utilities
- utils.py: Generic helper functions (string formatting, date math, etc.)
- models.py: Database models only, but keep all these in the models folder, not within each domain folder
- No direct database access from routes.py — always go through tools.py services

## Domain Boundaries
- Each domain accessible from the front end (auth, strava, profile) has its own routes.py, tools.py
- Cross-domain calls go through tools.py exports to increase reuse
- Other domains import services, not implementation details

## Analysis Approach
- Deterministic analysis outside the LLM where possible
- LLM used for narrative interpretation on top of deterministic findings
- Keep LLM payloads compact and schema-driven

## Performance
- Fast cold starts are critical for Lambda deployment
- Minimize dependencies loaded at import time
- Lazy-load expensive operations
- Keep core paths (login, auth) lightweight

## Deployment
- Pragmatic choices over unnecessary complexity
- Prefer serverless (Lambda) for isolated workloads