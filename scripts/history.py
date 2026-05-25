#!/usr/bin/env python3
"""Generates build/history.html — the archive listing all published daily briefings.

Discovers published dates by listing YYYY-MM-DD.html keys in the S3 bucket,
then merges in today's build date (which may not be in S3 yet). Groups by month,
newest first.
"""
import argparse
import sys
from datetime import date
from itertools import groupby
from pathlib import Path

import boto3
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULT_BUILD_DIR = REPO_ROOT / "build"
DEFAULT_BUCKET = "prates-fyi-news"


def list_s3_dates(bucket: str) -> list:
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    dates = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if len(key) == 15 and key.endswith(".html"):
                try:
                    dates.append(date.fromisoformat(key[:-5]))
                except ValueError:
                    pass
    return sorted(dates)


def group_by_month(dates: list) -> list:
    descending = sorted(dates, reverse=True)
    groups = []
    for month_key, items in groupby(descending, key=lambda d: (d.year, d.month)):
        month_date = date(month_key[0], month_key[1], 1)
        groups.append({
            "month_label": month_date.strftime("%B %Y"),
            "dates": list(items),
        })
    return groups


def render_history(month_groups: list, output_dir: Path) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    html = env.get_template("history.html").render(
        nav_active="archive",
        month_groups=month_groups,
    )
    (output_dir / "history.html").write_text(html)


def build_history(
    today: date,
    bucket: str = DEFAULT_BUCKET,
    output_dir: Path = DEFAULT_BUILD_DIR,
) -> None:
    import os
    output_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("ENV") == "prod":
        s3_dates = list_s3_dates(bucket)
    else:
        print("Skipping S3 date listing (ENV != prod)", file=sys.stderr)
        s3_dates = []
    all_dates = sorted(set(s3_dates) | {today})
    month_groups = group_by_month(all_dates)
    render_history(month_groups, output_dir)
    print(f"✓ Rendered history.html ({len(all_dates)} dates)", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate history.html")
    parser.add_argument("--date", help="Build date YYYY-MM-DD (default: today)")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--output-dir", default=str(DEFAULT_BUILD_DIR))
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    build_history(today=today, bucket=args.bucket, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
