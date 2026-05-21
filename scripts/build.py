#!/usr/bin/env python3
"""Orchestrates the full build: render HTML, generate history, deploy to S3.

Called by deploy.yml after ingest.yml has committed updated articles.json.

Usage:
    python scripts/build.py [--date YYYY-MM-DD] [--bucket BUCKET]
"""
import argparse
from datetime import date
from pathlib import Path

import deploy as deploy_module
import history as history_module
import render as render_module

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_BUILD_DIR = REPO_ROOT / "build"


def run(
    today: date | None = None,
    build_dir: Path = DEFAULT_BUILD_DIR,
    bucket: str = deploy_module.DEFAULT_BUCKET,
    weekly_only: bool = False,
) -> None:
    if today is None:
        today = date.today()
    render_module.render(today=today, output_dir=build_dir, weekly_only=weekly_only)
    history_module.build_history(today=today, bucket=bucket, output_dir=build_dir)
    deploy_module.deploy(build_dir=build_dir, bucket=bucket)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and deploy prates.fyi")
    parser.add_argument("--date", help="Build date YYYY-MM-DD (default: today)")
    parser.add_argument("--bucket", default=deploy_module.DEFAULT_BUCKET)
    parser.add_argument("--weekly-only", action="store_true", help="Skip homepage and daily archive; render weekly pages only")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    run(today=today, build_dir=DEFAULT_BUILD_DIR, bucket=args.bucket, weekly_only=args.weekly_only)


if __name__ == "__main__":
    main()
