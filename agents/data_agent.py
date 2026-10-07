"""
DataAgent - 数据获取与清洗模块
职责：从 trade-krono-cli 真实数据源获取 K 线、数据清洗、缺失值处理、标准化
数据源：outputs/cache/pipeline_cache.db（kline_cache 表）
"""
import pandas as pd
import numpy as np

from agents.base_agent import BaseAgent
from agents.data_provider import fetch_kline_from_cache


class DataAgent(BaseAgent):
    """
    数据Agent
    职责：自动生成/获取行情数据、数据清洗、缺失值处理、标准化
    """

    def __init__(self):
        super().__init__("数据获取Agent")

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """数据清洗：处理缺失值、异常值、计算涨跌幅"""
        self.log("开始数据清洗与标准化")

        # 处理缺失值：前向填充 + 后向填充
        df = df.ffill().bfill()

        # 异常值处理：价格波动超过20%视为异常，用前值填充
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                pct_change = df[col].pct_change().abs()
                df.loc[pct_change > 0.2, col] = np.nan
        df = df.ffill().bfill()

        # 计算基础字段：涨跌幅
        df["pct_chg"] = df["close"].pct_change()
        df["pct_chg"] = df["pct_chg"].fillna(0)

        return df

    def execute(self, state: dict) -> dict:
        config = state["task_config"]
        symbol = config.get("symbol", "000001.SZ")
        start_date = config.get("start_date", "2023-01-01")
        end_date = config.get("end_date", "2026-09-30")

        self.log(f"从 trade-krono-cli 缓存加载 K 线: {symbol}")
        df = fetch_kline_from_cache(symbol, start_date, end_date)

        if df is None or df.empty:
            self.log("⚠️ 未找到真实数据，回退至演示数据生成")
            df = self._generate_demo_data(start_date, end_date, symbol)

        df = self.clean_data(df)

        state["data"] = df
        self.log(
            f"数据获取完成，共{len(df)}条K线，"
            f"时间范围: {df.index[0].date()} 至 {df.index[-1].date()}"
        )
        return state

    # ------------------------------------------------------------------
    # 演示数据回退（缓存不可用时使用）
    # ------------------------------------------------------------------

    def _generate_demo_data(self, start_date: str, end_date: str,
                            symbol: str = "DEMO") -> pd.DataFrame:
        """生成模拟行情数据用于演示，实际使用时可替换为 Tushare/AkShare/FinScope API"""
        self.log("生成演示行情数据（可替换为真实API数据源）")

        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        n = len(dates)

        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.02, n)
        close = 100 * np.cumprod(1 + returns)

        high = close * (1 + np.random.uniform(0, 0.03, n))
        low = close * (1 - np.random.uniform(0, 0.03, n))
        open_price = low + np.random.uniform(0, 1, n) * (high - low)
        volume = np.random.randint(1_000_000, 10_000_000, n)

        df = pd.DataFrame({
            'open': open_price, 'high': high, 'low': low,
            'close': close, 'volume': volume,
        }, index=dates)
        df['symbol'] = symbol
        return df
