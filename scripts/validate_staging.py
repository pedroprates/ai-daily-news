#!/usr/bin/env python3
"""
PostToolUse hook: validates data/staging/*.json against schemas/staging.schema.json.
Reads the Claude hook payload from stdin. Exits non-zero on schema violations.
Also usable standalone: python3 scripts/validate_staging.py data/staging/YYYY-MM-DD.json
"""
import json
import sys
import fnmatch
from pathlib import Path

import jsonschema


SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "staging.schema.json"


def validate(file_path: str) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    data = json.loads(Path(file_path).read_text())
    jsonschema.validate(instance=data, schema=schema)


def main():
    # Standalone mode: python3 scripts/validate_staging.py <file>
    if sys.argv[1:]:
        failed = False
        for arg in sys.argv[1:]:
            try:
                validate(arg)
                print(f"✓ {arg} valid", file=sys.stderr)
            except jsonschema.ValidationError as e:
                print(f"✗ {arg}: {e.message} (path: {list(e.absolute_path)})", file=sys.stderr)
                failed = True
            except Exception as e:
                print(f"✗ {arg}: {e}", file=sys.stderr)
                failed = True
        if failed:
            sys.exit(1)
        return

    # Hook mode: reads stdin JSON from Claude's PostToolUse event
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")

    if not fnmatch.fnmatch(file_path, "*/data/staging/*.json"):
        sys.exit(0)

    try:
        validate(file_path)
        print(f"✓ {file_path} valid against staging schema", file=sys.stderr)
    except jsonschema.ValidationError as e:
        print(f"✗ Schema validation failed for {file_path}:", file=sys.stderr)
        print(f"  {e.message}", file=sys.stderr)
        print(f"  Path: {list(e.absolute_path)}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Validation error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
