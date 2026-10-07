"""
测试 agents/backtest_agent.py —— 回测引擎与绩效指标
"""
import pandas as pd
import numpy as np
import pytest
from agents.backtest_agent import BacktestAgent


class TestBacktestAgent:
    """测试回测引擎、绩效指标计算及 execute 流程"""

    @pytest.fixture
    def agent(self):
        return BacktestAgent()

    # ---- run_backtest ----

    def _make_signal_df(self, n=50, signals=None):
        """构造带 signal 列的测试 DataFrame"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=n, freq="B")
        close = 100 + np.cumsum(np.random.normal(0, 0.5, n))
        df = pd.DataFrame({"close": close}, index=dates)
        if signals is None:
            signals = [0] * n
        df["signal"] = signals
        return df

    def test_no_trades_when_no_signal(self, agent):
        df = self._make_signal_df(30, signals=[0] * 30)
        result = agent.run_backtest(df, {"initial_capital": 100_000})
        assert result["trades"] == []
        assert result["final_position"] == 0
        assert result["final_cash"] == 100_000

    def test_buy_then_sell(self, agent):
        """第1天买入信号，第2天卖出信号，验证完整交易"""
        signals = [1, -1] + [0] * 48
        df = self._make_signal_df(50, signals)
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
        })
        assert len(result["trades"]) == 2
        assert result["trades"][0]["type"] == "buy"
        assert result["trades"][1]["type"] == "sell"
        assert result["final_position"] == 0

    def test_slippage_increases_buy_price(self, agent):
        df = self._make_signal_df(5, signals=[1, 0, 0, 0, 0])
        config = {"initial_capital": 100_000, "slippage": 0.001}
        result = agent.run_backtest(df, config)
        buy_trade = result["trades"][0]
        # 买入价 = close * (1 + slippage)
        expected_price = df.iloc[0]["close"] * (1 + 0.001)
        assert abs(buy_trade["price"] - expected_price) < 0.01

    def test_commission_deducted_on_buy(self, agent):
        df = self._make_signal_df(5, signals=[1, 0, 0, 0, 0])
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "commission_rate": 0.001,
        })
        trade = result["trades"][0]
        # cost = price * volume * (1 + commission)
        assert trade["cost"] > trade["price"] * trade["volume"]

    def test_position_is_multiple_of_100(self, agent):
        df = self._make_signal_df(10, signals=[1] + [0] * 9)
        result = agent.run_backtest(df, {"initial_capital": 500_000})
        if result["trades"]:
            assert result["trades"][0]["volume"] % 100 == 0

    def test_net_value_curve_length(self, agent):
        df = self._make_signal_df(30)
        result = agent.run_backtest(df, {})
        assert len(result["net_value_curve"]) == 30

    def test_final_asset_formula(self, agent):
        df = self._make_signal_df(10, signals=[1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        result = agent.run_backtest(df, {"initial_capital": 100_000})
        final_price = df.iloc[-1]["close"]
        final_asset = result["final_cash"] + result["final_position"] * final_price
        assert abs(result["final_asset"] - final_asset) < 0.01

    # ---- calc_performance_metrics ----

    def _make_backtest_result(self, agent):
        df = self._make_signal_df(50, signals=[1, -1] + [0] * 48)
        result = agent.run_backtest(df, {"initial_capital": 100_000})
        return result, df

    def test_metrics_has_all_keys(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        expected_keys = {
            "total_return", "annual_return", "annual_volatility",
            "sharpe_ratio", "max_drawdown", "max_drawdown_duration",
            "calmar_ratio", "total_trades", "round_trips",
            "win_rate", "profit_loss_ratio", "avg_win_profit",
            "avg_loss", "benchmark_return", "benchmark_annual_return",
            "excess_return", "daily_returns",
        }
        assert expected_keys.issubset(metrics.keys())

    def test_total_return_matches_bt(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        assert abs(metrics["total_return"] - bt["total_return"]) < 1e-10

    def test_sharpe_is_numeric(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        assert isinstance(metrics["sharpe_ratio"], float)

    def test_max_drawdown_is_negative(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        assert metrics["max_drawdown"] <= 0

    def test_max_drawdown_duration_is_non_negative(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        assert metrics["max_drawdown_duration"] >= 0

    def test_daily_returns_length(self, agent):
        bt, df = self._make_backtest_result(agent)
        metrics = agent.calc_performance_metrics(bt, df)
        assert len(metrics["daily_returns"]) == len(bt["net_value_curve"]) - 1

    # ---- _calc_max_drawdown_duration ----

    def test_static_method_single_peak(self):
        nv = pd.Series([100, 110, 105, 100, 95, 90],
                       index=pd.date_range("2023-01-01", periods=6, freq="B"))
        cummax = nv.cummax()
        dd = (nv - cummax) / cummax
        dur = BacktestAgent._calc_max_drawdown_duration(cummax, dd)
        assert isinstance(dur, int)
        assert dur >= 0

    def test_static_method_no_drawdown(self):
        nv = pd.Series([100, 101, 102, 103],
                       index=pd.date_range("2023-01-01", periods=4, freq="B"))
        cummax = nv.cummax()
        dd = (nv - cummax) / cummax
        dur = BacktestAgent._calc_max_drawdown_duration(cummax, dd)
        assert dur == 0  # 从未出现负回撤

    # ---- execute ----

    def test_execute_updates_state(self, agent, mock_state, sample_with_factors):
        mock_state["data"] = sample_with_factors.copy()
        mock_state["data"]["signal"] = 0
        result = agent.execute(mock_state)
        assert result["backtest_result"] is not None
        assert "metrics" in result["backtest_result"]

    # ---- 止损/止盈/移动止损 ----

    def test_stop_loss_triggered(self, agent):
        """买入后价格跌超8%触发固定止损"""
        df = self._make_signal_df(5, signals=[1, 0, 0, 0, 0])
        # 手动构造：day0=100买入, day1=95, day2=90（跌10%触发8%止损）
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[1], "close"] = 95.0
        df.loc[df.index[2], "close"] = 90.0
        df.loc[df.index[3], "close"] = 92.0
        df.loc[df.index[4], "close"] = 95.0
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "stop_loss_pct": 0.08,
        })
        # 应触发止损卖出
        sell_trades = [t for t in result["trades"] if t["type"] == "sell"]
        assert len(sell_trades) >= 1
        assert any(t.get("reason") == "固定止损" for t in sell_trades)

    def test_take_profit_triggered(self, agent):
        """买入后价格涨超15%触发固定止盈"""
        df = self._make_signal_df(5, signals=[1, 0, 0, 0, 0])
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[1], "close"] = 105.0
        df.loc[df.index[2], "close"] = 118.0  # 涨18%触发15%止盈
        df.loc[df.index[3], "close"] = 120.0
        df.loc[df.index[4], "close"] = 122.0
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "take_profit_pct": 0.15,
        })
        sell_trades = [t for t in result["trades"] if t["type"] == "sell"]
        assert any(t.get("reason") == "固定止盈" for t in sell_trades)

    def test_trailing_stop_triggered(self, agent):
        """价格上涨后回落超5%触发移动止损"""
        df = self._make_signal_df(6, signals=[1, 0, 0, 0, 0, 0])
        df.loc[df.index[0], "close"] = 100.0   # 买入价约100
        df.loc[df.index[1], "close"] = 110.0   # 涨到110
        df.loc[df.index[2], "close"] = 115.0   # 新高115
        df.loc[df.index[3], "close"] = 112.0   # 回调
        df.loc[df.index[4], "close"] = 108.0   # 从115回撤3.5%
        df.loc[df.index[5], "close"] = 105.0   # 从115回撤8.7%触发5%移动止损
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "trailing_stop_pct": 0.05,
        })
        sell_trades = [t for t in result["trades"] if t["type"] == "sell"]
        assert any(t.get("reason") == "移动止损" for t in sell_trades)

    def test_no_stop_loss_below_threshold(self, agent):
        """跌幅未达8%不应触发止损"""
        df = self._make_signal_df(5, signals=[1, 0, 0, 0, 0])
        df.loc[df.index[0], "close"] = 100.0
        df.loc[df.index[1], "close"] = 96.0   # 跌4%，不足8%
        df.loc[df.index[2], "close"] = 98.0
        df.loc[df.index[3], "close"] = 102.0
        df.loc[df.index[4], "close"] = 105.0
        result = agent.run_backtest(df, {
            "initial_capital": 100_000,
            "stop_loss_pct": 0.08,
        })
        sell_trades = [t for t in result["trades"] if t["type"] == "sell"]
        assert not any(t.get("reason") == "固定止损" for t in sell_trades)
