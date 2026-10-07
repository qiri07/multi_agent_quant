"""
测试 agents/risk_agent.py —— 风控评估与报告生成
"""
import pytest
import pandas as pd
from agents.risk_agent import RiskAgent


class TestRiskAgent:
    """测试风险评估、优化建议及报告生成"""

    @pytest.fixture
    def agent(self):
        return RiskAgent()

    # ---- risk_assessment ----

    def test_low_risk_when_all_good(self, agent):
        """drawdown=-0.05, sharpe=1.5, win_rate=0.7 → 低风险"""
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=1.5, max_drawdown=-0.05, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=20, round_trips=10,
            win_rate=0.7, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=0.025,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        assert result["risk_level"] == "低"
        assert result["pass_risk_check"] is True

    def test_high_risk_when_large_drawdown(self, agent):
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=1.5, max_drawdown=-0.25, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=20, round_trips=10,
            win_rate=0.7, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=0.025,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        assert result["risk_level"] == "高"
        assert result["pass_risk_check"] is False

    def test_medium_risk_when_sharpe_low(self, agent):
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=0.3, max_drawdown=-0.05, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=20, round_trips=10,
            win_rate=0.7, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=0.025,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        # sharpe<0.5 → 高风险（超过中风险）
        assert result["risk_level"] == "高"

    def test_warning_added_for_low_winrate(self, agent):
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=1.5, max_drawdown=-0.05, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=20, round_trips=10,
            win_rate=0.3, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=0.025,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        warnings = result["risk_warnings"]
        assert any("胜率" in w or "信号" in w for w in warnings)

    def test_warning_added_for_overtrading(self, agent):
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=1.5, max_drawdown=-0.05, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=50, round_trips=25,
            win_rate=0.7, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=0.025,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        assert any("频繁" in w or "手续费" in w for w in result["risk_warnings"])

    def test_warning_added_for_underperforming(self, agent):
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=1.5, max_drawdown=-0.05, max_drawdown_duration=3,
            calmar_ratio=0.8, total_trades=20, round_trips=10,
            win_rate=0.7, profit_loss_ratio=2.0,
            avg_win_profit=500.0, avg_loss=250.0,
            benchmark_return=0.03, benchmark_annual_return=0.025,
            excess_return=-0.02,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        assert any("跑赢" in w or "基准" in w for w in result["risk_warnings"])

    def test_default_warning_when_no_issues(self, agent):
        """所有指标健康时，应给出 ✅ 提示"""
        m = dict(
            total_return=0.10, annual_return=0.05, annual_volatility=0.12,
            sharpe_ratio=2.0, max_drawdown=-0.03, max_drawdown_duration=3,
            calmar_ratio=1.5, total_trades=0, round_trips=0,
            win_rate=1.0, profit_loss_ratio=99.0,
            avg_win_profit=600.0, avg_loss=240.0,
            benchmark_return=0.02, benchmark_annual_return=0.018,
            excess_return=0.03,
            daily_returns=pd.Series([0.001] * 10),
        )
        result = agent.risk_assessment(m)
        assert result["risk_level"] == "低"
        # 无任何触发条件时，只有一条默认 ✅ 提示
        assert result["risk_warnings"] == ["✅ 各项风险指标正常"]

    # ---- generate_optimization_suggestions ----

    def test_suggestion_for_large_drawdown(self):
        m = dict(win_rate=0.7, profit_loss_ratio=2.0, total_trades=10,
                 sharpe_ratio=1.5, max_drawdown=-0.20)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("止损" in s for s in suggestions)

    def test_suggestion_for_low_winrate(self):
        m = dict(win_rate=0.3, profit_loss_ratio=2.0, total_trades=10,
                 sharpe_ratio=1.5, max_drawdown=-0.05)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("过滤" in s or "假信号" in s for s in suggestions)

    def test_suggestion_for_low_profit_loss_ratio(self):
        m = dict(win_rate=0.7, profit_loss_ratio=0.8, total_trades=10,
                 sharpe_ratio=1.5, max_drawdown=-0.05)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("止盈" in s or "盈亏比" in s for s in suggestions)

    def test_suggestion_for_high_frequency(self):
        m = dict(win_rate=0.7, profit_loss_ratio=2.0, total_trades=150,
                 sharpe_ratio=1.5, max_drawdown=-0.05)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("阈值" in s or "无效交易" in s for s in suggestions)

    def test_suggestion_for_low_sharpe(self):
        m = dict(win_rate=0.7, profit_loss_ratio=2.0, total_trades=10,
                 sharpe_ratio=0.3, max_drawdown=-0.05)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("因子" in s or "融合" in s for s in suggestions)

    def test_default_suggestion_when_all_good(self):
        m = dict(win_rate=0.7, profit_loss_ratio=2.0, total_trades=10,
                 sharpe_ratio=1.5, max_drawdown=-0.05)
        suggestions = RiskAgent.generate_optimization_suggestions(m, {})
        assert any("样本外" in s or "敏感性" in s for s in suggestions)

    # ---- generate_report ----

    def test_report_contains_key_sections(self, agent, mock_state, sample_metrics):
        mock_state["task_config"] = {"symbol": "000001.SZ", "start_date": "2023-01-01",
                                      "end_date": "2023-06-30", "vote_threshold": 2}
        mock_state["backtest_result"] = {"metrics": sample_metrics,
                                          "initial_capital": 100_000, "final_asset": 115_000}
        mock_state["risk_report"] = {"risk_assessment": {"risk_level": "低",
                                                          "risk_warnings": ["✅ 正常"]},
                                      "suggestions": ["建议：保持现状"]}
        mock_state["factors"] = ["MA5", "RSI"]
        mock_state["signals"] = {"buy_count": 5, "sell_count": 3}
        mock_state["duration"] = 0.5

        report = agent.generate_report(mock_state)
        assert "# 📊" in report
        assert "标的代码" in report
        assert "总收益率" in report
        assert "风险等级" in report
        assert "优化建议" in report

    def test_report_contains_metrics_values(self, agent, mock_state, sample_metrics):
        mock_state["task_config"] = {"symbol": "600519.SH", "start_date": "2023-01-01",
                                      "end_date": "2023-06-30", "vote_threshold": 3}
        mock_state["backtest_result"] = {"metrics": sample_metrics,
                                          "initial_capital": 200_000, "final_asset": 230_000}
        mock_state["risk_report"] = {"risk_assessment": {"risk_level": "中",
                                                          "risk_warnings": ["⚠️ 注意"]},
                                      "suggestions": ["改进1"]}
        mock_state["factors"] = ["MA5"]
        mock_state["signals"] = {"buy_count": 2, "sell_count": 1}
        mock_state["duration"] = 1.0

        report = agent.generate_report(mock_state)
        assert "600519.SH" in report
        assert "200,000.00" in report
        assert "15.00%" in report  # total_return 15%
        assert "中" in report

    # ---- execute ----

    def test_execute_generates_report_and_saves(self, agent, mock_state, patch_report_file):
        mock_state["backtest_result"] = {
            "metrics": dict(
                total_return=0.10, annual_return=0.05, annual_volatility=0.12,
                sharpe_ratio=1.5, max_drawdown=-0.05, max_drawdown_duration=3,
                calmar_ratio=0.8, total_trades=20, round_trips=10,
                win_rate=0.7, profit_loss_ratio=2.0,
                avg_win_profit=500.0, avg_loss=250.0,
                benchmark_return=0.03, benchmark_annual_return=0.025,
                excess_return=0.025,
                daily_returns=pd.Series([0.001] * 10),
            ),
            "initial_capital": 100_000,
            "final_asset": 110_000,
        }
        mock_state["duration"] = 0.5
        mock_state["factors"] = ["MA5", "RSI"]
        mock_state["signals"] = {"buy_count": 3, "sell_count": 1}
        result = agent.execute(mock_state)
        assert result["risk_report"] is not None
        assert "risk_assessment" in result["risk_report"]
        assert "suggestions" in result["risk_report"]
        assert result["final_report"] is not None
        assert patch_report_file.exists()
        content = patch_report_file.read_text(encoding="utf-8")
        assert "📊" in content
