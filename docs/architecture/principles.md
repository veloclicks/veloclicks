# Veloclicks Architecture Principles

These are enduring design principles, distinct from architecture decisions (ADRs). Decisions should comply with applicable principles, but need not each be derived from a principle.

## AP-01 — Domain Encapsulation and High Cohesion

Related business functionality shall be organised into cohesive domains with clearly defined responsibilities and boundaries. Each domain shall encapsulate its own business logic and minimise coupling with other domains.

**Rationale:** Promotes maintainability, independent evolution, and clear ownership of functionality.

## AP-02 — Infrastructure Independence

Application logic, across all domains, shall be independent of the infrastructure and execution environment in which it operates. Platform-specific code shall be isolated from application logic through clearly defined adapters.

In particular, logic deployed to AWS Lambda shall not be embedded within Lambda-specific handlers or depend on Lambda-specific event or runtime interfaces. Moving to another serverless platform or conventional hosting environment should require replacing adapters or configuration, not rewriting application logic.

**Rationale:** Preserves portability, simplifies local execution and testing, and limits platform lock-in.

## AP-03 — Reusable Domain Services

Each domain shall encapsulate its core business capabilities within well-defined services that can be invoked by other domains through explicit contracts. Business logic shall not be duplicated across domains.

These contracts do not necessarily require network calls; in-process service interfaces are appropriate where domains share a deployment.

**Rationale:** Provides one authoritative implementation of each business capability and supports consistent reuse.

## AP-04 — Separation of Presentation and Business Logic

The user interface shall be completely separated from business logic. All business functionality used by the presentation layer shall be accessed through explicitly exposed APIs. The presentation layer shall be responsible for user interaction, rendering, and UI-specific state, not domain rules.

This does not require internal domain-to-domain service calls to use HTTP or another network protocol.

**Rationale:** Enables multiple user interfaces and clients to use the same business capabilities without duplicating business logic.
