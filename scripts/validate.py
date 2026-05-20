#!/usr/bin/env python3
"""Validates data/articles.json and data/staging/*.json against their schemas.

Usage (CI — pass only the files that changed):
    python scripts/validate.py data/articles.json data/staging/2026-05-20.json

Exits non-zero if any file fails validation. Skips files whose paths
don't match a known schema (e.g. unrelated JSON).
"""
import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).parent.parent
SCHEMAS = {
    "articles": REPO_ROOT / "schemas" / "article.schema.json",
    "staging": REPO_ROOT / "schemas" / "staging.schema.json",
}


def detect_schema(path: Path) -> str | None:
    """Return 'articles', 'staging', or None for unrecognised paths."""
    if path.name == "articles.json":
        return "articles"
    if path.parent.name == "staging" and path.suffix == ".json":
        return "staging"
    return None


def validate_file(path: Path) -> None:
    """Validate path against its schema. Raises on failure or unknown path."""
    kind = detect_schema(path)
    if kind is None:
        raise ValueError(f"Unknown schema for {path}")
    schema = json.loads(SCHEMAS[kind].read_text())
    data = json.loads(path.read_text())
    jsonschema.validate(instance=data, schema=schema)


def main() -> None:
    if not sys.argv[1:]:
        print("Usage: validate.py <file> [<file> ...]", file=sys.stderr)
        sys.exit(1)

    failed = False
    for arg in sys.argv[1:]:
        path = Path(arg)
        kind = detect_schema(path)
        if kind is None:
            print(f"skip {arg} (no schema)", file=sys.stderr)
            continue
        try:
            validate_file(path)
            print(f"✓ {arg}", file=sys.stderr)
        except jsonschema.ValidationError as e:
            print(f"✗ {arg}: {e.message} (path: {list(e.absolute_path)})", file=sys.stderr)
            failed = True
        except Exception as e:
            print(f"✗ {arg}: {e}", file=sys.stderr)
            failed = True

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
