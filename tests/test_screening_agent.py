"""
ScreeningAgent 单元测试
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_db_path(tmp_path):
    """创建临时 SQLite 数据库，含模拟 ticker 数据"""
    import sqlite3
    db = tmp_path / "test_cache.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE kline_cache (
            ticker TEXT, start TEXT, end TEXT, freq TEXT, ttl INTEGER, data BLOB
        )
    """)
    tickers = [
        "sh.600000", "sh.600001", "sz.000001", "sz.000002",
        "bj.920000", "bj.920001",
    ]
    for t in tickers:
        df = pd.DataFrame({
            "timestamps": pd.date_range("2023-01-01", periods=50, freq="B"),
            "open": [10.0] * 50,
            "high": [11.0] * 50,
            "low": [9.0] * 50,
            "close": [10.5] * 50,
            "volume": [1_000_000] * 50,
            "amount": [10_500_000] * 50,
        })
        import pickle
        conn.execute(
            "INSERT INTO kline_cache (ticker, start, end, freq, ttl, data) VALUES (?,?,?,?,?,?)",
            (t, "2023-01-01", "2023-12-31", "1d", 86400, pickle.dumps(df)),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def sample_result_df():
    """构造一份模拟筛选结果 DataFrame"""
    return pd.DataFrame({
        "symbol": ["sz.000001", "sh.600519", "sh.600036"],
        "total_return": [0.05, 0.12, -0.03],
        "annual_return": [0.04, 0.10, -0.02],
        "sharpe_ratio": [0.3, 0.8, -0.1],
        "max_drawdown": [-0.08, -0.15, -0.05],
        "win_rate": [0.4, 0.55, 0.35],
        "total_trades": [20, 30, 15],
        "risk_level": ["中", "低", "高"],
        "final_asset": [105000, 112000, 97000],
    })


class TestGetAvailableTickers:
    """测试股票池获取"""

    def test_get_all_tickers(self, mock_db_path):
        from agents.screening_agent import ScreeningAgent
        tickers = ScreeningAgent.get_available_tickers(db_path=mock_db_path)
        assert len(tickers) == 6
        assert "sh.600000" in tickers
        assert "sz.000001" in tickers

    def test_exchange_filter(self, mock_db_path):
        from agents.screening_agent import ScreeningAgent
        tickers = ScreeningAgent.get_available_tickers(
            db_path=mock_db_path, exchange_filter=["sh"]
        )
        assert all(t.startswith("sh.") for t in tickers)
        assert len(tickers) == 2

    def test_exchange_filter_sz(self, mock_db_path):
        from agents.screening_agent import ScreeningAgent
        tickers = ScreeningAgent.get_available_tickers(
            db_path=mock_db_path, exchange_filter=["sz"]
        )
        assert all(t.startswith("sz.") for t in tickers)
        assert len(tickers) == 2

    def test_nonexistent_db(self):
        from agents.screening_agent import ScreeningAgent
        tickers = ScreeningAgent.get_available_tickers(
            db_path=Path("/nonexistent/path.db")
        )
        assert tickers == []

    def test_empty_exchange_filter(self, mock_db_path):
        from agents.screening_agent import ScreeningAgent
        tickers = ScreeningAgent.get_available_tickers(
            db_path=mock_db_path, exchange_filter=[]
        )
        assert tickers == []


class TestPrintSummary:
    """测试结果展示"""

    def test_print_summary_empty(self):
        from agents.screening_agent import ScreeningAgent
        result = ScreeningAgent.print_summary(pd.DataFrame())
        assert "暂无筛选结果" in result

    def test_print_summary_with_data(self, sample_result_df):
        from agents.screening_agent import ScreeningAgent
        result = ScreeningAgent.print_summary(sample_result_df)
        assert "# 📊 多Agent量化筛选结果" in result
        assert "sz.000001" in result
        assert "sh.600519" in result


class TestSaveResults:
    """测试结果保存"""

    def test_save_results(self, sample_result_df, tmp_path):
        from agents.screening_agent import ScreeningAgent
        output = tmp_path / "test_screening.md"
        ScreeningAgent.save_results(sample_result_df, str(output))
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "sz.000001" in content


class TestRunSingle:
    """测试单票流水线执行（mock OrchestratorAgent）"""

    def test_run_single_success(self, sample_with_factors):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        config = {
            "symbol": "sz.000001",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "vote_threshold": 2,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "trend_filter": True,
            "trend_ma_window": 60,
        }
        with patch("agents.orchestrator_agent.OrchestratorAgent") as MockOrch:
            mock_state = {
                "task_config": config,
                "start_time": datetime.now(),
                "status": "success",
                "errors": [],
                "data": sample_with_factors,
                "factors": {},
                "signals": None,
                "backtest_result": {
                    "metrics": {
                        "total_return": 0.05,
                        "annual_return": 0.04,
                        "annual_volatility": 0.15,
                        "sharpe_ratio": 0.5,
                        "max_drawdown": -0.08,
                        "calmar_ratio": 0.5,
                        "win_rate": 0.45,
                        "profit_loss_ratio": 1.2,
                        "total_trades": 20,
                        "round_trips": 10,
                        "benchmark_return": 0.03,
                        "excess_return": 0.02,
                        "daily_returns": pd.Series([0.001] * 10),
                    },
                    "trades": [],
                    "final_asset": 105000,
                    "final_position": 0,
                },
                "risk_report": {
                    "risk_assessment": {"risk_level": "低", "risk_warnings": []},
                    "suggestions": [],
                },
                "final_report": None,
            }
            mock_orch = MagicMock()
            mock_orch.execute.return_value = mock_state
            MockOrch.return_value = mock_orch

            result = sa.run_single("sz.000001", config)
            assert result is not None
            assert result["symbol"] == "sz.000001"
            assert result["metrics"]["total_return"] == 0.05

    def test_run_single_no_data(self):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        config = {
            "symbol": "sz.999999",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "vote_threshold": 2,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "trend_filter": True,
            "trend_ma_window": 60,
        }
        with patch("agents.orchestrator_agent.OrchestratorAgent") as MockOrch:
            mock_state = {
                "task_config": config,
                "start_time": datetime.now(),
                "status": "failed",
                "errors": ["数据获取失败"],
                "data": pd.DataFrame(),
                "factors": {},
                "signals": None,
                "backtest_result": None,
                "risk_report": None,
                "final_report": None,
            }
            mock_orch = MagicMock()
            mock_orch.execute.return_value = mock_state
            MockOrch.return_value = mock_orch

            result = sa.run_single("sz.999999", config)
            assert result is None


class TestRunScreening:
    """测试批量筛选逻辑（mock 单票执行）"""

    def test_run_screening_basic(self, sample_with_factors):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        symbols = ["sz.000001", "sh.600519"]
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "vote_threshold": 2,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "sort_by": "total_return",
            "top_n": None,
            "min_sharpe": None,
        }

        with patch.object(sa, "run_single") as mock_run:
            mock_run.side_effect = [
                {
                    "symbol": "sz.000001",
                    "metrics": {
                        "total_return": 0.10, "annual_return": 0.08,
                        "annual_volatility": 0.15, "sharpe_ratio": 0.6,
                        "max_drawdown": -0.08, "calmar_ratio": 1.0,
                        "win_rate": 0.5, "profit_loss_ratio": 1.5,
                        "total_trades": 20, "round_trips": 10,
                        "benchmark_return": 0.05, "excess_return": 0.03,
                        "daily_returns": pd.Series([0.001] * 10),
                    },
                    "risk_level": "低",
                    "risk_warnings": [],
                    "trades": [],
                    "final_asset": 110000,
                },
                {
                    "symbol": "sh.600519",
                    "metrics": {
                        "total_return": 0.05, "annual_return": 0.04,
                        "annual_volatility": 0.12, "sharpe_ratio": 0.4,
                        "max_drawdown": -0.06, "calmar_ratio": 0.67,
                        "win_rate": 0.4, "profit_loss_ratio": 1.2,
                        "total_trades": 15, "round_trips": 7,
                        "benchmark_return": 0.03, "excess_return": 0.01,
                        "daily_returns": pd.Series([0.001] * 10),
                    },
                    "risk_level": "中",
                    "risk_warnings": [],
                    "trades": [],
                    "final_asset": 105000,
                },
            ]
            result_df = sa.run_screening(symbols, **config)
            assert len(result_df) == 2
            assert result_df.iloc[0]["symbol"] == "sz.000001"  # 收益更高排第一

    def test_run_screening_top_n(self, sample_with_factors):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        symbols = ["sz.000001", "sh.600519", "sh.600036"]
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "vote_threshold": 2,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "sort_by": "total_return",
            "top_n": 2,
            "min_sharpe": None,
        }

        with patch.object(sa, "run_single") as mock_run:
            mock_run.side_effect = [
                {"symbol": "sz.000001", "metrics": {
                    "total_return": 0.10, "annual_return": 0.08,
                    "annual_volatility": 0.15, "sharpe_ratio": 0.6,
                    "max_drawdown": -0.08, "calmar_ratio": 1.0,
                    "win_rate": 0.5, "profit_loss_ratio": 1.5,
                    "total_trades": 20, "round_trips": 10,
                    "benchmark_return": 0.05, "excess_return": 0.03,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "低", "risk_warnings": [], "trades": [], "final_asset": 110000},
                {"symbol": "sh.600519", "metrics": {
                    "total_return": 0.05, "annual_return": 0.04,
                    "annual_volatility": 0.12, "sharpe_ratio": 0.4,
                    "max_drawdown": -0.06, "calmar_ratio": 0.67,
                    "win_rate": 0.4, "profit_loss_ratio": 1.2,
                    "total_trades": 15, "round_trips": 7,
                    "benchmark_return": 0.03, "excess_return": 0.01,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "中", "risk_warnings": [], "trades": [], "final_asset": 105000},
                {"symbol": "sh.600036", "metrics": {
                    "total_return": 0.02, "annual_return": 0.01,
                    "annual_volatility": 0.10, "sharpe_ratio": 0.2,
                    "max_drawdown": -0.04, "calmar_ratio": 0.25,
                    "win_rate": 0.35, "profit_loss_ratio": 1.0,
                    "total_trades": 10, "round_trips": 5,
                    "benchmark_return": 0.01, "excess_return": 0.0,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "低", "risk_warnings": [], "trades": [], "final_asset": 102000},
            ]
            result_df = sa.run_screening(symbols, **config)
            assert len(result_df) == 2
            assert result_df.iloc[0]["symbol"] == "sz.000001"

    def test_run_screening_min_sharpe_filter(self, sample_with_factors):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        symbols = ["sz.000001", "sh.600519"]
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "vote_threshold": 2,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "sort_by": "sharpe_ratio",
            "top_n": None,
            "min_sharpe": 0.5,
        }

        with patch.object(sa, "run_single") as mock_run:
            mock_run.side_effect = [
                {"symbol": "sz.000001", "metrics": {
                    "total_return": 0.10, "annual_return": 0.08,
                    "annual_volatility": 0.15, "sharpe_ratio": 0.6,
                    "max_drawdown": -0.08, "calmar_ratio": 1.0,
                    "win_rate": 0.5, "profit_loss_ratio": 1.5,
                    "total_trades": 20, "round_trips": 10,
                    "benchmark_return": 0.05, "excess_return": 0.03,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "低", "risk_warnings": [], "trades": [], "final_asset": 110000},
                {"symbol": "sh.600519", "metrics": {
                    "total_return": 0.05, "annual_return": 0.04,
                    "annual_volatility": 0.12, "sharpe_ratio": 0.4,
                    "max_drawdown": -0.06, "calmar_ratio": 0.67,
                    "win_rate": 0.4, "profit_loss_ratio": 1.2,
                    "total_trades": 15, "round_trips": 7,
                    "benchmark_return": 0.03, "excess_return": 0.01,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "中", "risk_warnings": [], "trades": [], "final_asset": 105000},
            ]
            result_df = sa.run_screening(symbols, **config)
            assert len(result_df) == 1
            assert result_df.iloc[0]["symbol"] == "sz.000001"

    def test_run_screening_all_fail(self):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        symbols = ["sz.999999", "sh.999999"]
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "vote_threshold": 2,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "sort_by": "total_return",
            "top_n": None,
            "min_sharpe": None,
        }

        with patch.object(sa, "run_single") as mock_run:
            mock_run.return_value = None
            result_df = sa.run_screening(symbols, **config)
            assert result_df.empty

    def test_run_screening_sort_by_max_drawdown(self, sample_with_factors):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        symbols = ["sz.000001", "sh.600519"]
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100_000,
            "vote_threshold": 2,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "stop_loss_pct": 0.08,
            "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.05,
            "sort_by": "max_drawdown",
            "top_n": None,
            "min_sharpe": None,
        }

        with patch.object(sa, "run_single") as mock_run:
            mock_run.side_effect = [
                {"symbol": "sz.000001", "metrics": {
                    "total_return": 0.10, "annual_return": 0.08,
                    "annual_volatility": 0.15, "sharpe_ratio": 0.6,
                    "max_drawdown": -0.08, "calmar_ratio": 1.0,
                    "win_rate": 0.5, "profit_loss_ratio": 1.5,
                    "total_trades": 20, "round_trips": 10,
                    "benchmark_return": 0.05, "excess_return": 0.03,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "低", "risk_warnings": [], "trades": [], "final_asset": 110000},
                {"symbol": "sh.600519", "metrics": {
                    "total_return": 0.05, "annual_return": 0.04,
                    "annual_volatility": 0.12, "sharpe_ratio": 0.4,
                    "max_drawdown": -0.06, "calmar_ratio": 0.67,
                    "win_rate": 0.4, "profit_loss_ratio": 1.2,
                    "total_trades": 15, "round_trips": 7,
                    "benchmark_return": 0.03, "excess_return": 0.01,
                    "daily_returns": pd.Series([0.001] * 10),
                }, "risk_level": "中", "risk_warnings": [], "trades": [], "final_asset": 105000},
            ]
            result_df = sa.run_screening(symbols, **config)
            # max_drawdown 降序：-0.06 > -0.08，所以 sh.600519 排第一
            assert result_df.iloc[0]["symbol"] == "sh.600519"


class TestExecute:
    """测试 execute 入口"""

    def test_execute_with_symbols(self):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        state = {
            "screening_config": {
                "symbols": ["sz.000001", "sh.600519"],
                "sort_by": "total_return",
                "top_n": None,
                "min_sharpe": None,
            }
        }
        with patch.object(sa, "run_screening") as mock_run:
            mock_run.return_value = pd.DataFrame({
                "symbol": ["sz.000001"],
                "total_return": [0.10],
                "sharpe_ratio": [0.6],
                "max_drawdown": [-0.08],
            })
            result = sa.execute(state)
            assert "screening_result" in result
            assert len(result["screening_result"]) == 1

    def test_execute_no_symbols(self):
        from agents.screening_agent import ScreeningAgent
        sa = ScreeningAgent()
        state = {"screening_config": {}}
        result = sa.execute(state)
        assert result["screening_result"].empty
