import json

from ingest import ingest, load_master, load_staging_articles


def test_new_article_is_appended(sample_article):
    master = {"version": 1, "updated_at": "", "articles": []}
    updated, count = ingest(master, [sample_article])
    assert count == 1
    assert len(updated["articles"]) == 1
    assert updated["articles"][0]["id"] == sample_article["id"]


def test_duplicate_article_is_skipped(sample_article):
    master = {"version": 1, "updated_at": "", "articles": [sample_article]}
    updated, count = ingest(master, [sample_article])
    assert count == 0
    assert len(updated["articles"]) == 1


def test_updated_at_is_set(sample_article):
    master = {"version": 1, "updated_at": "", "articles": []}
    updated, _ = ingest(master, [sample_article])
    assert updated["updated_at"] != ""


def test_load_master_returns_empty_when_missing(tmp_path):
    missing = tmp_path / "articles.json"
    master = load_master(missing)
    assert master["articles"] == []
    assert master["version"] == 1


def test_load_staging_articles(tmp_path, sample_article):
    staging_file = tmp_path / "2026-05-20.json"
    staging_file.write_text(json.dumps([sample_article]))
    articles = load_staging_articles(tmp_path)
    assert len(articles) == 1
    assert articles[0]["id"] == sample_article["id"]


def test_load_staging_articles_empty_dir(tmp_path):
    articles = load_staging_articles(tmp_path)
    assert articles == []


def test_multiple_staging_files_merged(tmp_path, sample_article):
    a2 = sample_article.copy()
    a2["id"] = "bbbbbbbbbbbbbbbb"
    (tmp_path / "2026-05-19.json").write_text(json.dumps([sample_article]))
    (tmp_path / "2026-05-20.json").write_text(json.dumps([a2]))
    articles = load_staging_articles(tmp_path)
    assert len(articles) == 2
