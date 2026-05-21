#!/usr/bin/env python3
"""
Structural Refactoring Engineer Playbook

Takes an architect's analysis and produces detailed implementation steps.

Usage:
  python3 structural_refactoring_engineer.py --analysis output/playbook/structural_arch_review_strava_20250520_160126.md
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


def build_prompt(agent_name: str, task: str, context: str, agent_def: str, playbook_guidance: str, architect_analysis: str) -> str:
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
        f"\n# ARCHITECT ANALYSIS\n",
        architect_analysis,
        f"\n# TASK\n",
        task,
    ])
    
    return "\n".join(sections).strip()


def run_playbook(analysis_file: str, model: str = "claude-opus-4-6"):
    """Run the structural refactoring engineer playbook."""
    
    agent_name = "engineer"
    task = """Based on the architect's analysis, provide detailed implementation steps for Phases 1, 2, 5, and 6.

For each phase:
1. List exact files to create or modify
2. Show before/after code (complete and runnable)
3. Specify all import changes needed
4. Provide grep/sed commands for bulk replacements
5. List specific test cases to verify completion
6. Call out any risks or gotchas

Follow all code style standards in the constraints.
Be specific — show actual code, not pseudo-code.
Assume the engineer will execute literally."""
    
    # Determine base directory
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up to veloclicks/ai/
    repo_root = base_dir.parent  # Go up to veloclicks/
    
    print(f"📂 Base directory: {base_dir}")
    print(f"📂 Repo root: {repo_root}\n")
    
    # Load architect analysis
    analysis_path = repo_root / analysis_file
    if not analysis_path.exists():
        print(f"❌ Error: Analysis file not found: {analysis_path}")
        sys.exit(1)
    
    print(f"📖 Loading architect analysis: {analysis_file}")
    architect_analysis = read_file(analysis_path)
    
    # Load all components
    print(f"📖 Loading {agent_name} agent...")
    agent_def = load_agent(agent_name, base_dir)
    
    print("📖 Loading context...")
    context = load_context(base_dir)
    
    print("📖 Loading playbook guidance...")
    playbook_guidance = load_playbook_guidance(script_dir, "structural_refactoring_engineer")
    
    # Build prompt
    prompt = build_prompt(agent_name, task, context, agent_def, playbook_guidance, architect_analysis)
    
    print("\n" + "="*80)
    print(f"🤖 Running structural refactoring engineer...")
    print("="*80 + "\n")
    
    # Call Claude API
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    response = client.messages.create(
        model=model,
        max_tokens=6000,
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
    output_file = save_analysis(result)
    
    print("\n" + "="*80)
    print("✅ Implementation plan complete")
    print(f"📝 Saved to: {output_file}")
    print("="*80)
    
    return result


def save_analysis(analysis: str) -> str:
    """Save analysis to a markdown file."""
    from datetime import datetime
    
    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"structural_refactoring_engineer_phases_1_2_5_6_{timestamp}.md"
    
    # Create output/playbook folder if needed
    output_dir = Path("output/playbook")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / filename
    
    # Write file with metadata
    content = f"""# Structural Refactoring Engineer Implementation Plan

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{analysis}
"""
    
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Structural Refactoring Engineer Playbook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 structural_refactoring_engineer.py --analysis output/playbook/structural_arch_review_strava_20250520_160126.md
        """
    )
    
    parser.add_argument(
        "--analysis",
        required=True,
        help="Path to architect analysis file (relative to repo root)"
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-6",
        help="Claude model to use (default: claude-opus-4-6)"
    )
    
    args = parser.parse_args()
    
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Run playbook
    run_playbook(args.analysis, args.model)


if __name__ == "__main__":
    main()
