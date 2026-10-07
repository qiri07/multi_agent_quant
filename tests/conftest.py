"""
共享 pytest fixtures，供所有测试文件使用
"""

import numpy as np
import pandas as pd
import pytest

# =============================================================================
#  fixtures：构造标准测试数据 DataFrame
# =============================================================================

@pytest.fixture
def sample_ohlcv():
    """生成一段干净的 OHLCV 测试数据（100 个交易日），含 pct_chg"""
    np.random.seed(0)
    n = 100
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = 100 * np.cumprod(1 + np.random.normal(0.0003, 0.015, n))
    high = close * (1 + np.random.uniform(0, 0.02, n))
    low = close * (1 - np.random.uniform(0, 0.02, n))
    open_price = low + np.random.uniform(0, 1, n) * (high - low)
    volume = np.random.randint(1_000_000, 5_000_000, n)
    df = pd.DataFrame({
        "open": open_price, "high": high, "low": low,
        "close": close, "volume": volume,
    }, index=dates)
    df["pct_chg"] = df["close"].pct_change().fillna(0)
    return df


@pytest.fixture
def sample_with_factors(sample_ohlcv):
    """在 sample_ohlcv 基础上注入因子列，供策略/回测 Agent 使用"""
    df = sample_ohlcv.copy()
    # 均线
    for w in [5, 10, 20, 60]:
        df[f"MA{w}"] = df["close"].rolling(w).mean()
    df["MA_bull"] = ((df["MA5"] > df["MA10"]) & (df["MA10"] > df["MA20"])).astype(int)
    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + rs))
    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["MACD_DIF"] = ema12 - ema26
    df["MACD_DEA"] = df["MACD_DIF"].ewm(span=9).mean()
    df["MACD_HIST"] = 2 * (df["MACD_DIF"] - df["MACD_DEA"])
    # 布林带
    boll_mid = df["close"].rolling(20).mean()
    boll_std = df["close"].rolling(20).std()
    df["BOLL_MID"] = boll_mid
    df["BOLL_UPPER"] = boll_mid + 2 * boll_std
    df["BOLL_LOWER"] = boll_mid - 2 * boll_std
    # CCI
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = typical_price.rolling(14).mean()
    mad_tp = typical_price.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["CCI"] = (typical_price - sma_tp) / (0.015 * mad_tp)
    # KDJ
    low_n = df["low"].rolling(9).min()
    high_n = df["high"].rolling(9).max()
    rsv = (df["close"] - low_n) / (high_n - low_n) * 100
    df["KDJ_K"] = rsv.ewm(com=2, adjust=False).mean()
    df["KDJ_D"] = df["KDJ_K"].ewm(com=2, adjust=False).mean()
    df["KDJ_J"] = 3 * df["KDJ_K"] - 2 * df["KDJ_D"]
    # ADX (+DI / -DI / ADX)
    atr = df["close"].diff().abs().rolling(14).mean().replace(0, np.nan)
    atr = atr.bfill()
    plus_dm = df["high"].diff().where(
        (df["high"].diff() > -df["low"].diff()) & (df["high"].diff() > 0), 0)
    minus_dm = (-df["low"].diff()).where(
        (-df["low"].diff() > df["high"].diff()) & (-df["low"].diff() > 0), 0)
    df["PLUS_DI"] = 100 * (plus_dm.rolling(14).mean() / atr)
    df["MINUS_DI"] = 100 * (minus_dm.rolling(14).mean() / atr)
    dx = 100 * abs(df["PLUS_DI"] - df["MINUS_DI"]) / (df["PLUS_DI"] + df["MINUS_DI"])
    df["ADX"] = dx.rolling(14).mean()
    # 量价
    df["VOL_MA5"] = df["volume"].rolling(5).mean()
    df["VOL_MA10"] = df["volume"].rolling(10).mean()
    df["VOL_RATIO"] = df["VOL_MA5"] / df["VOL_MA10"]
    # pct_chg
    df["pct_chg"] = df["close"].pct_change().fillna(0)
    return df.dropna()


@pytest.fixture
def sample_metrics():
    """构造一份标准的绩效指标字典，供 RiskAgent 测试"""
    return {
        "total_return": 0.15,
        "annual_return": 0.08,
        "annual_volatility": 0.18,
        "sharpe_ratio": 0.7,
        "max_drawdown": -0.12,
        "max_drawdown_duration": 5,
        "calmar_ratio": 0.67,
        "total_trades": 30,
        "round_trips": 15,
        "win_rate": 0.60,
        "profit_loss_ratio": 1.8,
        "avg_win_profit": 500.0,
        "avg_loss": 300.0,
        "benchmark_return": 0.05,
        "benchmark_annual_return": 0.04,
        "excess_return": 0.04,
        "daily_returns": pd.Series([0.001] * 10),
    }


@pytest.fixture
def mock_state():
    """最小化流水线中间状态，用于直接测试单个 Agent"""
    return {
        "task_config": {
            "symbol": "000001.SZ",
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
            "initial_capital": 100_000,
            "commission_rate": 0.0003,
            "slippage": 0.0001,
            "position_ratio": 1.0,
            "vote_threshold": 2,
        },
        "data": None,
        "factors": [],
        "signals": None,
        "backtest_result": None,
        "risk_report": None,
        "final_report": None,
    }


@pytest.fixture
def patch_report_file(tmp_path, monkeypatch):
    """将报告保存路径临时指向测试目录，避免污染项目根目录"""
    test_report = tmp_path / "回测报告.md"
    monkeypatch.setattr("agents.risk_agent.REPORT_FILENAME", str(test_report))
    return test_report
