#!/usr/bin/env python3
"""
Generate env.local.json for `sam local start-api`, sourced from the repo's
own .env — so local secrets have one home (.env) instead of being duplicated
into a second file by hand.

Usage: python3 generate_local_env.py
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"
OUTPUT_FILE = Path(__file__).resolve().parent / "env.local.json"

VARS_NEEDED = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "SECRET_KEY",
]


def read_env(path):
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main():
    env = read_env(ENV_FILE)
    missing = [v for v in VARS_NEEDED if v not in env]
    if missing:
        raise SystemExit(f"Missing from .env: {', '.join(missing)}")

    # template.yaml's own Environment block sets DATABASE_URL via !Ref DatabaseUrl.
    # With no --parameter-overrides, SAM leaves that unresolved as a literal
    # placeholder string, and db.py checks DATABASE_URL before POSTGRES_* — so it
    # must be set explicitly here to override the template's broken placeholder.
    database_url = (
        f"postgresql://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )

    import json
    payload = {
        "AuthFunction": {
            "DATABASE_URL": database_url,
            "SECRET_KEY": env["SECRET_KEY"],
        }
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
