#!/usr/bin/env python3
"""Shared infrastructure for all playbook scripts."""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()


def read_file(path: Path) -> str:
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
    """Load all .md files from an agent's directory in sorted order."""
    agent_dir = base_dir / "agents" / agent_name
    if not agent_dir.exists():
        return f"[Agent not found: {agent_name}]"
    return load_markdown_files(agent_dir)


def load_context(base_dir: Path) -> str:
    """Load all shared context .md files."""
    return load_markdown_files(base_dir / "context")


def load_playbook_section(playbook_md: Path, agent_name: str) -> str:
    """Extract the section for a specific agent from the playbook .md.

    Matches a ## heading whose text equals the agent name (normalised:
    underscores → spaces, title-cased).  Returns everything up to the
    next ## heading.
    """
    if not playbook_md.exists():
        return ""
    heading = agent_name.replace("_", " ").title()
    lines = read_file(playbook_md).split("\n")
    in_section = False
    section_lines = []
    for line in lines:
        if line.startswith("## ") and line[3:].strip().lower() == heading.lower():
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def load_code(code_paths: list[str], repo_root: Path) -> str:
    """Load code files or directories from the repo."""
    if not code_paths:
        return ""
    parts = ["# CODE\n"]
    for code_path in code_paths:
        path = repo_root / code_path
        if path.is_file():
            parts.append(f"\n## FILE: {code_path}\n")
            parts.append(read_file(path))
        elif path.is_dir():
            parts.append(f"\n## DIRECTORY: {code_path}\n")
            for file in sorted(path.rglob("*.py")):
                rel = file.relative_to(repo_root)
                parts.append(f"\n### {rel}\n")
                content = read_file(file)
                if len(content) > 10000:
                    content = content[:10000] + f"\n... [truncated, {len(content)} chars total]"
                parts.append(content)
        else:
            parts.append(f"\n## NOT FOUND: {code_path}\n")
    return "\n".join(parts).strip()


def build_prompt(context: str, agent_def: str, playbook_instructions: str, task_input: str) -> str:
    """Assemble the full prompt from its components."""
    sections = ["# SHARED CONTEXT\n", context, "\n# AGENT\n", agent_def]
    if playbook_instructions:
        sections.extend(["\n# PLAYBOOK INSTRUCTIONS\n", playbook_instructions])
    if task_input:
        sections.extend(["\n# INPUT\n", task_input])
    return "\n".join(sections).strip()


def call_claude(prompt: str, model: str = "claude-opus-4-6", max_tokens: int = 4000) -> str:
    """Call the Claude API and return the text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def save_output(content: str, filename_prefix: str, header: str, base_dir: Path) -> Path:
    """Save output to ai/output/playbook/ with a timestamp suffix."""
    output_dir = base_dir / "output" / "playbook"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{filename_prefix}_{timestamp}.md"
    body = (
        f"# {header}\n\n"
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"---\n\n{content}"
    )
    path.write_text(body, encoding="utf-8")
    return path


def resolve_dirs(script_path: Path) -> tuple[Path, Path, Path]:
    """Return (playbook_dir, base_dir, repo_root) from a script's __file__.

    Expects scripts to live at ai/playbooks/<playbook_name>/<script>.py.
    """
    playbook_dir = script_path.parent           # ai/playbooks/structural_refactoring/
    base_dir = playbook_dir.parent.parent       # ai/
    repo_root = base_dir.parent                 # veloclicks/
    return playbook_dir, base_dir, repo_root
