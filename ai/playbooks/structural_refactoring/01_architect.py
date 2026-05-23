#!/usr/bin/env python3
"""
Structural Refactoring — Step 1: Architecture Review

Reviews a Flask module for structural issues and produces a phased migration plan.

Usage:
  python3 01_architect.py --code flask/app/strava
  python3 01_architect.py --code flask/app/strava --goal "Introduce a service layer so the analytics domain can call strava cleanly"
  python3 01_architect.py --code flask/app/strava flask/app/auth --model claude-opus-4-7
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_base import (
    build_prompt, call_claude, load_agent, load_code,
    load_context, load_playbook_section, resolve_dirs, save_output,
)


def main():
    parser = argparse.ArgumentParser(description="Structural Refactoring Step 1: Architecture Review")
    parser.add_argument("--code", nargs="+", required=True, help="Code files/directories to analyse (relative to repo root)")
    parser.add_argument("--goal", help="What you are trying to achieve — extra context for the architect")
    parser.add_argument("--model", default="claude-opus-4-6")
    args = parser.parse_args()

    playbook_dir, base_dir, repo_root = resolve_dirs(Path(__file__))

    print("📖 Loading architect agent...")
    agent_def = load_agent("architect", base_dir)

    print("📖 Loading context...")
    context = load_context(base_dir)

    print("📖 Loading playbook instructions...")
    playbook_instructions = load_playbook_section(playbook_dir / "playbook.md", "architect")

    print(f"📖 Loading code: {', '.join(args.code)}")
    code = load_code(args.code, repo_root)

    task_input = code
    if args.goal:
        task_input = f"## Goal\n{args.goal}\n\n{code}"

    prompt = build_prompt(context, agent_def, playbook_instructions, task_input)

    print("\n" + "=" * 80)
    print("🤖 Running architecture review...")
    print("=" * 80 + "\n")

    result = call_claude(prompt, args.model, max_tokens=8000)
    print(result)

    module = args.code[0].rstrip("/").split("/")[-1]
    output_path = save_output(result, f"01_arch_review_{module}", "Structural Architecture Review", base_dir)

    print(f"\n✅ Saved to: {output_path}")
    print(f"\n👉 Next step:")
    print(f"   python3 02_developer.py --analysis {output_path.relative_to(repo_root)} --phase 1")


if __name__ == "__main__":
    main()
