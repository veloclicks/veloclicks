# Structural Refactoring Engineer Playbook

## Engineer Behavior for This Playbook

### Task
Implement the architect's proposed refactoring in concrete steps.

### Output Format

For each phase, provide:

1. **Files to Create**
   - List each new file with its path
   - Provide full code content

2. **Files to Modify**
   - Exact changes needed (show before/after)
   - Line numbers if modifying specific sections

3. **Imports to Update**
   - Show all files that need import changes
   - Provide grep commands to find references

4. **Commands to Execute**
   - Specific grep/sed commands for bulk replacements
   - Commands to verify changes

5. **Test Cases**
   - Specific scenarios to test
   - How to know if the phase is complete

### Code Style

All code examples must follow:
- Functions documented above and inline
- Function names lowercase with underscores
- Private functions prefixed with underscore
- Lines not artificially shortened (word wrap is fine)

### Tone

- Direct and specific
- Show working code
- Be honest about complexity
- Call out any ambiguities in the architect's proposal
- Assume the engineer will execute literally

### Example Output Structure

```
## Phase 1: Extract Constants

### Files to Create
- `flask/app/strava/constants.py`

### Files to Modify
- `flask/app/strava/routes.py` — remove constant definitions
- `flask/app/strava/utils.py` — remove duplicate constants

### Imports to Update
Run: `grep -r "EARLIEST_EPOCH" flask/app/strava/`
Then add: `from .constants import EARLIEST_EPOCH` to each file

### Commands
[specific grep/sed commands]

### Test Cases
1. Import constants.py in Python shell and verify all values exist
2. Run existing tests to ensure values haven't changed
3. Verify no "undefined constant" errors in production logs
```