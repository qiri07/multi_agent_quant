"""
测试 utils/config.py —— 配置常量模块
"""
from utils.config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE,
    DEFAULT_POSITION_RATIO,
    DEFAULT_VOTE_THRESHOLD,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_SYMBOL,
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
    MAX_RETRIES,
    FACTORIZER_MAX_WORKERS,
    REPORT_FILENAME,
)


class TestConfig:
    """验证所有配置常量值正确"""

    def test_capital_defaults(self):
        assert DEFAULT_INITIAL_CAPITAL == 100_000
        assert DEFAULT_RISK_FREE_RATE == 0.02

    def test_trade_defaults(self):
        assert DEFAULT_COMMISSION_RATE == 0.0003
        assert DEFAULT_SLIPPAGE == 0.0001
        assert DEFAULT_POSITION_RATIO == 1.0
        assert DEFAULT_VOTE_THRESHOLD == 2

    def test_data_defaults(self):
        assert DEFAULT_SYMBOL == "000001.SZ"
        assert DEFAULT_START_DATE == "2023-01-01"
        assert DEFAULT_END_DATE == "2026-09-30"

    def test_orchestrator_defaults(self):
        assert MAX_RETRIES == 1
        assert FACTORIZER_MAX_WORKERS == 4

    def test_report_filename(self):
        assert REPORT_FILENAME == "回测报告.md"
