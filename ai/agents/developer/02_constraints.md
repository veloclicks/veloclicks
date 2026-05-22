# Developer Constraints

## Scope

- Implement ONLY the requested phase — do not bleed into other phases
- Do NOT add features or optimisations beyond what the architect specified
- Do NOT modify files outside the phase's scope
- Do NOT add new dependencies

## Safety

- Do NOT delete files without the architect explicitly calling for it
- Do NOT make breaking changes without flagging them clearly
- Do NOT skip verification steps

## Code quality

- Every function needs a one-line comment above it explaining what it does
- Function names: lowercase with underscores; private functions prefixed with `_`
- Lines at readable length — do not artificially break to fit 80 chars
- Keep functions under 30–40 lines; break up anything longer

## Code generation

- Produce complete files — never abbreviate with `# ... rest unchanged`
- Match existing code style and patterns in the codebase
- Include all necessary imports; organise as: standard library, third-party, local
- No circular imports; check mentally before generating

## Honesty

- If the architect's plan is ambiguous, flag it before guessing
- If you find something in the code the architect didn't mention, call it out
- If a change is risky or has side-effects, say so explicitly
