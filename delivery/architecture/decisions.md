# Architecture Decision Log

> **These decisions were made with ChatGPT.** This document records the current agreed architectural direction, not an audit trail. Remove or rewrite decisions when they no longer apply. Git retains version history.

## Architecture

| Decision | Rationale |
| --- | --- |
| Organise modules by business responsibility, independently of deployment units. | Logical modules do not imply one Lambda per module. |
| Strava owns Strava OAuth and access/refresh tokens; Analytics owns deterministic classification, intervals, snapshots and power metrics (power curve, power zones, TSS). | Keep external integration, analysis and coaching responsibilities distinct. |

## Application design

| Decision | Rationale |
| --- | --- |
| Retain Flask for the existing HTTP API. | Avoid a rewrite without a demonstrated benefit. |
| Keep business logic independent of Lambda, SAM and other hosting-specific entry points. | Enable local testing and future hosting portability. |
| Refactor incrementally rather than reorganising the entire codebase. | Preserve existing behaviour and avoid unnecessary complexity. |

## Deployment

| Decision | Rationale |
| --- | --- |
| Keep Docker Compose as the primary local development workflow. | Run and test the application without requiring AWS deployment. |

Implementation details such as the Flask WSGI adapter, which modules share a deployment, and database hosting are proposals in [README.md](README.md), not decisions recorded here.
