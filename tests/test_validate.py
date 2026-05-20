import json
import pytest

from validate import detect_schema, validate_file


def test_detect_schema_articles(tmp_path):
    f = tmp_path / "articles.json"
    assert detect_schema(f) == "articles"


def test_detect_schema_staging(tmp_path):
    f = tmp_path / "staging" / "2026-05-20.json"
    assert detect_schema(f) == "staging"


def test_detect_schema_unknown(tmp_path):
    f = tmp_path / "other.json"
    assert detect_schema(f) is None


def test_valid_articles_file_passes(tmp_path, sample_article):
    articles = {
        "version": 1,
        "updated_at": "2026-05-20T06:00:00+00:00",
        "articles": [sample_article],
    }
    f = tmp_path / "articles.json"
    f.write_text(json.dumps(articles))
    validate_file(f)  # should not raise


def test_invalid_articles_file_raises(tmp_path):
    f = tmp_path / "articles.json"
    f.write_text(json.dumps({"version": 1}))  # missing required fields
    with pytest.raises(Exception):
        validate_file(f)


def test_valid_staging_file_passes(tmp_path, sample_article):
    f = tmp_path / "staging" / "2026-05-20.json"
    f.parent.mkdir()
    f.write_text(json.dumps([sample_article]))
    validate_file(f)  # should not raise


def test_invalid_staging_file_raises(tmp_path):
    f = tmp_path / "staging" / "2026-05-20.json"
    f.parent.mkdir()
    f.write_text(json.dumps([{"title": "missing fields"}]))
    with pytest.raises(Exception):
        validate_file(f)


def test_unknown_path_raises(tmp_path):
    f = tmp_path / "random.json"
    f.write_text("{}")
    with pytest.raises(ValueError, match="Unknown"):
        validate_file(f)
