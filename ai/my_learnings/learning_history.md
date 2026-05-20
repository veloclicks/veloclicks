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