# Veloclicks Engineering Standards

These are implementation standards, separate from architecture principles and architecture decision records. Apply to new or substantially modified code; improve legacy code incrementally rather than requiring a wholesale rewrite.

## 1. Documentation — mandatory

- Every non-trivial module, class, public function, method, and private helper must have a meaningful docstring describing its purpose. Document parameters, return values, exceptions, units, and non-obvious side effects where relevant. Do not merely restate the name.
- Within functions, add explanatory comments before non-obvious blocks of logic, especially branching rules, transformations, algorithms, assumptions, thresholds, and workarounds. Explain **why** the block exists and what it achieves, not a line-by-line translation of Python.
- Keep comments and docstrings current when behaviour changes. Do not leave misleading or placeholder documentation.
- Straightforward glue code and self-explanatory statements do not need redundant comments. Documentation quality is a review requirement, not something a formatter can fully enforce.

## 2. Python design

- Follow PEP 8, PEP 257, and conventional Python idioms; prefer clear, explicit code over Java-style boilerplate.
- Use module-level functions for stateless operations. Use classes when they hold meaningful state, enforce invariants, implement a coherent abstraction, or provide dependency injection. Do not create classes solely to group functions.
- Use `@dataclass` for simple typed data structures when appropriate; use existing SQLAlchemy models for persistence.
- Public names have no leading underscore. Prefix implementation-only functions and attributes with one underscore; Python privacy is by convention, not Java-style enforcement. Avoid double-underscore name mangling unless there is a specific inheritance-related reason.
- Use decorators for established cross-cutting concerns (such as Flask routes, authentication, caching) when they genuinely simplify the code. Avoid elaborate custom decorator chains that obscure control flow.
- Use type hints for new and materially changed service interfaces.

## 3. Domain code organisation

- Keep code within cohesive business domains. Prefer consistent layers **within** a domain: router/controller (transport), service (business behaviour), repository/data access, and model/schema where needed.
- Routers validate/translate requests and responses; services own business rules; repositories own persistence operations. Do not force an empty layer or an identical folder layout on every domain.
- Domain services expose explicit interfaces to other domains; do not reach into another domain's internals or duplicate its business rules.
- Keep deployment-specific adapters (including AWS Lambda handlers) thin and separate from application logic.

## 4. Functions and maintainability

- Prefer short, single-purpose functions. If a function has multiple distinct responsibilities, complex nesting, or repeated blocks, extract named helpers. Avoid arbitrary hard line-count limits.
- Prefer descriptive names, explicit dependencies, early returns where helpful, and minimal hidden side effects.
- Handle errors deliberately; avoid blanket exception suppression.
- Include regression tests for behaviour changes and edge cases. Tests should document the intended behaviour.

## 5. Tooling and enforcement

- Use Ruff for linting/formatting when adopted in the repository; configure rules explicitly rather than assuming every default is appropriate.
- Automate mechanical checks in CI where practical, including formatting, unused imports, and test execution.
- Code review (including AI-assisted changes) must verify meaningful docstrings and comments for non-obvious code blocks: these cannot be guaranteed by linting alone.
- Introduce new lint/format tooling separately and assess the existing codebase before applying repo-wide formatting.
