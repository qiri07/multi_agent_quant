"""
测试 agents/data_agent.py —— 数据获取与清洗
"""
import pandas as pd
import numpy as np
import pytest
from agents.data_agent import DataAgent


class TestDataAgent:
    """测试数据生成、清洗及 execute 全流程"""

    @pytest.fixture
    def agent(self):
        return DataAgent()

    # ---- generate_demo_data ----

    def test_generate_returns_ohlcv_df(self, agent):
        df = agent._generate_demo_data("2023-01-01", "2023-01-10")
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume", "symbol"]
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_generate_date_range(self, agent):
        df = agent._generate_demo_data("2023-06-01", "2023-06-10")
        dates = df.index
        assert dates[0] >= pd.Timestamp("2023-06-01")
        assert dates[-1] <= pd.Timestamp("2023-06-10")

    def test_generate_reproducible(self, agent):
        """固定随机种子，两次调用结果一致"""
        df1 = agent._generate_demo_data("2023-01-01", "2023-01-05")
        df2 = agent._generate_demo_data("2023-01-01", "2023-01-05")
        pd.testing.assert_frame_equal(df1, df2)

    def test_generate_symbol_default(self, agent):
        df = agent._generate_demo_data("2023-01-01", "2023-01-05")
        assert (df["symbol"] == "DEMO").all()

    def test_generate_symbol_custom(self, agent):
        df = agent._generate_demo_data("2023-01-01", "2023-01-05", symbol="600519.SH")
        assert (df["symbol"] == "600519.SH").all()

    # ---- clean_data ----

    def test_clean_adds_pct_chg(self, agent):
        df = agent._generate_demo_data("2023-01-01", "2023-01-10")
        cleaned = agent.clean_data(df)
        assert "pct_chg" in cleaned.columns

    def test_clean_no_nan_prices(self, agent):
        df = agent._generate_demo_data("2023-01-01", "2023-01-10")
        cleaned = agent.clean_data(df)
        for col in ["open", "high", "low", "close"]:
            assert cleaned[col].notna().all()

    def test_clean_handles_extreme_spike(self, agent):
        """插入一个 50% 的异常涨幅，验证清洗后会用前值填充"""
        df = agent._generate_demo_data("2023-01-01", "2023-01-10")
        df.loc[df.index[5], "close"] = df.loc[df.index[4], "close"] * 1.50
        cleaned = agent.clean_data(df)
        assert abs(cleaned["close"].pct_change().max()) <= 0.2 + 1e-6

    # ---- execute ----

    def test_execute_populates_state(self, agent, mock_state):
        mock_state["task_config"]["start_date"] = "2023-01-01"
        mock_state["task_config"]["end_date"] = "2023-01-10"
        result = agent.execute(mock_state)
        assert result["data"] is not None
        assert isinstance(result["data"], pd.DataFrame)
        assert len(result["data"]) > 0

    def test_execute_preserves_columns(self, agent, mock_state):
        mock_state["task_config"]["start_date"] = "2023-01-01"
        mock_state["task_config"]["end_date"] = "2023-01-10"
        result = agent.execute(mock_state)
        df = result["data"]
        for col in ["open", "high", "low", "close", "volume", "pct_chg"]:
            assert col in df.columns
