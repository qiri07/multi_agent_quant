"""
飞书机器人 Webhook 通知模块
通过 HTTP POST 发送富文本消息到飞书群机器人。
"""
from __future__ import annotations

import requests
from loguru import logger

from utils.config import FEISHU_WEBHOOK_URL


def _send_feishu_webhook(text: str, title: str = "📊 多Agent量化回测报告") -> bool:
    """
    向飞书机器人发送富文本卡片消息（无签名验证）。

    Args:
        text:   消息正文（支持 Markdown）
        title:  消息标题

    Returns:
        是否发送成功
    """
    if not FEISHU_WEBHOOK_URL or FEISHU_WEBHOOK_URL.strip() == "":
        logger.debug("飞书 Webhook 未配置，跳过推送")
        return False

    url = FEISHU_WEBHOOK_URL

    # 使用 interactive 卡片格式，支持更丰富的展示
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "green",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": text},
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "⚠️ 本报告由多Agent量化流水线自动生成，仅供参考，不构成投资建议"}
                    ],
                },
            ],
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        # 兼容新旧格式的 success 判断
        if result.get("code") == 0 or result.get("StatusCode") == 0 or result.get("success") is True:
            logger.info("✅ 飞书推送成功")
            return True
        else:
            logger.warning(f"⚠️ 飞书推送失败: {result}")
            return False
    except requests.exceptions.Timeout:
        logger.warning("⚠️ 飞书推送超时（10s）")
        return False
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ 飞书推送异常: {e}")
        return False
    except Exception as e:
        logger.warning(f"⚠️ 飞书推送异常: {e}")
        return False


def send_report_notification(
    symbol: str,
    metrics: dict,
    risk_level: str,
    suggestions: list[str],
) -> None:
    """
    将回测结果摘要发送至飞书。

    Args:
        symbol:     标的代码
        metrics:    BacktestAgent 输出的 metrics 字典
        risk_level: RiskAgent 评估的风险等级
        suggestions: 优化建议列表
    """
    lines = [
        f"**标的**: {symbol}",
        f"**总收益**: {metrics.get('total_return', 0):.2%}  "
        f"**年化**: {metrics.get('annual_return', 0):.2%}",
        f"**夏普比率**: {metrics.get('sharpe_ratio', 0):.2f}  "
        f"**最大回撤**: {metrics.get('max_drawdown', 0):.2%}",
        f"**回撤持续**: {metrics.get('max_drawdown_duration', 0)} 天  "
        f"**胜率**: {metrics.get('win_rate', 0):.0%}",
        f"**风险等级**: {risk_level}",
    ]
    if suggestions:
        lines.append("**优化建议**:")
        for s in suggestions[:3]:
            lines.append(f"• {s}")

    text = "\n".join(lines)
    _send_feishu_webhook(text, title=f"📈 量化回测完成 — {symbol}")
