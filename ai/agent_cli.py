#!/usr/bin/env python3
"""
Simple agent CLI for code analysis and refactoring suggestions.

Usage:
  python agent_cli.py --agent architect --task "Review auth module" --code flask/auth flask/models
"""

import argparse
import os
import sys
from pathlib import Path
import anthropic

from dotenv import load_dotenv
load_dotenv()


def read_file(path: Path) -> str:
    """Read a file safely."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Error reading file: {e}]"


def load_markdown_files(folder: Path) -> str:
    """Load all .md files from a folder in sorted order."""
    if not folder.exists():
        return f"[Folder not found: {folder}]"
    
    parts = []
    for file in sorted(folder.glob("*.md")):
        parts.append(f"\n## {file.name}\n")
        parts.append(read_file(file))
    
    return "\n".join(parts).strip()


def load_agent(agent_name: str, base_dir: Path) -> str:
    """Load agent system prompt and constraints."""
    agent_dir = base_dir / "agents" / agent_name
    if not agent_dir.exists():
        return f"[Agent not found: {agent_name}]"
    return load_markdown_files(agent_dir)


def load_context(base_dir: Path) -> str:
    """Load all context files."""
    context_dir = base_dir / "context"
    return load_markdown_files(context_dir)


def load_code(code_paths: list[str], repo_root: Path) -> str:
    """Load code files from repository."""
    if not code_paths:
        return ""
    
    parts = ["# CODE CONTEXT\n"]
    
    for code_path in code_paths:
        # Try as file first
        path = repo_root / code_path
        if path.is_file():
            parts.append(f"\n## FILE: {code_path}\n")
            parts.append(read_file(path))
        # Try as directory
        elif path.is_dir():
            parts.append(f"\n## DIRECTORY: {code_path}\n")
            for file in sorted(path.rglob("*.py")):
                relative_path = file.relative_to(repo_root)
                parts.append(f"\n### {relative_path}\n")
                content = read_file(file)
                # Truncate very long files
                if len(content) > 10000:
                    content = content[:10000] + f"\n... [truncated, original {len(content)} chars] ..."
                parts.append(content)
        else:
            parts.append(f"\n## NOT FOUND: {code_path}\n")
    
    return "\n".join(parts).strip()


def build_prompt(agent_name: str, task: str, context: str, agent_def: str, code: str) -> str:
    """Build the complete prompt for Claude."""
    sections = [
        "# SHARED CONTEXT\n",
        context,
        f"\n# AGENT: {agent_name.upper()}\n",
        agent_def,
        f"\n# TASK\n",
        task,
    ]
    
    if code:
        sections.append(code)
    
    return "\n".join(sections).strip()


def run_agent(agent_name: str, task: str, code_paths: list[str], model: str = "claude-sonnet-4-20250514"):
    """Run an agent with the given task."""
    
    # Determine base directory (where ai/ folder is)
    # Assume this script is in veloclicks/ai/agents/
    script_dir = Path(__file__).parent
    base_dir = script_dir / "ai" if (script_dir / "ai").exists() else script_dir
    repo_root = base_dir.parent if base_dir.name == "ai" else script_dir
    
    print(f"📂 Base directory: {base_dir}")
    print(f"📂 Repo root: {repo_root}\n")
    
    # Load all components
    print(f"📖 Loading {agent_name} agent...")
    agent_def = load_agent(agent_name, base_dir)
    
    print("📖 Loading context...")
    context = load_context(base_dir)
    
    if code_paths:
        print(f"📖 Loading code files: {', '.join(code_paths)}")
        code = load_code(code_paths, repo_root)
    else:
        code = ""
    
    # Build prompt
    prompt = build_prompt(agent_name, task, context, agent_def, code)
    
    print("\n" + "="*80)
    print(f"🤖 Running {agent_name} agent...")
    print("="*80 + "\n")
    
    # Call Claude API
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    
    # Extract and print response
    result = response.content[0].text
    print(result)
    
    print("\n" + "="*80)
    print("✅ Analysis complete")
    print("="*80)
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run agent analysis on code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent_cli.py --agent architect --task "Review auth module for performance" --code flask/auth
  python agent_cli.py --agent architect --task "Refactor login to separate Lambda" --code flask/auth flask/models
  python agent_cli.py --agent architect --task "Analyze strava integration" --code flask/strava
        """
    )
    
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent to run (e.g., architect, engineer)"
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task description for the agent"
    )
    parser.add_argument(
        "--code",
        nargs="*",
        default=[],
        help="Code files/directories to analyze (optional)"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model to use (default: claude-sonnet-4-20250514)"
    )
    
    args = parser.parse_args()
    
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run agent
    run_agent(args.agent, args.task, args.code, args.model)


if __name__ == "__main__":
    main()