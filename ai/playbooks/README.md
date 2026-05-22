
# Cheat Sheet

python3 playbooks/structural_refactoring/01_architect.py --code flask/app/strava --goal "review the strava module against the architect's design principles and propose actionable refactorings that an engineer can implement"


# Playbooks

Playbooks are multi-step AI pipelines for structured engineering tasks. Each playbook lives in its own folder and follows the same pattern: run scripts in order, review output between steps, commit when happy.

---

## How playbooks work

Each playbook folder contains:
- `playbook.md` — describes the pipeline and provides per-agent instructions
- Numbered Python scripts (`01_*.py`, `02_*.py`) — one per pipeline step
- Scripts are run manually in order; each writes output to `ai/output/playbook/`

The shared infrastructure lives in `playbook_base.py` (this folder). Individual scripts import from it and stay thin.

---

## Available playbooks

### `structural_refactoring/`

Analyses a Flask module for architectural issues and implements fixes phase by phase.

**Step 1 — Architecture review:**
```bash
cd veloclicks/ai
python3 playbooks/structural_refactoring/01_architect.py --code flask/app/strava
```

With a goal (recommended — gives the architect useful extra context):
```bash
python3 playbooks/structural_refactoring/01_architect.py \
  --code flask/app/strava \
  --goal "Introduce a service.py service layer so the analytics domain can call strava without touching the DB directly"
```

#### My example:
python3 playbooks/structural_refactoring/01_architect.py --code flask/app/strava --goal "review the strava module against the architect's design principles and propose actionable refactorings that an engineer can implement"

Multiple modules at once:
```bash
python3 playbooks/structural_refactoring/01_architect.py \
  --code flask/app/strava flask/app/auth \
  --goal "Review both modules — auth decorator needs to be shareable across domains"
```

**Step 2 — Implement a phase:**
```bash
python3 playbooks/structural_refactoring/02_developer.py \
  --analysis ai/output/playbook/01_arch_review_strava_20260522_120000.md \
  --phase 1 \
  --code flask/app/strava
```

Run phases in order. After each phase: review the changes in VS Code, run the app, then commit before moving to the next phase.

---

## Passing extra context with --goal

`--goal` is a free-text prompt you pass to the architect to describe what you're trying to achieve. Use it to:

- Focus the review on a specific concern: `--goal "We need to add caching — review the current API call patterns first"`
- Explain a constraint: `--goal "Auth module cannot change — strava refactor must work with existing auth decorator"`
- Set scope: `--goal "Phase 1 only — we're in a freeze, just identify the quick wins"`

The architect sees your goal before it sees the code, so it shapes the entire review.

---

## Output files

All output lands in `ai/output/playbook/` with a timestamp suffix:
- `01_arch_review_{module}_{timestamp}.md` — architect's analysis
- `02_developer_phase_{N}_{timestamp}.md` — developer's implementation output

Keep these files. They're the paper trail for why changes were made.

---

## Adding a new playbook

1. Create a folder: `playbooks/your_playbook_name/`
2. Add `playbook.md` with a `## AgentName` section for each agent you need
3. Add numbered scripts that import from `playbook_base`
4. Add an entry here

The agents available are in `ai/agents/`. Each agent's `.md` files are loaded in sorted order (numeric prefix controls order).
