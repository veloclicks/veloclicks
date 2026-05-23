#!/usr/bin/env python3
"""
Structural Refactoring — Step 2: Developer Implementation

Takes the architect's review and implements one phase — writes files to disk.
Review changes in VS Code, then commit manually.

Usage:
  python3 02_developer.py --analysis ai/output/playbook/01_arch_review_strava_*.md --phase 1 --code flask/app/strava
  python3 02_developer.py --analysis ai/output/playbook/01_arch_review_strava_*.md --phase 2 --code flask/app/strava
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_base import (
    build_prompt, call_claude, load_agent, load_code, load_context,
    load_playbook_section, read_file, resolve_dirs, save_output,
)


def apply_code_changes(generation_output: str, repo_root: Path) -> dict:
    """Parse CREATE/MODIFY markers from output and write files to disk."""
    changes = {"files_created": 0, "files_modified": 0}
    lines = generation_output.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if "CREATE:" in line and ("✓" in line or line.startswith("CREATE")):
            file_path = line.split("CREATE:")[1].strip()
            i += 1
            content_lines = []
            in_code_block = False

            while i < len(lines):
                current = lines[i]
                if any(x in current for x in ["✓ MODIFY:", "✓ DELETE:", "MODIFY:", "DELETE:"]):
                    break
                if "```" in current:
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

            while content_lines and not content_lines[-1].strip():
                content_lines.pop()

            if file_path and content_lines:
                full_path = repo_root / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("\n".join(content_lines) + "\n", encoding="utf-8")
                print(f"  ✓ Created: {file_path}")
                changes["files_created"] += 1
            continue

        if "MODIFY:" in line and ("✓" in line or line.startswith("MODIFY")):
            file_path = line.split("MODIFY:")[1].strip()
            print(f"  ⚠️  Modified: {file_path} (review diff above before committing)")
            changes["files_modified"] += 1

        i += 1

    return changes


def main():
    parser = argparse.ArgumentParser(description="Structural Refactoring Step 2: Developer")
    parser.add_argument("--analysis", required=True, help="Path to architect's review (relative to repo root)")
    parser.add_argument("--phase", required=True, type=int, choices=[1, 2, 3, 4], help="Phase number to implement")
    parser.add_argument("--code", nargs="+", required=True, help="Code files/directories to include (relative to repo root)")
    parser.add_argument("--model", default="claude-opus-4-6")
    args = parser.parse_args()

    playbook_dir, base_dir, repo_root = resolve_dirs(Path(__file__))

    analysis_path = repo_root / args.analysis
    if not analysis_path.exists():
        print(f"❌ Error: File not found: {analysis_path}")
        sys.exit(1)

    print(f"📖 Loading architect review: {args.analysis}")
    arch_review = read_file(analysis_path)

    print("📖 Loading developer agent...")
    agent_def = load_agent("developer", base_dir)

    print("📖 Loading context...")
    context = load_context(base_dir)

    print("📖 Loading playbook instructions...")
    playbook_instructions = load_playbook_section(playbook_dir / "playbook.md", "developer")

    print(f"📖 Loading code: {', '.join(args.code)}")
    code = load_code(args.code, repo_root)

    task_input = f"Implement Phase {args.phase}.\n\n# ARCHITECT REVIEW\n{arch_review}\n\n{code}"

    prompt = build_prompt(context, agent_def, playbook_instructions, task_input)

    print("\n" + "=" * 80)
    print(f"🤖 Developer — implementing Phase {args.phase}...")
    print("=" * 80 + "\n")

    result = call_claude(prompt, args.model, max_tokens=8000)
    print(result)

    output_path = save_output(
        result,
        f"02_developer_phase_{args.phase}",
        f"Developer Output — Phase {args.phase}",
        base_dir,
    )

    print("\n" + "=" * 80)
    print("💾 Writing files to disk...")
    print("=" * 80)

    changes = apply_code_changes(result, repo_root)

    print("\n" + "=" * 80)
    print(f"✅ Phase {args.phase} complete")
    print(f"📝 Output saved to: {output_path}")
    print(f"📁 Files: {changes['files_created']} created, {changes['files_modified']} modified")
    print(f"\n👀 Review changes, then commit:")
    print(f"   git add .")
    print(f"   git commit -m \"Phase {args.phase}: [description]\"")
    if args.phase < 4:
        print(f"\n👉 Next phase:")
        print(f"   python3 02_developer.py --analysis {args.analysis} --phase {args.phase + 1} --code {' '.join(args.code)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
