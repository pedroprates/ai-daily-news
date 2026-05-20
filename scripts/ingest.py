#!/usr/bin/env python3
"""Merges all data/staging/*.json files into data/articles.json.

Deduplicates by article id. Idempotent: safe to run multiple times.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).parent.parent
STAGING_DIR = REPO_ROOT / "data" / "staging"
ARTICLES_PATH = REPO_ROOT / "data" / "articles.json"
ARTICLE_SCHEMA_PATH = REPO_ROOT / "schemas" / "article.schema.json"

_EMPTY_MASTER = {"version": 1, "updated_at": "", "articles": []}


def load_master(path: Path) -> dict:
    if not path.exists():
        return dict(_EMPTY_MASTER)
    return json.loads(path.read_text())


def load_staging_articles(staging_dir: Path) -> list:
    articles = []
    for f in sorted(staging_dir.glob("*.json")):
        articles.extend(json.loads(f.read_text()))
    return articles


def ingest(master: dict, staging_articles: list) -> tuple:
    existing_ids = {a["id"] for a in master["articles"]}
    new_articles = [a for a in staging_articles if a["id"] not in existing_ids]
    master["articles"].extend(new_articles)
    master["updated_at"] = datetime.now(timezone.utc).isoformat()
    return master, len(new_articles)


def validate_master(master: dict, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text())
    jsonschema.validate(instance=master, schema=schema)


def main() -> None:
    staging_articles = load_staging_articles(STAGING_DIR)
    master = load_master(ARTICLES_PATH)
    master, added = ingest(master, staging_articles)
    validate_master(master, ARTICLE_SCHEMA_PATH)
    ARTICLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_PATH.write_text(json.dumps(master, indent=2, ensure_ascii=False) + "\n")
    print(f"✓ Ingested {added} new articles ({len(master['articles'])} total)", file=sys.stderr)


if __name__ == "__main__":
    main()
