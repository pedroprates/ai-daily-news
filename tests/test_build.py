from datetime import date
from unittest.mock import patch

import build


def test_build_calls_render_history_deploy(tmp_path):
    today = date(2026, 5, 20)
    with patch("build.render_module.render") as mock_render, \
         patch("build.history_module.build_history") as mock_history, \
         patch("build.deploy_module.deploy") as mock_deploy:
        build.run(today=today, build_dir=tmp_path, bucket="test-bucket")

    mock_render.assert_called_once_with(today=today, output_dir=tmp_path)
    mock_history.assert_called_once_with(today=today, bucket="test-bucket", output_dir=tmp_path)
    mock_deploy.assert_called_once_with(build_dir=tmp_path, bucket="test-bucket")


def test_build_order_is_render_history_deploy(tmp_path):
    call_order = []
    today = date(2026, 5, 20)

    with patch("build.render_module.render", side_effect=lambda **kw: call_order.append("render")), \
         patch("build.history_module.build_history", side_effect=lambda **kw: call_order.append("history")), \
         patch("build.deploy_module.deploy", side_effect=lambda **kw: call_order.append("deploy")):
        build.run(today=today, build_dir=tmp_path, bucket="test-bucket")

    assert call_order == ["render", "history", "deploy"]
