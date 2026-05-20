#!/usr/bin/env python3
"""Renders data/articles.json → build/ HTML using Jinja2 templates.

Outputs:
  build/index.html        — homepage (today's articles + weekly sidebar)
  build/YYYY-MM-DD.html   — permanent daily archive for the build date
  build/static/           — copy of static/ assets
"""
import argparse
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import constants

REPO_ROOT = Path(__file__).parent.parent
ARTICLES_PATH = REPO_ROOT / "data" / "articles.json"
TEMPLATES_DIR = REPO_ROOT / "templates"
STATIC_DIR = REPO_ROOT / "static"
DEFAULT_BUILD_DIR = REPO_ROOT / "build"


def load_articles(path: Path) -> list:
    data = json.loads(path.read_text())
    articles = data["articles"]
    for a in articles:
        a["css_key"] = constants.VENDOR_CSS_KEY.get(a["vendor"], "industry")
    return articles


def datefmt(value: str) -> str:
    d = date.fromisoformat(value)
    return d.strftime("%b %-d")


def filter_today_articles(articles: list, today: date) -> list:
    yesterday = today - timedelta(days=1)
    window = {today.isoformat(), yesterday.isoformat()}
    filtered = [a for a in articles if a["scraped_at"] in window]
    return sorted(filtered, key=lambda a: (-a["score"], a["id"]))


def filter_archive_articles(articles: list, today: date) -> list:
    today_str = today.isoformat()
    filtered = [a for a in articles if a["scraped_at"] == today_str]
    return sorted(filtered, key=lambda a: (-a["score"], a["id"]))


def filter_week_articles(articles: list, today: date) -> list:
    cutoff = (today - timedelta(days=7)).isoformat()
    filtered = [
        a for a in articles
        if a["scraped_at"] >= cutoff and a["score"] >= 7
    ]
    return sorted(filtered, key=lambda a: (-a["score"], a["id"]))[:10]


def group_by_vendor(articles: list) -> list:
    groups: dict = {}
    for a in articles:
        groups.setdefault(a["vendor"], []).append(a)
    return sorted(
        [{"vendor": v, "articles": arts} for v, arts in groups.items()],
        key=lambda g: -max(a["score"] for a in g["articles"]),
    )


def build_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["datefmt"] = datefmt
    return env


def render_index(env: Environment, today: date, articles: list, output_dir: Path) -> None:
    today_articles = filter_today_articles(articles, today)
    week_articles = filter_week_articles(articles, today)
    today_groups = group_by_vendor(today_articles)

    html = env.get_template("index.html").render(
        nav_active="home",
        today_formatted=today.strftime("%A, %B %-d, %Y"),
        today_iso=today.isoformat(),
        today_groups=today_groups,
        week_articles=week_articles,
    )
    (output_dir / "index.html").write_text(html)


def render_daily(env: Environment, today: date, articles: list, output_dir: Path) -> None:
    archive_articles = filter_archive_articles(articles, today)
    article_groups = group_by_vendor(archive_articles)

    html = env.get_template("daily.html").render(
        nav_active="archive",
        date_formatted=today.strftime("%A, %B %-d, %Y"),
        date_iso=today.isoformat(),
        article_groups=article_groups,
    )
    (output_dir / f"{today.isoformat()}.html").write_text(html)


def copy_static(output_dir: Path) -> None:
    dest = output_dir / "static"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(str(STATIC_DIR), str(dest))


def render(today: date = None, output_dir: Path = DEFAULT_BUILD_DIR) -> None:
    if today is None:
        today = date.today()
    output_dir.mkdir(parents=True, exist_ok=True)
    articles = load_articles(ARTICLES_PATH)
    env = build_jinja_env()
    render_index(env, today, articles, output_dir)
    render_daily(env, today, articles, output_dir)
    copy_static(output_dir)
    print(f"✓ Rendered to {output_dir}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render articles.json → HTML")
    parser.add_argument("--date", help="Build date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", default=str(DEFAULT_BUILD_DIR))
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    render(today=today, output_dir=Path(args.output_dir))


if __name__ == "__main__":
    main()
