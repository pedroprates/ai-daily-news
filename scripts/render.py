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

import markdown as md_lib
import constants

REPO_ROOT = Path(__file__).parent.parent
ARTICLES_PATH = REPO_ROOT / "data" / "articles.json"
TEMPLATES_DIR = REPO_ROOT / "templates"
STATIC_DIR = REPO_ROOT / "static"
IMGS_DIR = REPO_ROOT / "imgs"
DEFAULT_BUILD_DIR = REPO_ROOT / "build"
SUMMARIES_DIR = REPO_ROOT / "data" / "summaries"


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


def weeks_from_articles(articles: list) -> list[str]:
    weeks: set[str] = set()
    for a in articles:
        cal = date.fromisoformat(a["date"]).isocalendar()
        weeks.add(f"{cal.year}-W{cal.week:02d}")
    return sorted(weeks)


def group_by_day(articles: list) -> list:
    days: dict = {}
    for a in articles:
        days.setdefault(a["date"], []).append(a)
    return sorted(
        [
            {
                "date_iso": d,
                "date_formatted": date.fromisoformat(d).strftime("%A, %B %-d, %Y"),
                "articles": sorted(arts, key=lambda a: -a["score"]),
            }
            for d, arts in days.items()
        ],
        key=lambda g: g["date_iso"],
        reverse=True,
    )


def _week_dates(week_iso: str) -> tuple:
    year, week = int(week_iso[:4]), int(week_iso[6:])
    return date.fromisocalendar(year, week, 1), date.fromisocalendar(year, week, 5)


def _period_str(monday: date, friday: date, include_year: bool = False) -> str:
    if monday.month == friday.month:
        base = f"{monday.strftime('%b %-d')} – {friday.strftime('%-d')}"
    else:
        base = f"{monday.strftime('%b %-d')} – {friday.strftime('%b %-d')}"
    return f"{base}, {monday.year}" if include_year else base


def render_weekly_week(
    env: Environment,
    week_iso: str,
    articles: list,
    output_dir: Path,
    summaries_dir: Path | None = None,
) -> None:
    if summaries_dir is None:
        summaries_dir = SUMMARIES_DIR

    year, week_num = int(week_iso[:4]), int(week_iso[6:])
    week_articles = []
    for a in articles:
        cal = date.fromisoformat(a["date"]).isocalendar()
        if cal.year == year and cal.week == week_num:
            week_articles.append(a)

    monday, friday = _week_dates(week_iso)
    summary_path = summaries_dir / f"{week_iso}.md"
    summary_html = None
    if summary_path.exists():
        summary_html = md_lib.markdown(summary_path.read_text())

    html = env.get_template("weekly.html").render(
        nav_active="weekly",
        week_label=f"Week {week_num} · {year}",
        period_str=_period_str(monday, friday, include_year=True),
        week_iso=week_iso,
        summary_html=summary_html,
        day_groups=group_by_day(week_articles),
    )
    out = output_dir / "weekly" / week_iso
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html)


def render_weekly_index(
    env: Environment,
    articles: list,
    output_dir: Path,
    today: date,
) -> None:
    today_cal = today.isocalendar()
    today_week_iso = f"{today_cal.year}-W{today_cal.week:02d}"

    week_rows = []
    for week_iso in reversed(weeks_from_articles(articles)):
        year, week_num = int(week_iso[:4]), int(week_iso[6:])
        monday, friday = _week_dates(week_iso)

        week_articles = []
        for a in articles:
            cal = date.fromisoformat(a["date"]).isocalendar()
            if cal.year == year and cal.week == week_num:
                week_articles.append(a)

        week_rows.append({
            "week_iso": week_iso,
            "week_label": f"Week {week_num} · {year}",
            "period_str": _period_str(monday, friday),
            "article_count": len(week_articles),
            "is_current": week_iso == today_week_iso,
        })

    html = env.get_template("weekly_index.html").render(
        nav_active="weekly",
        week_rows=week_rows,
    )
    out = output_dir / "weekly"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html)


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
    imgs_dest = output_dir / "imgs"
    if imgs_dest.exists():
        shutil.rmtree(imgs_dest)
    shutil.copytree(str(IMGS_DIR), str(imgs_dest))


def render(
    today: date | None = None,
    output_dir: Path = DEFAULT_BUILD_DIR,
    weekly_only: bool = False,
    articles_path: Path | None = None,
) -> None:
    if today is None:
        today = date.today()
    if articles_path is None:
        articles_path = ARTICLES_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    articles = load_articles(articles_path)
    env = build_jinja_env()
    if not weekly_only:
        render_index(env, today, articles, output_dir)
        render_daily(env, today, articles, output_dir)
    render_weekly_index(env, articles, output_dir, today)
    for week_iso in weeks_from_articles(articles):
        render_weekly_week(env, week_iso, articles, output_dir)
    copy_static(output_dir)
    print(f"✓ Rendered to {output_dir}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render articles.json → HTML")
    parser.add_argument("--date", help="Build date YYYY-MM-DD (default: today)")
    parser.add_argument("--output-dir", default=str(DEFAULT_BUILD_DIR))
    parser.add_argument("--weekly-only", action="store_true", help="Skip homepage and daily archive; render weekly pages only")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    render(today=today, output_dir=Path(args.output_dir), weekly_only=args.weekly_only)


if __name__ == "__main__":
    main()
