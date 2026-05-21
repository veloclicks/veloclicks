#!/usr/bin/env python3
"""
Structural Refactoring Code Generator Playbook

Takes an engineer's implementation plan and generates code changes for a specific phase.

Usage:
  python3 structural_refactoring_code_generator.py \
    --analysis output/playbook/structural_refactoring_engineer_phases_1_2_5_6_*.md \
    --phase 1
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
    """Load agent system prompt, constraints, and coding standards."""
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


def build_prompt(agent_name: str, phase: int, context: str, agent_def: str, playbook_guidance: str, engineer_plan: str) -> str:
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
        f"\n# ENGINEER IMPLEMENTATION PLAN\n",
        engineer_plan,
        f"\n# TASK\n",
        f"Generate code changes for Phase {phase} only.",
        f"",
        f"Extract Phase {phase} from the engineer's plan and generate all code changes needed.",
        f"Show before/after diffs for each file modification.",
        f"Be explicit about what's changing and why.",
        f"Follow all coding standards exactly.",
    ])
    
    return "\n".join(sections).strip()


def run_playbook(analysis_file: str, phase: int, model: str = "claude-opus-4-6"):
    """Run the code generator for a specific phase."""
    
    agent_name = "code_generator"
    
    # Determine base directory
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up to veloclicks/ai/
    repo_root = base_dir.parent  # Go up to veloclicks/
    
    print(f"📂 Base directory: {base_dir}")
    print(f"📂 Repo root: {repo_root}\n")
    
    # Load engineer's plan
    analysis_path = repo_root / analysis_file
    if not analysis_path.exists():
        print(f"❌ Error: Analysis file not found: {analysis_path}")
        sys.exit(1)
    
    print(f"📖 Loading engineer's plan: {analysis_file}")
    engineer_plan = read_file(analysis_path)
    
    # Load all components
    print(f"📖 Loading {agent_name} agent...")
    agent_def = load_agent(agent_name, base_dir)
    
    print("📖 Loading context...")
    context = load_context(base_dir)
    
    print("📖 Loading playbook guidance...")
    playbook_guidance = load_playbook_guidance(script_dir, "structural_refactoring_code_generator")
    
    # Build prompt
    prompt = build_prompt(agent_name, phase, context, agent_def, playbook_guidance, engineer_plan)
    
    print("\n" + "="*80)
    print(f"🤖 Code Generator - Phase {phase}")
    print("="*80 + "\n")
    
    # Call Claude API
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    response = client.messages.create(
        model=model,
        max_tokens=8000,
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
    output_file = save_analysis(result, phase)
    
    print("\n" + "="*80)
    print(f"✅ Code generation complete for Phase {phase}")
    print(f"📝 Saved to: {output_file}")
    print("\n⚠️  REVIEW THE CHANGES ABOVE BEFORE COMMITTING")
    print("="*80)
    
    return result


def save_analysis(analysis: str, phase: int) -> str:
    """Save analysis to a markdown file."""
    from datetime import datetime
    
    # Create output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"code_generator_phase_{phase}_{timestamp}.md"
    
    # Create output/playbook folder if needed
    output_dir = Path("output/playbook")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / filename
    
    # Write file with metadata
    content = f"""# Code Generator Output - Phase {phase}

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{analysis}
"""
    
    output_path.write_text(content, encoding="utf-8")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Code Generator Playbook - Generate code changes for a specific phase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 structural_refactoring_code_generator.py \\
    --analysis output/playbook/structural_refactoring_engineer_phases_1_2_5_6_*.md \\
    --phase 1

  python3 structural_refactoring_code_generator.py \\
    --analysis output/playbook/structural_refactoring_engineer_phases_1_2_5_6_20260520_174332.md \\
    --phase 2
        """
    )
    
    parser.add_argument(
        "--analysis",
        required=True,
        help="Path to engineer's implementation plan (relative to repo root)"
    )
    parser.add_argument(
        "--phase",
        required=True,
        type=int,
        choices=[1, 2, 5, 6],
        help="Phase number to generate code for (1, 2, 5, or 6)"
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
    run_playbook(args.analysis, args.phase, args.model)


if __name__ == "__main__":
    main()