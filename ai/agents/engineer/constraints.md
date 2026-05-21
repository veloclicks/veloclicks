# Engineer Constraints

## Code Quality Standards

### Documentation
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

### Function Naming
- Function names must be lowercase with underscores separating words
- Private functions must be prepended with underscore
- Examples:
  - `get_user_activities()` — public
  - `_fetch_from_strava()` — private
  - `_calculate_sync_window()` — private

### Code Formatting
- Keep lines reasonably length (assume word wrap is available)
- Do NOT artificially break lines to fit 80 char limit
- Prioritize readability over fitting in terminal width

## What NOT to Do

- Do not suggest over-engineered solutions
- Do not introduce new design patterns without justification
- Do not recommend complex abstractions for simple problems
- Do not suggest imports that add unnecessary dependencies
- Do not skip documentation — every function needs it
- Do not create functions longer than 30-40 lines (suggest refactoring if needed)

## Implementation Style

- Show actual working code, not pseudo-code or sketches
- Be explicit about file paths and line numbers
- Provide grep/sed commands for find-and-replace when applicable
- Specify the order of changes (dependencies matter)
- Include specific test cases, not just "test this"