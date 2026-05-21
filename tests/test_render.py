from datetime import date

import pytest

from render import (
    build_jinja_env,
    datefmt,
    filter_archive_articles,
    filter_today_articles,
    filter_week_articles,
    group_by_day,
    group_by_vendor,
    render_weekly_week,
    weeks_from_articles,
)


@pytest.fixture
def article_today(sample_article):
    a = sample_article.copy()
    a["scraped_at"] = "2026-05-20"
    a["css_key"] = "anthropic"
    return a


@pytest.fixture
def article_yesterday(sample_article):
    a = sample_article.copy()
    a["id"] = "bbbbbbbbbbbbbbbb"
    a["scraped_at"] = "2026-05-19"
    a["css_key"] = "anthropic"
    return a


@pytest.fixture
def article_old(sample_article):
    a = sample_article.copy()
    a["id"] = "cccccccccccccccc"
    a["scraped_at"] = "2026-05-10"
    a["css_key"] = "anthropic"
    return a


def test_filter_today_includes_today_and_yesterday(article_today, article_yesterday, article_old, today):
    result = filter_today_articles([article_today, article_yesterday, article_old], today)
    ids = [a["id"] for a in result]
    assert article_today["id"] in ids
    assert article_yesterday["id"] in ids
    assert article_old["id"] not in ids


def test_filter_today_sorted_by_score_then_id(today):
    a1 = {"id": "aaaaaaaaaaaaaaaa", "vendor": "Anthropic", "score": 7, "scraped_at": "2026-05-20", "css_key": "anthropic"}
    a2 = {"id": "bbbbbbbbbbbbbbbb", "vendor": "OpenAI",    "score": 9, "scraped_at": "2026-05-20", "css_key": "openai"}
    a3 = {"id": "cccccccccccccccc", "vendor": "Google",    "score": 9, "scraped_at": "2026-05-20", "css_key": "google"}
    result = filter_today_articles([a1, a2, a3], today)
    assert result[0]["score"] == 9
    assert result[1]["score"] == 9
    assert result[1]["id"] > result[0]["id"]


def test_filter_archive_only_today(article_today, article_yesterday, today):
    result = filter_archive_articles([article_today, article_yesterday], today)
    assert len(result) == 1
    assert result[0]["id"] == article_today["id"]


def test_filter_week_excludes_low_scores(article_today, today):
    low = article_today.copy()
    low["id"] = "dddddddddddddddd"
    low["score"] = 5
    result = filter_week_articles([article_today, low], today)
    ids = [a["id"] for a in result]
    assert article_today["id"] in ids
    assert low["id"] not in ids


def test_filter_week_caps_at_10(sample_article, today):
    articles = []
    for i in range(15):
        a = sample_article.copy()
        a["id"] = f"{i:016x}"
        a["score"] = 8
        a["css_key"] = "anthropic"
        articles.append(a)
    result = filter_week_articles(articles, today)
    assert len(result) == 10


def test_filter_week_excludes_older_than_7_days(sample_article, today):
    old = sample_article.copy()
    old["id"] = "eeeeeeeeeeeeeeee"
    old["scraped_at"] = "2026-05-12"  # 8 days before 2026-05-20
    old["css_key"] = "anthropic"
    result = filter_week_articles([old], today)
    assert result == []


def test_group_by_vendor_orders_groups_by_max_score(sample_article, today):
    a1 = sample_article.copy()
    a1["vendor"] = "OpenAI"
    a1["score"] = 5
    a1["css_key"] = "openai"
    a2 = sample_article.copy()
    a2["id"] = "bbbbbbbbbbbbbbbb"
    a2["vendor"] = "Anthropic"
    a2["score"] = 9
    a2["css_key"] = "anthropic"
    groups = group_by_vendor([a1, a2])
    assert groups[0]["vendor"] == "Anthropic"
    assert groups[1]["vendor"] == "OpenAI"


def test_group_by_vendor_structure(article_today):
    groups = group_by_vendor([article_today])
    assert len(groups) == 1
    assert groups[0]["vendor"] == "Anthropic"
    assert groups[0]["articles"][0]["id"] == article_today["id"]


def test_datefmt_strips_leading_zero():
    assert datefmt("2026-05-20") == "May 20"
    assert datefmt("2026-01-01") == "Jan 1"


# ── weeks_from_articles ───────────────────────────────────────────────────────

def test_weeks_from_articles_returns_sorted_iso_weeks():
    articles = [
        {"date": "2026-05-20"},  # W21
        {"date": "2026-05-18"},  # W21
        {"date": "2026-05-11"},  # W20
    ]
    assert weeks_from_articles(articles) == ["2026-W20", "2026-W21"]


def test_weeks_from_articles_deduplicates():
    articles = [{"date": "2026-05-20"}, {"date": "2026-05-21"}]
    assert weeks_from_articles(articles) == ["2026-W21"]


def test_weeks_from_articles_empty():
    assert weeks_from_articles([]) == []


# ── group_by_day ──────────────────────────────────────────────────────────────

def test_group_by_day_newest_first():
    articles = [
        {"date": "2026-05-20", "score": 8, "id": "a" * 16, "css_key": "anthropic"},
        {"date": "2026-05-19", "score": 9, "id": "b" * 16, "css_key": "openai"},
    ]
    groups = group_by_day(articles)
    assert groups[0]["date_iso"] == "2026-05-20"
    assert groups[1]["date_iso"] == "2026-05-19"


def test_group_by_day_articles_sorted_by_score_desc():
    articles = [
        {"date": "2026-05-20", "score": 5, "id": "a" * 16, "css_key": "anthropic"},
        {"date": "2026-05-20", "score": 9, "id": "b" * 16, "css_key": "openai"},
    ]
    groups = group_by_day(articles)
    assert groups[0]["articles"][0]["score"] == 9


def test_group_by_day_date_formatted():
    articles = [
        {"date": "2026-05-20", "score": 8, "id": "a" * 16, "css_key": "anthropic"},
    ]
    groups = group_by_day(articles)
    assert groups[0]["date_formatted"] == "Wednesday, May 20, 2026"


# ── render_weekly_week ────────────────────────────────────────────────────────

def test_render_weekly_week_creates_file(tmp_path, sample_article):
    article = {**sample_article, "date": "2026-05-20", "scraped_at": "2026-05-20", "css_key": "anthropic"}
    env = build_jinja_env()
    render_weekly_week(env, "2026-W21", [article], tmp_path, summaries_dir=tmp_path / "summaries")
    assert (tmp_path / "weekly" / "2026-W21" / "index.html").exists()


def test_render_weekly_week_contains_article_title(tmp_path, sample_article):
    article = {**sample_article, "date": "2026-05-20", "scraped_at": "2026-05-20",
               "css_key": "anthropic", "title": "Big AI News This Week"}
    env = build_jinja_env()
    render_weekly_week(env, "2026-W21", [article], tmp_path, summaries_dir=tmp_path / "summaries")
    html = (tmp_path / "weekly" / "2026-W21" / "index.html").read_text()
    assert "Big AI News This Week" in html


def test_render_weekly_week_no_summary_when_file_missing(tmp_path, sample_article):
    article = {**sample_article, "date": "2026-05-20", "scraped_at": "2026-05-20", "css_key": "anthropic"}
    env = build_jinja_env()
    render_weekly_week(env, "2026-W21", [article], tmp_path, summaries_dir=tmp_path / "summaries")
    html = (tmp_path / "weekly" / "2026-W21" / "index.html").read_text()
    assert "Editor's Summary" not in html


def test_render_weekly_week_shows_summary_when_file_exists(tmp_path, sample_article):
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    (summaries_dir / "2026-W21.md").write_text("This week was enormous.")
    article = {**sample_article, "date": "2026-05-20", "scraped_at": "2026-05-20", "css_key": "anthropic"}
    env = build_jinja_env()
    render_weekly_week(env, "2026-W21", [article], tmp_path, summaries_dir=summaries_dir)
    html = (tmp_path / "weekly" / "2026-W21" / "index.html").read_text()
    assert "This week was enormous" in html


def test_render_weekly_week_filters_to_correct_week(tmp_path, sample_article):
    in_week = {**sample_article, "date": "2026-05-20", "scraped_at": "2026-05-20",
               "css_key": "anthropic", "title": "In W21"}
    out_of_week = {**sample_article, "id": "b" * 16, "date": "2026-05-11", "scraped_at": "2026-05-11",
                   "css_key": "anthropic", "title": "In W20"}
    env = build_jinja_env()
    render_weekly_week(env, "2026-W21", [in_week, out_of_week], tmp_path, summaries_dir=tmp_path / "summaries")
    html = (tmp_path / "weekly" / "2026-W21" / "index.html").read_text()
    assert "In W21" in html
    assert "In W20" not in html
