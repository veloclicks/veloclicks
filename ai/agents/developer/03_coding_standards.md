# Developer Coding Standards

## Naming

- Functions: `get_user_activities()` — public; `_fetch_from_strava()` — private
- Variables: descriptive, lowercase with underscores
- Constants: `UPPER_SNAKE_CASE`

## Imports

Group in this order, alphabetically within each group:
```python
import logging
from functools import wraps

from flask import request, jsonify, current_app

from app.strava.constants import EARLIEST_EPOCH
```

## Comments

Explain WHY, not WHAT:
- Bad: `# Add 1 to count`
- Good: `# Offset by 1 because the Strava API uses 1-based page numbers`

One-line comment above every function definition. Inline comments only for non-obvious logic.
Remove debug `print()` statements — use logging instead.

## Formatting

- 4-space indentation (standard Python)
- Readable line length — prioritise clarity over terminal width
- Type hints in function signatures where practical

## Refactoring markers

When moving code between files, add a brief inline comment on the first line of the moved block:
```python
# Moved from routes.py — Phase 2
```
Do NOT comment out old code. Do NOT add timestamps. Git history has both.

## Error handling

- Raise specific exceptions with context messages, not bare `Exception`
- Log at the appropriate level (`logger.warning`, `logger.error`)
