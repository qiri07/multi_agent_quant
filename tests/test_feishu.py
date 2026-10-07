"""
测试 utils/feishu.py —— 飞书 Webhook 通知
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.feishu import _send_feishu_webhook, send_report_notification


class TestSendFeishuWebhook:
    """测试飞书消息发送（网络层 mock）"""

    def test_skips_when_webhook_empty(self):
        """未配置 Webhook 时应静默跳过"""
        with patch("utils.feishu.FEISHU_WEBHOOK_URL", ""):
            result = _send_feishu_webhook("test message")
            assert result is False

    def test_skips_when_webhook_none(self):
        """Webhook 为 None 时应静默跳过"""
        with patch("utils.feishu.FEISHU_WEBHOOK_URL", None):
            result = _send_feishu_webhook("test message")
            assert result is False

    @patch("utils.feishu.requests.post")
    def test_success_response(self, mock_post):
        """飞书返回成功时应返回 True"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "data": {}}
        mock_post.return_value = mock_resp

        result = _send_feishu_webhook("Hello", "Title")
        assert result is True
        mock_post.assert_called_once()

    @patch("utils.feishu.requests.post")
    def test_failure_response(self, mock_post):
        """飞书返回错误码时应返回 False"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 1, "msg": "invalid"}
        mock_post.return_value = mock_resp

        result = _send_feishu_webhook("test")
        assert result is False

    @patch("utils.feishu.requests.post")
    def test_network_error_handled(self, mock_post):
        """网络异常时应捕获并返回 False"""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("connection refused")

        result = _send_feishu_webhook("test")
        assert result is False


class TestSendReportNotification:
    """测试回测摘要构建与发送"""

    @patch("utils.feishu._send_feishu_webhook")
    def test_sends_summary(self, mock_send):
        metrics = {
            "total_return": 0.15,
            "annual_return": 0.08,
            "sharpe_ratio": 0.9,
            "max_drawdown": -0.12,
            "max_drawdown_duration": 10,
            "win_rate": 0.6,
        }
        send_report_notification("000001.SZ", metrics, "中", ["建议1", "建议2"])
        mock_send.assert_called_once()
        # 验证消息中包含关键指标
        call_text = mock_send.call_args[0][0]
        assert "000001.SZ" in call_text
        assert "15.00%" in call_text
        assert "中" in call_text
        assert "建议1" in call_text

    @patch("utils.feishu._send_feishu_webhook")
    def test_empty_suggestions(self, mock_send):
        send_report_notification("600519.SH", {}, "低", [])
        mock_send.assert_called_once()
        call_text = mock_send.call_args[0][0]
        assert "600519.SH" in call_text
