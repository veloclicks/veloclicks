Usage

- cd /Users/patrick/dev/veloclicks/ai
- source .venv/bin/activate
- python3 agent_cli.py --agent architect --task "Review strava module. Identify where design preferences are not being followed and suggest refactorings" --code flask/app/strava

Iteration 1:
Had the following:
context/product_overview.md
context/architecture_overview.md
context/architectrue_design_principles.md
context/domain_model.md
context/texh_stack.md

agents/architect/system.md
agents/architect/constraints.md

Iteration 1 - Review strava
python3 agent_cli.py --agent architect --task "Review strava module. Identify where design preferences are not being followed and suggest refactorings" --code flask/app/strava

It did a good job but also suggested using @dataclass decorator which I don't want to use. Thus I'd need to add a contraint to not use this

Decided to create a separate playbook script for a structural review and have ended up with this informal methodology (see bottomg)

-- Engineer agent
python3 playbooks/structural_refactoring_engineering.py --analysis ai/output/playbook/structural_arch_review_strava_20260520_160126.md


Best Practises:
## I've devloped this folder strcuture:

- agents: contains specs for various agents
- context : overall context files describing the probem domain, architecture patterns etc
- playbooks : various different playbooks for different scenarios (e.g. refactor review). INcludes python scripts and .md files

## agents/{agent_name}/
- `system.md` — How the agent thinks and what it does
- `constraints.md` — What it should NOT do

## context/
- `architecture_overview.md` — System structure, directory layout, deployment
- `domain_model.md` — Key concepts (Activity, Athlete, FTP, Zones, Classification)
- `tech_stack.md` — Technologies (Flask, Postgres, Next.js, Lambda, Claude)
- `design_principles.md` — Code organization, performance goals, LLM usage

## playbooks/
- `playbook_name.py` — Executable script
- `playbook_name.md` — Task-specific guidance for the agent


## Flow
```
python3 playbooks/playbook_name.py --code flask/app/strava

→ Loads agents/{agent}/system.md + constraints.md
→ Loads context/* (shared knowledge)
→ Loads playbooks/playbook_name.md (task guidance)
→ Loads your code

→ Claude produces analysis
→ Saved to output/playbook/
```