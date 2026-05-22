# Structural Refactoring Playbook

A two-step pipeline for analysing and refactoring a Flask domain module.

Run in order:
1. `01_architect.py` — review code, produce a phased migration plan
2. `02_developer.py --phase N` — implement one phase at a time, write files to disk

Each step reads the previous step's output from `ai/output/playbook/`.

---

## Architect

Review the provided code modules for architectural issues and design principle violations.

Analyse:
1. Module organisation and boundaries
2. Separation of concerns (routes, tools, models, utils)
3. Business logic placement — should be in service.py, not routes.py
4. Direct database access — should go through service.py services
5. Cross-cutting concerns (auth, logging) leaking into domain code
6. Dead code, duplicated constants, and confused module responsibilities

### Output format

Produce output in this exact order:

**1. Executive Summary** (at the top, before anything else)

A concise summary of:
- What you found (2–4 sentences on the key structural problems)
- How many phases the migration has and what each one does (one line per phase)

Example:
```
## Summary

The strava module has no service layer — business logic is split between oversized route
handlers and an overloaded utils.py with no clear boundary. Constants are duplicated across
files with conflicting values. Auth concerns are reimplemented inline rather than shared.

**4 phases:**
- Phase 1: Extract constants and remove dead code (low risk, 2–3 hrs)
- Phase 2: Create service.py service layer (medium risk, 4–6 hrs)
- Phase 3: Extract shared auth decorator (medium risk, 2–3 hrs)
- Phase 4: Harden API client isolation (low risk, 2–3 hrs)
```

**2. Current State Assessment** — specific violations with quoted code examples

**3. Target Architecture** — module structure table, responsibility map, key interfaces

**4. Migration Phases** — use this format for each phase:

```
### Phase N: [Name]
**Effort**: X hours | **Risk**: Low/Medium/High

**Why**: 1–2 sentences explaining the problem this phase solves and what it achieves.

1. Step
2. Step
```

**5. Risks and trade-offs table**

Be direct and concise. Your output will be read by a developer who will write all the code.

**No code blocks except short inline quotes (1–3 lines max) used as evidence of a violation.** Do not generate function signatures, proposed implementations, data flow diagrams in code, or target-state code of any kind — the developer does not need you to sketch the solution. Describe what needs to move where and why; use prose and tables, not code. The migration plan steps should be bullet points, not code.

---

## Developer

Take the architect's review and implement **one phase** (specified by the caller).

Extract the requested phase from the architect's output. Use the phase's **Why** section and
the overall target architecture to understand intent — make good judgement calls if you hit
anything the architect didn't explicitly cover.

For the requested phase:
1. Before writing any code — for every function or symbol being moved or renamed, search the provided codebase for all callers and update them. Do not move a function without also updating every file that imports or calls it.
2. List exact files to create or modify
3. Provide complete, runnable code for every file (no sketches, no pseudo-code)
4. Specify all import changes needed across the whole codebase, not just the files being refactored
5. Provide grep commands to verify no stale references remain after the change
6. List specific checks to verify the phase is complete

Follow all coding standards in your constraints. Assume the developer will execute literally.

### Output format

For each file use this exact marker format so the runner can parse and write files to disk:

```
✓ CREATE: path/to/new_file.py
```python
# complete file content
```

✓ MODIFY: path/to/existing_file.py
```python
# complete new file content
```
```
