from datetime import date
from unittest.mock import MagicMock, patch

from history import build_history, group_by_month, list_s3_dates


def test_group_by_month_newest_month_first():
    dates = [date(2026, 4, 22), date(2026, 5, 1), date(2026, 5, 20)]
    groups = group_by_month(dates)
    assert groups[0]["month_label"] == "May 2026"
    assert groups[1]["month_label"] == "April 2026"


def test_group_by_month_dates_newest_first_within_month():
    dates = [date(2026, 5, 1), date(2026, 5, 20), date(2026, 5, 15)]
    groups = group_by_month(dates)
    may = groups[0]
    assert may["dates"][0] == date(2026, 5, 20)
    assert may["dates"][1] == date(2026, 5, 15)
    assert may["dates"][2] == date(2026, 5, 1)


def test_group_by_month_single_month():
    dates = [date(2026, 5, 1), date(2026, 5, 2)]
    groups = group_by_month(dates)
    assert len(groups) == 1
    assert groups[0]["month_label"] == "May 2026"


def test_list_s3_dates_parses_yyyy_mm_dd_keys():
    mock_s3 = MagicMock()
    mock_s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [
            {"Key": "2026-05-20.html"},
            {"Key": "2026-04-22.html"},
            {"Key": "index.html"},
            {"Key": "history.html"},
            {"Key": "static/style.css"},
        ]}
    ]
    with patch("history.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        dates = list_s3_dates("test-bucket")

    assert date(2026, 5, 20) in dates
    assert date(2026, 4, 22) in dates
    assert len(dates) == 2


def test_build_history_includes_today(tmp_path):
    today = date(2026, 5, 21)
    mock_s3 = MagicMock()
    mock_s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": "2026-05-20.html"}]}
    ]
    with patch("history.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        build_history(today=today, bucket="test-bucket", output_dir=tmp_path)

    html = (tmp_path / "history.html").read_text()
    assert "2026-05-21" in html
    assert "2026-05-20" in html


def test_build_history_deduplicates_today_if_already_in_s3(tmp_path):
    today = date(2026, 5, 20)
    mock_s3 = MagicMock()
    mock_s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": "2026-05-20.html"}]}
    ]
    with patch("history.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        build_history(today=today, bucket="test-bucket", output_dir=tmp_path)

    html = (tmp_path / "history.html").read_text()
    assert html.count('href="/2026-05-20.html"') == 1
    assert html.count('<span class="iso">2026-05-20</span>') == 1
