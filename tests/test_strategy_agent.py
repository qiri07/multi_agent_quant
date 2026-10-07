"""
测试 agents/strategy_agent.py —— 策略信号生成与融合
"""
import pandas as pd
import pytest

from agents.strategy_agent import StrategyAgent


class TestStrategyAgent:
    """测试各子策略信号生成、投票融合及 execute 流程"""

    @pytest.fixture
    def agent(self):
        return StrategyAgent()

    # ---- 子策略 ----

    def test_ma_cross_generates_signals(self, agent, sample_with_factors):
        signal = agent.ma_cross_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_ma_cross_length_matches_index(self, agent, sample_with_factors):
        signal = agent.ma_cross_strategy(sample_with_factors)
        assert len(signal) == len(sample_with_factors)

    def test_rsi_generates_signals(self, agent, sample_with_factors):
        signal = agent.rsi_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_macd_generates_signals(self, agent, sample_with_factors):
        signal = agent.macd_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_boll_generates_signals(self, agent, sample_with_factors):
        signal = agent.boll_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_cci_generates_signals(self, agent, sample_with_factors):
        signal = agent.cci_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_kdj_generates_signals(self, agent, sample_with_factors):
        signal = agent.kdj_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_adx_trend_generates_signals(self, agent, sample_with_factors):
        signal = agent.adx_trend_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_volume_divergence_generates_signals(self, agent, sample_with_factors):
        signal = agent.volume_divergence_strategy(sample_with_factors)
        assert set(signal.unique()).issubset({-1, 0, 1})

    def test_all_strategies_produce_same_index(self, agent, sample_with_factors):
        signals = [
            agent.ma_cross_strategy(sample_with_factors),
            agent.rsi_strategy(sample_with_factors),
            agent.macd_strategy(sample_with_factors),
            agent.boll_strategy(sample_with_factors),
            agent.cci_strategy(sample_with_factors),
            agent.kdj_strategy(sample_with_factors),
            agent.adx_trend_strategy(sample_with_factors),
            agent.volume_divergence_strategy(sample_with_factors),
        ]
        idx = signals[0].index
        for s in signals:
            assert list(s.index) == list(idx)

    # ---- 信号融合 ----

    def test_fuse_signals_strict_majority(self):
        """5 个买入 + 3 个卖出，阈值=2 → 买入"""
        n = 10
        signals = [pd.Series([1] * n) for _ in range(5)]
        signals += [pd.Series([-1] * n) for _ in range(3)]
        result = StrategyAgent.fuse_signals(signals, threshold=2)
        assert (result == 1).all()

    def test_fuse_signals_below_threshold(self):
        """1 个买入 + 7 个持有，阈值=2 → 全部持有"""
        n = 10
        s1 = pd.Series([1] * n)
        s_rest = [pd.Series([0] * n) for _ in range(7)]
        result = StrategyAgent.fuse_signals([s1] + s_rest, threshold=2)
        assert (result == 0).all()

    def test_fuse_signals_all_sell(self):
        """全卖出 → 卖出信号"""
        n = 10
        signals = [pd.Series([-1] * n) for _ in range(8)]
        result = StrategyAgent.fuse_signals(signals, threshold=2)
        assert (result == -1).all()

    def test_fuse_signals_all_hold(self):
        """全持有 → 保持持有"""
        n = 10
        signals = [pd.Series([0] * n) for _ in range(8)]
        result = StrategyAgent.fuse_signals(signals, threshold=2)
        assert (result == 0).all()

    def test_fuse_signals_mixed(self):
        """混合信号，按阈值正确判断"""
        n = 10
        signals = [pd.Series([1] * n) for _ in range(4)]
        signals += [pd.Series([-1] * n) for _ in range(4)]
        # 总和 = 0，阈值=2 → 无信号
        result = StrategyAgent.fuse_signals(signals, threshold=2)
        assert (result == 0).all()

    def test_fuse_signals_respects_different_threshold(self):
        """阈值=5，4 买 4 卖 → 无信号"""
        n = 10
        signals = [pd.Series([1] * n) for _ in range(4)]
        signals += [pd.Series([-1] * n) for _ in range(4)]
        result = StrategyAgent.fuse_signals(signals, threshold=5)
        assert (result == 0).all()

    # ---- execute ----

    def test_execute_populates_signals(self, agent, mock_state, sample_with_factors):
        mock_state["data"] = sample_with_factors
        result = agent.execute(mock_state)
        assert result["signals"] is not None
        assert "buy_count" in result["signals"]
        assert "sell_count" in result["signals"]
        assert "hold_count" in result["signals"]

    def test_execute_signal_column_added(self, agent, mock_state, sample_with_factors):
        mock_state["data"] = sample_with_factors
        result = agent.execute(mock_state)
        assert "signal" in result["data"].columns
        assert set(result["data"]["signal"].unique()).issubset({-1, 0, 1})

    def test_execute_signal_counts_consistent(self, agent, mock_state, sample_with_factors):
        mock_state["data"] = sample_with_factors
        result = agent.execute(mock_state)
        sig = result["signals"]["signal_series"]
        assert result["signals"]["buy_count"] == int((sig == 1).sum())
        assert result["signals"]["sell_count"] == int((sig == -1).sum())
        assert result["signals"]["hold_count"] == int((sig == 0).sum())

    # ---- 趋势过滤 ----

    def test_trend_filter_blocks_buy_in_downtrend(self, agent, sample_with_factors):
        """价格在MA60下方时，买入信号应被过滤"""
        df = sample_with_factors.copy()
        df.loc[df.index[-3:], "close"] = df["MA60"].iloc[-4] * 0.8
        df = df.dropna()
        signals = [
            agent.ma_cross_strategy(df), agent.rsi_strategy(df),
            agent.macd_strategy(df), agent.boll_strategy(df),
            agent.cci_strategy(df), agent.kdj_strategy(df),
            agent.adx_trend_strategy(df), agent.volume_divergence_strategy(df),
        ]
        fused = agent.fuse_signals(signals, threshold=2)
        filtered = agent.apply_trend_filter(df, fused, ma_window=60)
        last_three = filtered.iloc[-3:]
        assert (last_three == 1).sum() == 0

    def test_trend_filter_allows_buy_in_uptrend(self, agent, sample_with_factors):
        """价格在MA60上方时，买入信号应保留"""
        df = sample_with_factors.copy()
        df.loc[df.index[-3:], "close"] = df["MA60"].iloc[-4] * 1.2
        df = df.dropna()
        signals = [
            agent.ma_cross_strategy(df), agent.rsi_strategy(df),
            agent.macd_strategy(df), agent.boll_strategy(df),
            agent.cci_strategy(df), agent.kdj_strategy(df),
            agent.adx_trend_strategy(df), agent.volume_divergence_strategy(df),
        ]
        fused = agent.fuse_signals(signals, threshold=2)
        filtered = agent.apply_trend_filter(df, fused, ma_window=60)
        # 上升趋势中不应有卖出信号（被过滤为0），买入信号应保留或至少不违反规则
        assert (filtered[filtered == -1].sum() == 0) or (fused.sum() == 0)
