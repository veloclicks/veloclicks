#!/usr/bin/env python3
"""
Ad-hoc agent invocation — ask any agent a question without a playbook.

Usage:
  python3 ai/ask.py architect "Is the analytics module well-structured?"
  python3 ai/ask.py architect "Review cross-domain service calls" --code flask/app/analytics
  python3 ai/ask.py architect "Compare these two modules" --code flask/app/strava flask/app/analytics
  python3 ai/ask.py --help
"""

import argparse
import sys
from pathlib import Path

base_dir = Path(__file__).parent        # ai/
repo_root = base_dir.parent             # veloclicks/

sys.path.insert(0, str(base_dir))
from agent_base import build_prompt, call_claude, load_agent, load_code, load_context, save_output


def main():
    parser = argparse.ArgumentParser(
        description="Ask any agent a question ad-hoc, without a playbook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
agents:
  architect   Reviews code structure and design principles
  developer   Implements changes to code

examples:
  python3 ai/ask.py architect "Is the analytics module well-structured?"
  python3 ai/ask.py architect "Review cross-domain service calls" --code flask/app/analytics
        """,
    )
    parser.add_argument("agent", help="Agent to use (e.g. architect, developer)")
    parser.add_argument("task", help="What you want the agent to do")
    parser.add_argument("--code", nargs="+", help="Code files/directories to include (relative to repo root)")
    parser.add_argument("--save", action="store_true", help="Save output to ai/output/ask/")
    parser.add_argument("--model", default="claude-opus-4-6")
    args = parser.parse_args()

    print(f"📖 Loading {args.agent} agent...")
    agent_def = load_agent(args.agent, base_dir)
    if agent_def.startswith("[Agent not found"):
        print(f"❌ {agent_def}")
        sys.exit(1)

    print("📖 Loading context...")
    context = load_context(base_dir)

    task_input = f"## Task\n{args.task}"
    if args.code:
        print(f"📖 Loading code: {', '.join(args.code)}")
        task_input += f"\n\n{load_code(args.code, repo_root)}"

    prompt = build_prompt(context, agent_def, playbook_instructions="", task_input=task_input)

    print("\n" + "=" * 80)
    print(f"🤖 {args.agent.title()} — {args.task}")
    print("=" * 80 + "\n")

    result = call_claude(prompt, args.model, max_tokens=8000)
    print(result)

    if args.save:
        from datetime import datetime
        output_dir = base_dir / "output" / "ask"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{timestamp}_{args.agent}.md"
        output_path.write_text(result, encoding="utf-8")
        print(f"\n✅ Saved to: {output_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
