"""
FactorAgent - 多因子计算模块
职责：并行计算各类量化因子（均线/动量/波动率/量价）
采用 ThreadPoolExecutor 多线程并行计算，提升效率
"""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from utils.config import FACTORIZER_MAX_WORKERS


class FactorAgent(BaseAgent):
    """
    多因子计算Agent
    职责：并行计算各类量化因子，支持技术因子、量价因子、波动率因子等
    """

    def __init__(self):
        super().__init__("多因子计算Agent")

    # ------------------------------------------------------------------
    # 因子计算函数
    # ------------------------------------------------------------------

    def calc_ma_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """均线类因子（5个）"""
        self.log("计算均线类因子...")
        factors = {}
        for window in [5, 10, 20, 60]:
            factors[f'MA{window}'] = df['close'].rolling(window).mean()
        factors['MA_bull'] = (
            (factors['MA5'] > factors['MA10']) &
            (factors['MA10'] > factors['MA20'])
        ).astype(int)
        return factors

    def calc_momentum_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """动量类因子（7个）"""
        self.log("计算动量类因子...")
        factors = {}

        # RSI(14)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        factors['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        factors['MACD_DIF'] = ema12 - ema26
        factors['MACD_DEA'] = factors['MACD_DIF'].ewm(span=9).mean()
        factors['MACD_HIST'] = 2 * (factors['MACD_DIF'] - factors['MACD_DEA'])

        # 收益率动量
        for window in [5, 10, 20]:
            factors[f'momentum_{window}d'] = df['close'].pct_change(window)

        return factors

    def calc_volatility_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """波动率类因子（7个）"""
        self.log("计算波动率类因子...")
        factors = {}

        # 布林带
        boll_mid = df['close'].rolling(20).mean()
        boll_std = df['close'].rolling(20).std()
        factors['BOLL_MID'] = boll_mid
        factors['BOLL_STD'] = boll_std
        factors['BOLL_UPPER'] = boll_mid + 2 * boll_std
        factors['BOLL_LOWER'] = boll_mid - 2 * boll_std
        upper_minus_lower = factors['BOLL_UPPER'] - factors['BOLL_LOWER']
        factors['BOLL_POS'] = (df['close'] - factors['BOLL_LOWER']) / upper_minus_lower

        # 年化波动率
        factors['volatility_20d'] = df['pct_chg'].rolling(20).std() * np.sqrt(252)

        # ATR(14)
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift())
        tr3 = abs(df['low'] - df['close'].shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        factors['ATR'] = tr.rolling(14).mean()

        return factors

    def calc_volume_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """量价类因子（4个）"""
        self.log("计算量价类因子...")
        factors = {}
        factors['VOL_MA5'] = df['volume'].rolling(5).mean()
        factors['VOL_MA10'] = df['volume'].rolling(10).mean()
        factors['VOL_RATIO'] = factors['VOL_MA5'] / factors['VOL_MA10']
        factors['VWAP'] = (
            (df['close'] * df['volume']).rolling(20).sum() /
            df['volume'].rolling(20).sum()
        )
        return factors

    # ------------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------------

    def calc_cci_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """CCI 商品通道指数（1个）"""
        self.log("计算CCI因子...")
        factors = {}
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(14).mean()
        mad_tp = typical_price.rolling(14).mean()
        # MAD = mean absolute deviation
        mad_tp = typical_price.rolling(14).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        factors['CCI'] = (typical_price - sma_tp) / (0.015 * mad_tp)
        return factors

    def calc_kdj_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """KDJ 随机指标（3个）"""
        self.log("计算KDJ因子...")
        factors = {}
        low_n = df['low'].rolling(9).min()
        high_n = df['high'].rolling(9).max()
        rsv = (df['close'] - low_n) / (high_n - low_n) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        factors['KDJ_K'] = k
        factors['KDJ_D'] = d
        factors['KDJ_J'] = j
        return factors

    def calc_adx_factors(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """ADX 平均趋向指标（3个：+DI, -DI, ADX）"""
        self.log("计算ADX因子...")
        factors = {}
        # 若 ATR 未预计算，则内部计算
        if "ATR" in df.columns:
            atr = df["ATR"]
        else:
            tr1 = df["high"] - df["low"]
            tr2 = abs(df["high"] - df["close"].shift())
            tr3 = abs(df["low"] - df["close"].shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()

        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        factors["PLUS_DI"] = plus_di
        factors["MINUS_DI"] = minus_di
        factors["ADX"] = adx
        return factors

    def execute(self, state: dict) -> dict:
        df = state['data']

        factor_tasks: list[Callable[[pd.DataFrame], dict]] = [
            self.calc_ma_factors,
            self.calc_momentum_factors,
            self.calc_volatility_factors,
            self.calc_volume_factors,
            self.calc_cci_factors,
            self.calc_kdj_factors,
            self.calc_adx_factors,
        ]

        all_factors: dict[str, pd.Series] = {}

        with ThreadPoolExecutor(max_workers=FACTORIZER_MAX_WORKERS) as executor:
            futures = [executor.submit(task, df) for task in factor_tasks]
            for future in as_completed(futures):
                all_factors.update(future.result())

        # 将因子合并到行情数据中
        for name, factor in all_factors.items():
            df[name] = factor

        df = df.dropna()

        state['data'] = df
        state['factors'] = list(all_factors.keys())
        self.log(f"多因子计算完成，共生成{len(all_factors)}个因子: {list(all_factors.keys())}")
        return state
