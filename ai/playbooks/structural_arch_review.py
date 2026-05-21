#!/usr/bin/env python3
"""
Structural Architecture Review Playbook

Analyzes code modules for architectural issues and design principle violations.

Usage:
  python3 structural_arch_review.py --code flask/app/strava
  python3 structural_arch_review.py --code flask/app/auth flask/app/profile
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# Load .env file
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


def load_playbook_guidance(playbooks_dir: Path, playbook_name: str) -> str:
    """Load playbook-specific guidance for the agent."""
    playbook_file = playbooks_dir / f"{playbook_name}.md"
    if playbook_file.exists():
        return read_file(playbook_file)
    return ""


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


def build_prompt(agent_name: str, task: str, context: str, agent_def: str, playbook_guidance: str, code: str) -> str:
    """Build the complete prompt for Claude."""
    sections = [
        "# SHARED CONTEXT\n",
        context,
        f"\n# AGENT: {agent_name.upper()}\n",
        agent_def,
    ]
    
    if playbook_guidance:
        sections.append("\n# PLAYBOOK GUIDANCE\n")
        sections.append(playbook_guidance)
    
    sections.extend([
        f"\n# TASK\n",
        task,
    ])
    
    if code:
        sections.append(code)
    
    return "\n".join(sections).strip()


def run_playbook(code_paths: list[str], model: str = "claude-opus-4-6"):
    """Run the structural architecture review playbook."""
    
    agent_name = "architect"
    task = """Review the provided code modules for architectural issues and design principle violations.

Analyze:
1. Module organization and boundaries
2. Separation of concerns (routes, tools, models, utils)
3. Business logic placement (should be in tools.py, not routes.py)
4. Direct database access (should go through tools.py services)
5. Code complexity and maintainability
6. Adherence to design principles

Provide:
- Current state assessment
- Specific design principle violations
- Target architecture proposal
- Migration path with phases
- Risks and trade-offs"""
    
    # Determine base directory (where ai/ folder is)
    # Assume this script is in veloclicks/ai/playbooks/
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up to veloclicks/ai/
    repo_root = base_dir.parent  # Go up to veloclicks/
    
    print(f"📂 Base directory: {base_dir}")
    print(f"📂 Repo root: {repo_root}\n")
    
    # Load all components
    print(f"📖 Loading {agent_name} agent...")
    agent_def = load_agent(agent_name, base_dir)
    
    print("📖 Loading context...")
    context = load_context(base_dir)
    
    print("📖 Loading playbook guidance...")
    playbook_guidance = load_playbook_guidance(script_dir, "structural_arch_review")
    
    if code_paths:
        print(f"📖 Loading code files: {', '.join(code_paths)}")
        code = load_code(code_paths, repo_root)
    else:
        code = ""
    
    # Build prompt
    prompt = build_prompt(agent_name, task, context, agent_def, playbook_guidance, code)
    
    print("\n" + "="*80)
    print(f"🤖 Running structural architecture review...")
    print("="*80 + "\n")
    
    # Call Claude API
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
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
    
    # Save to file
    output_file = save_analysis(result, code_paths)
    
    print("\n" + "="*80)
    print("✅ Analysis complete")
    print(f"📝 Saved to: {output_file}")
    print("="*80)
    
    return result


def save_analysis(analysis: str, code_paths: list[str]) -> str:
    """Save analysis to a markdown file."""
    from datetime import datetime
    
    # Extract module name from code path
    module_name = "analysis"
    if code_paths:
        # Use first code path, extract last part
        module_name = code_paths[0].split("/")[-1]
    
    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"structural_arch_review_{module_name}_{timestamp}.md"
    
    # Create output/playbook folder if needed
    output_dir = Path("output/playbook")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / filename
    
    # Write file with metadata
    content = f"""# Structural Architecture Review

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Module**: {module_name}

---

{analysis}
"""
    
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Structural Architecture Review Playbook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 structural_arch_review.py --code flask/app/strava
  python3 structural_arch_review.py --code flask/app/auth flask/app/profile
  python3 structural_arch_review.py --code flask/app/strava --model claude-opus-4-6
        """
    )
    
    parser.add_argument(
        "--code",
        nargs="*",
        default=[],
        help="Code files/directories to analyze (required)"
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-6",
        help="Claude model to use (default: claude-opus-4-6)"
    )
    
    args = parser.parse_args()
    
    # Check for code argument
    if not args.code:
        parser.print_help()
        print("\n❌ Error: --code argument is required")
        sys.exit(1)
    
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run playbook
    run_playbook(args.code, args.model)


if __name__ == "__main__":
    main()