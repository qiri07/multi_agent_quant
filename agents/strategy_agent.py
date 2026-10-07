"""
StrategyAgent - 策略信号生成模块
职责：基于因子数据生成交易信号，支持多策略投票融合
"""

import pandas as pd

from agents.base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """
    策略信号Agent
    职责：基于计算好的因子生成交易信号（买入/卖出/持有），支持多策略融合
    默认实现：双均线 + RSI + MACD + 布林带 四策略投票
    """

    def __init__(self):
        super().__init__("策略信号Agent")

    # ------------------------------------------------------------------
    # 子策略信号生成
    # ------------------------------------------------------------------

    def ma_cross_strategy(self, df: pd.DataFrame) -> pd.Series:
        """双均线金叉死叉策略"""
        self.log("生成双均线策略信号...")
        signal = pd.Series(0, index=df.index)
        golden_cross = (
            (df['MA5'] > df['MA10']) &
            (df['MA5'].shift() <= df['MA10'].shift())
        )
        death_cross = (
            (df['MA5'] < df['MA10']) &
            (df['MA5'].shift() >= df['MA10'].shift())
        )
        signal[golden_cross] = 1
        signal[death_cross] = -1
        return signal

    def rsi_strategy(self, df: pd.DataFrame) -> pd.Series:
        """RSI 超买超卖策略"""
        self.log("生成RSI策略信号...")
        signal = pd.Series(0, index=df.index)
        signal[df['RSI'] < 30] = 1
        signal[df['RSI'] > 70] = -1
        return signal

    def macd_strategy(self, df: pd.DataFrame) -> pd.Series:
        """MACD 金叉死叉策略"""
        self.log("生成MACD策略信号...")
        signal = pd.Series(0, index=df.index)
        macd_gold = (
            (df['MACD_DIF'] > df['MACD_DEA']) &
            (df['MACD_DIF'].shift() <= df['MACD_DEA'].shift())
        )
        macd_death = (
            (df['MACD_DIF'] < df['MACD_DEA']) &
            (df['MACD_DIF'].shift() >= df['MACD_DEA'].shift())
        )
        signal[macd_gold] = 1
        signal[macd_death] = -1
        return signal

    def boll_strategy(self, df: pd.DataFrame) -> pd.Series:
        """布林带突破策略"""
        self.log("生成布林带策略信号...")
        signal = pd.Series(0, index=df.index)
        signal[df['close'] < df['BOLL_LOWER']] = 1
        signal[df['close'] > df['BOLL_UPPER']] = -1
        return signal

    def cci_strategy(self, df: pd.DataFrame) -> pd.Series:
        """CCI 商品通道指数震荡策略

        CCI 从下方穿越 -100 时做多，从上方穿越 +100 时做空。
        """
        self.log("生成CCI策略信号...")
        signal = pd.Series(0, index=df.index)
        cci = df['CCI']
        # 买入：CCI 从下方穿越 -100
        buy = (cci <= -100) & (cci.shift(1) > -100)
        # 卖出：CCI 从上方穿越 +100
        sell = (cci >= 100) & (cci.shift(1) < 100)
        signal[buy] = 1
        signal[sell] = -1
        return signal

    def kdj_strategy(self, df: pd.DataFrame) -> pd.Series:
        """KDJ 随机指标超买超卖策略

        超卖区金叉做多（K<30 且 K上穿D），超买区死叉做空（K>70 且 K下穿D）。
        """
        self.log("生成KDJ策略信号...")
        signal = pd.Series(0, index=df.index)
        k = df['KDJ_K']
        d = df['KDJ_D']
        # 买入：K 上穿 D 且在超卖区（K < 30）
        buy = (k > d) & (k.shift(1) <= d.shift(1)) & (k < 30)
        # 卖出：K 下穿 D 且在超买区（K > 70）
        sell = (k < d) & (k.shift(1) >= d.shift(1)) & (k > 70)
        signal[buy] = 1
        signal[sell] = -1
        return signal

    def adx_trend_strategy(self, df: pd.DataFrame) -> pd.Series:
        """ADX 趋势强度策略

        +DI 上穿 -DI 且 ADX > 20 做多；-DI 上穿 +DI 且 ADX > 20 做空。
        """
        self.log("生成ADX趋势强度策略信号...")
        signal = pd.Series(0, index=df.index)
        plus_di = df['PLUS_DI']
        minus_di = df['MINUS_DI']
        adx = df['ADX']
        # 买入：+DI 上穿 -DI 且 ADX 确认趋势强度
        buy = (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1)) & (adx > 20)
        # 卖出：-DI 上穿 +DI 且 ADX 确认趋势强度
        sell = (minus_di > plus_di) & (minus_di.shift(1) <= plus_di.shift(1)) & (adx > 20)
        signal[buy] = 1
        signal[sell] = -1
        return signal

    def volume_divergence_strategy(self, df: pd.DataFrame) -> pd.Series:
        """量价背离策略

        放量破位做多（价格创新低 + 成交量放大）；
        缩量创新高做空（价格创新高 + 成交量萎缩）。
        """
        self.log("生成量价背离策略信号...")
        signal = pd.Series(0, index=df.index)
        vol_ratio = df['VOL_RATIO']
        # 价格创新低（20日）且放量 → 做多
        price_new_low = df['close'] == df['close'].rolling(20).min()
        high_vol = vol_ratio > 1.5
        buy = price_new_low & high_vol
        # 价格创新高（20日）且缩量 → 做空
        price_new_high = df['close'] == df['close'].rolling(20).max()
        low_vol = vol_ratio < 0.5
        sell = price_new_high & low_vol
        signal[buy] = 1
        signal[sell] = -1
        return signal

    # ------------------------------------------------------------------
    # 信号融合
    # ------------------------------------------------------------------

    @staticmethod
    def fuse_signals(signals: list[pd.Series], threshold: int = 2) -> pd.Series:
        """多策略信号融合：多数投票机制

        Args:
            signals: 各子策略产生的信号序列列表（1=买入, -1=卖出, 0=持有）
            threshold: 至少需要几个策略一致才确认信号

        Returns:
            融合后的最终信号序列
        """
        signal_sum = sum(signals)
        final_signal = pd.Series(0, index=signal_sum.index)
        final_signal[signal_sum >= threshold] = 1
        final_signal[signal_sum <= -threshold] = -1
        return final_signal

    @staticmethod
    def apply_trend_filter(
        df: pd.DataFrame,
        signal: pd.Series,
        ma_window: int = 60,
    ) -> pd.Series:
        """趋势过滤：仅在趋势向上时允许买入，趋势向下时允许卖出

        当价格高于 MA 时视为上升趋势，只保留买入信号；
        当价格低于 MA 时视为下降趋势，只保留卖出信号。
        """
        if ma_window <= 0 or "MA" + str(ma_window) not in df.columns:
            return signal  # 无均线数据或未启用过滤，直接返回原信号

        trend_up = df["close"] > df[f"MA{ma_window}"]
        trend_down = df["close"] <= df[f"MA{ma_window}"]

        filtered = signal.copy()
        filtered[trend_up & (signal == -1)] = 0   # 上升趋势中取消卖出信号
        filtered[trend_down & (signal == 1)] = 0   # 下降趋势中取消买入信号
        return filtered

    # ------------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------------

    def execute(self, state: dict) -> dict:
        df = state['data']
        config = state['task_config']

        # 生成各子策略信号（8个策略）
        ma_signal = self.ma_cross_strategy(df)
        rsi_signal = self.rsi_strategy(df)
        macd_signal = self.macd_strategy(df)
        boll_signal = self.boll_strategy(df)
        cci_signal = self.cci_strategy(df)
        kdj_signal = self.kdj_strategy(df)
        adx_signal = self.adx_trend_strategy(df)
        vol_signal = self.volume_divergence_strategy(df)

        # 信号融合
        vote_threshold = config.get('vote_threshold', 2)
        self.log(f"多策略信号融合，投票阈值: {vote_threshold}个策略一致")
        final_signal = self.fuse_signals(
            [ma_signal, rsi_signal, macd_signal, boll_signal,
             cci_signal, kdj_signal, adx_signal, vol_signal],
            threshold=vote_threshold,
        )

        # 趋势过滤（可选）
        if config.get('trend_filter', True):
            ma_window = config.get('trend_ma_window', 60)
            final_signal = self.apply_trend_filter(df, final_signal, ma_window=ma_window)
            self.log(f"趋势过滤已启用（MA{ma_window}），过滤后信号已更新")

        df['signal'] = final_signal

        # 统计信号数量
        buy_count = int((final_signal == 1).sum())
        sell_count = int((final_signal == -1).sum())
        hold_count = int((final_signal == 0).sum())

        state['data'] = df
        state['signals'] = {
            'buy_count': buy_count,
            'sell_count': sell_count,
            'hold_count': hold_count,
            'signal_series': final_signal,
        }
        self.log(
            f"信号生成完成：买入信号{buy_count}次，卖出信号{sell_count}次，持有{hold_count}天"
        )
        return state
