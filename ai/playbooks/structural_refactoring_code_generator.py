#!/usr/bin/env python3
"""
Structural Refactoring Code Generator Playbook

Takes an engineer's implementation plan and generates code changes for a specific phase.
Writes files to disk. You review in VS Code, then commit manually.

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
        f"For new files, provide complete file content.",
        f"For modified files, show before/after diffs.",
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
    
    # Extract response
    result = response.content[0].text
    print(result)
    
    # Save analysis to output
    output_file = save_analysis(result, phase)
    
    # Write files to disk
    print("\n" + "="*80)
    print(f"💾 Writing changes to disk...")
    print("="*80 + "\n")
    
    changes_made = apply_code_changes(result, repo_root)
    
    print("\n" + "="*80)
    print(f"✅ Phase {phase} complete")
    print(f"📝 Analysis saved to: {output_file}")
    print(f"📁 Files written: {changes_made['files_created']} created, {changes_made['files_modified']} modified")
    print("\n👀 Review changes in VS Code, then commit manually:")
    print("   git add .")
    print(f"   git commit -m \"Phase {phase}: [description]\"")
    print("="*80)
    
    return result


def apply_code_changes(generation_output: str, repo_root: Path) -> dict:
    """Parse Claude's output and write files to disk."""
    changes = {'files_created': 0, 'files_modified': 0}
    
    lines = generation_output.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for CREATE markers (more flexible matching)
        if 'CREATE:' in line and ('✓' in line or line.startswith('CREATE')):
            # Extract file path - handle various formats
            if '✓' in line:
                file_path = line.split('✓')[1].split('CREATE:')[1].strip()
            else:
                file_path = line.split('CREATE:')[1].strip()
            
            # Find the file content (next line starts with ``` usually)
            i += 1
            content_lines = []
            in_code_block = False
            
            while i < len(lines):
                current = lines[i]
                
                # Check for end markers
                if any(x in current for x in ['✓ MODIFY:', '✓ DELETE:', 'MODIFY:', 'DELETE:', 'Summary of Phase', '## File']):
                    break
                
                # Track code blocks
                if '```' in current:
                    in_code_block = not in_code_block
                    if in_code_block:
                        i += 1
                        continue
                    else:
                        i += 1
                        break
                
                if in_code_block or (content_lines and current.strip()):
                    content_lines.append(current)
                
                i += 1
            
            # Remove trailing empty lines
            while content_lines and not content_lines[-1].strip():
                content_lines.pop()
            
            # Write file
            if file_path and content_lines:
                full_path = repo_root / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                content = '\n'.join(content_lines)
                full_path.write_text(content + '\n', encoding='utf-8')
                
                print(f"✓ Created: {file_path}")
                changes['files_created'] += 1
            
            continue
        
        # Look for MODIFY markers
        if 'MODIFY:' in line and ('✓' in line or line.startswith('MODIFY')):
            if '✓' in line:
                file_path = line.split('✓')[1].split('MODIFY:')[1].strip()
            else:
                file_path = line.split('MODIFY:')[1].strip()
            
            print(f"⚠️  Modified: {file_path} (review diffs in output above)")
            changes['files_modified'] += 1
        
        i += 1
    
    return changes


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