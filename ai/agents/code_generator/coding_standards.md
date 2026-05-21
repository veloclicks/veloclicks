# Code Generator Coding Standards

## Function Naming

- Function names must be lowercase with underscores separating words
- Private functions must be prepended with underscore
- Examples:
  - `get_user_activities()` — public
  - `_fetch_from_strava()` — private
  - `_calculate_sync_window()` — private

## Documentation

- Every function must have a comment above the definition explaining what it does
- Use clear, concise language (one line typically sufficient)
- Include additional inline comments after the definition for complex logic
- Example:
```python
# Fetch activities from Strava for the given time window
def fetch_activities(user_id, after_epoch, before_epoch):
    # Only query activities within the valid date range
    activities = strava_client.get_activities(...)
    return activities
```

## Code Formatting

- Keep lines at reasonable length (assume word wrap is available)
- Do NOT artificially break lines to fit 80 character limit
- Prioritize readability over fitting in terminal width
- Use consistent indentation (4 spaces, standard Python)

## Import Organization

- Group imports: standard library, third-party, local
- Sort within each group alphabetically
- Example:
```python
import logging
from functools import wraps

from flask import request, jsonify, current_app

from app.strava.constants import EARLIEST_EPOCH
```

## Code Style

- Follow PEP 8 conventions
- Use meaningful variable names
- Keep functions focused and under 30-40 lines
- Break long functions into smaller, well-named functions
- Use type hints in function signatures when practical

## Comments

- Explain WHY, not WHAT
- Bad: `# Add 1 to count`
- Good: `# Increment to track next available slot`
- Use inline comments for non-obvious logic
- Remove debug print statements unless they're intentional

## Error Handling

- Raise specific exceptions, not generic `Exception`
- Include context in exception messages
- Log errors at appropriate level (info, warning, error)
