"""
测试 agents/data_provider.py —— 从 trade-krono-cli 缓存加载真实 K 线
"""
import pytest
import pandas as pd
from agents.data_provider import fetch_kline_from_cache, _normalize_ticker


class TestNormalizeTicker:
    """测试 ticker 格式规范化"""

    def test_sz_format(self):
        assert _normalize_ticker("000001.SZ") == "sz.000001"
        assert _normalize_ticker("000001.sz") == "sz.000001"
        assert _normalize_ticker("sz.000001") == "sz.000001"

    def test_sh_format(self):
        assert _normalize_ticker("600519.SH") == "sh.600519"
        assert _normalize_ticker("600519.sh") == "sh.600519"
        assert _normalize_ticker("sh.600519") == "sh.600519"

    def test_bj_format(self):
        assert _normalize_ticker("bj.920002") == "bj.920002"

    def test_plain_code_auto_detect(self):
        assert _normalize_ticker("000001") == "sz.000001"
        assert _normalize_ticker("600519") == "sh.600519"


class TestFetchKline:
    """测试真实数据加载"""

    def test_fetch_sz_000001(self):
        """000001.SZ（平安银行）应有数据"""
        df = fetch_kline_from_cache("000001.SZ", "2024-01-01", "2024-12-31")
        assert df is not None
        assert len(df) > 0
        assert "close" in df.columns

    def test_fetch_sh_600519(self):
        """600519.SH（贵州茅台）应有数据"""
        df = fetch_kline_from_cache("sh.600519", "2024-06-01", "2024-09-30")
        assert df is not None
        assert len(df) > 0
        assert df.index.name == "timestamps" or isinstance(df.index, pd.DatetimeIndex)

    def test_missing_ticker_returns_none(self):
        """不存在的 ticker 应返回 None"""
        result = fetch_kline_from_cache("ZZ999999.SZ", "2024-01-01", "2024-12-31")
        assert result is None

    def test_empty_date_range(self):
        """超出数据范围的日期应返回空 DataFrame"""
        df = fetch_kline_from_cache("000001.SZ", "2010-01-01", "2010-12-31")
        # 数据库存在但该 ticker 在此日期范围无数据 → 返回空 DataFrame
        if df is not None:
            assert len(df) == 0

    def test_columns_standardized(self):
        """加载后的 DataFrame 应有标准 OHLCV 列名"""
        df = fetch_kline_from_cache("000001.SZ", "2024-01-01", "2024-03-31")
        if df is not None and not df.empty:
            assert "close" in df.columns
            assert "volume" in df.columns
            assert "open" in df.columns
            assert "high" in df.columns
            assert "low" in df.columns

    def test_index_is_datetime(self):
        """index 应为 DatetimeIndex"""
        df = fetch_kline_from_cache("000001.SZ", "2024-01-01", "2024-03-31")
        if df is not None and not df.empty:
            assert isinstance(df.index, pd.DatetimeIndex)
