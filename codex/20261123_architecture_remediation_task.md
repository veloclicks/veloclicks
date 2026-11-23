# Task — Architecture Remediation: Authentication, Coaching and Local Startup

**Date:** 2026-11-23
**Status:** Ready for Codex
**Repository:** `veloclicks/veloclicks`
**Working directory:** `~/dev/veloclicks`

## Instructions and authority

Implement, test, and—once safe and verified—deploy the changes below. Work autonomously on routine implementation. Follow these repository documents **before editing code**:

1. `docs/architecture/principles.md` — binding architecture principles AP-01 through AP-04.
2. `docs/engineering/standards.md` — coding, docstring, comments, testing and layering standards.
3. `architecture/decisions.md` — recorded architecture decisions.
4. `docs/cheat_sheet.md` — actual local startup, test environment, production deployment commands and endpoints.
5. `claude.md` and `architecture/README.md` — existing deployment and architecture context.

**Known unresolved standard:** The statement in engineering standards preferring module-level functions for stateless operations is **not accepted**. Do not treat that sentence as mandatory; use cohesive domain services and existing patterns, and ask if a significant classes-versus-functions choice is borderline.

**Known contradictory architecture decision — ask before changing deployment strategy:** `architecture/decisions.md` currently says *replace Zappa with AWS SAM*, whereas the latest agreed direction and `docs/architecture/principles.md` retain Zappa for the Flask application and permit individual Lambda deployments. **Do not migrate Flask from Zappa to SAM.** Surface this discrepancy explicitly and request a decision on updating the decision log; do not let it block non-conflicting local refactoring.

## Scope

### 1. Authentication — high priority

- Consolidate business logic currently duplicated in `flask/app/auth/routes.py` and `aws/lambdas/auth/auth_service.py`; share one authoritative service between local Flask and the production standalone Auth Lambda.
- Keep API Gateway/Lambda and Flask HTTP handlers as thin adapters. Preserve existing user records, password hashes, login/register/refresh semantics and public response contracts.
- **Important compatibility risk:** existing Flask JWT and Auth Lambda JWT payloads and expiry policies differ. Inspect `flask/app/common/auth.py`, frontend token consumption and all production entry points; write compatibility tests before changing token generation. Preserve verification of existing valid tokens or explicitly escalate any unavoidable break.
- Local authentication must work without SAM or a Lambda runtime emulator.

### 2. AI coaching

- Refactor `flask/app/ai_coach/routes.py` so business logic does not directly depend on `boto3` Lambda invocation.
- Reuse the same coaching capability locally and in the standalone production Coach Lambda; infrastructure-specific adapters are permitted at the boundary.
- Preserve premium-tier authorisation, existing caching/persistence of insights, error responses, prompt behaviour and token usage reporting.
- Local coaching must not require a Lambda emulator.

### 3. Docker Compose startup

- Make `docker compose up --build` from the repository root sufficient to start **all required local application services**, including frontend, Flask, PostgreSQL, authentication and coaching.
- Do not require `sam local start-api` or a separate `npm run dev` terminal. Use Docker service names for container-to-container connections and browser-reachable URLs for browser requests.
- Avoid hard-coding secrets; respect existing `.env` handling and keep production hosting unchanged.
- Update `docs/cheat_sheet.md` with the actual new commands, ports and any setup prerequisites.

## Baseline startup and deployment reference

**Current local startup (to be simplified):**

```bash
cd ~/dev/veloclicks
open -a docker
docker compose up --build
# Currently, auth separately:
cd aws/lambdas
sam build
python3 generate_local_env.py
sam local start-api --port 3002 --docker-network veloclicks_default --env-vars env.local.json
# Currently, frontend separately:
cd ../../frontend
npm run dev
```

**Target local startup:**

```bash
cd ~/dev/veloclicks
docker compose up --build
```

Current documented local checks: frontend `http://localhost:3000/login`, Flask `http://localhost:5002/health`. Verify actual routes and update docs.

**Existing production deployment procedures** are in `docs/cheat_sheet.md` under *Production (Remote)*. Do not improvise new infrastructure. The documented Flask deployment is `cd zappa && source .venv/bin/activate && export AWS_PROFILE=zappa-deployer && zappa update dev`; Auth and Coach Lambdas deploy together through `aws/lambdas/template.yaml` using `sam build` and `sam deploy` with secrets from SSM. The frontend deploys automatically via Vercel on Git push. Read the full documented commands before any deployment; do not copy secrets into source, logs, commits or reports.

**Deployment caution:** The existing remote Zappa stage is named `dev` but is the live environment; treat it as production. Deploy only after passing automated and Docker integration tests, confirming current AWS identity and impact, and ensuring rollback is practical. If a destructive change, secret/configuration change, architecture ambiguity or significant production risk arises, stop and ask before that action.

## Required process and tests

1. Inspect repository layout, existing tests, environment configuration and all relevant call paths. Establish a baseline.
2. Make small, cohesive changes aligned with AP-01 through AP-04. Non-trivial methods need meaningful docstrings; explain non-obvious logic with comments. Do not undertake unrelated cleanup.
3. Add regression tests for auth registration/login/refresh, token compatibility and rejection cases; coaching generation/cache/authorisation/error paths; local HTTP adapters and shared services.
4. Run appropriate unit tests, build/start Docker Compose and perform end-to-end local smoke tests of authentication, authorised API access and coaching (mock paid LLM calls for repeatable tests; only perform a real call when appropriate and configured).
5. Verify the deployed production contracts and configuration are compatible. Deploy only the affected components using documented commands, and run post-deployment smoke tests without exposing user data or credentials.
6. Update documentation where behaviour/startup differs. Commit changes to Git; note that pushing to Git triggers Vercel frontend deployment.
7. If tests or deployments cannot be performed, say exactly which commands were attempted and why they failed. Never claim success without evidence.

## Escalation policy

Ask explicitly when a principle/standard is unclear, a proposed design is borderline, deployment boundaries must change, production compatibility cannot be guaranteed, or a consequential security choice is needed. Otherwise proceed without asking for routine permission. Never silently weaken security, change public APIs, or make destructive database changes.

## Completion report

Report concisely: changes and file paths; commit hash; exact tests run and pass/fail results; Docker startup verification; deployment commands executed and result; post-deployment checks; unresolved issues and decisions requiring input.
