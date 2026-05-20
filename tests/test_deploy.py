from pathlib import Path
from unittest.mock import MagicMock, patch

import deploy


def test_upload_dir_uploads_all_files(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "style.css").write_text("body {}")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        count = deploy.upload_dir(tmp_path, "test-bucket")

    assert count == 2
    assert mock_s3.put_object.call_count == 2


def test_upload_sets_html_content_type(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        deploy.upload_dir(tmp_path, "test-bucket")

    kwargs = mock_s3.put_object.call_args_list[0][1]
    assert "text/html" in kwargs["ContentType"]


def test_upload_sets_css_content_type(tmp_path):
    (tmp_path / "style.css").write_text("body {}")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        deploy.upload_dir(tmp_path, "test-bucket")

    kwargs = mock_s3.put_object.call_args_list[0][1]
    assert "text/css" in kwargs["ContentType"]


def test_upload_key_is_relative_path(tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "style.css").write_text("body {}")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        deploy.upload_dir(tmp_path, "test-bucket")

    kwargs = mock_s3.put_object.call_args_list[0][1]
    assert kwargs["Key"] == "static/style.css"


def test_invalidate_cloudfront_calls_create_invalidation():
    mock_cf = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_cf
        deploy.invalidate_cloudfront("EDFDVBD6EXAMPLE")

    mock_cf.create_invalidation.assert_called_once()
    call_kwargs = mock_cf.create_invalidation.call_args[1]
    assert call_kwargs["DistributionId"] == "EDFDVBD6EXAMPLE"
    assert "/*" in call_kwargs["InvalidationBatch"]["Paths"]["Items"]


def test_deploy_skips_cloudfront_when_env_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOUDFRONT_DISTRIBUTION_ID", raising=False)
    (tmp_path / "index.html").write_text("<html></html>")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        with patch("deploy.invalidate_cloudfront") as mock_cf:
            deploy.deploy(build_dir=tmp_path, bucket="test-bucket")

    mock_cf.assert_not_called()


def test_deploy_calls_cloudfront_when_env_set(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFRONT_DISTRIBUTION_ID", "EDFDVBD6EXAMPLE")
    (tmp_path / "index.html").write_text("<html></html>")

    mock_s3 = MagicMock()
    with patch("deploy.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_s3
        with patch("deploy.invalidate_cloudfront") as mock_cf:
            deploy.deploy(build_dir=tmp_path, bucket="test-bucket")

    mock_cf.assert_called_once_with("EDFDVBD6EXAMPLE")
