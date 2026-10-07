"""
BacktestAgent - 回测执行模块
职责：基于交易信号执行回测，计算净值曲线，输出完整绩效指标
"""
import pandas as pd
import numpy as np
from typing import Dict

from agents.base_agent import BaseAgent


class BacktestAgent(BaseAgent):
    """
    回测Agent
    职责：执行回测、计算净值曲线、统计完整绩效指标
    支持：手续费、滑点、整手交易、仓位管理
    """

    def __init__(self):
        super().__init__("回测执行Agent")

    # ------------------------------------------------------------------
    # 回测引擎
    # ------------------------------------------------------------------

    def run_backtest(self, df: pd.DataFrame, config: Dict) -> Dict:
        """执行事件驱动回测"""
        self.log("开始执行回测...")

        initial_capital = config.get('initial_capital', 100_000)
        commission_rate = config.get('commission_rate', 0.0003)
        slippage = config.get('slippage', 0.0001)
        position_ratio = config.get('position_ratio', 1.0)
        stop_loss_pct = config.get('stop_loss_pct', 0.0)
        take_profit_pct = config.get('take_profit_pct', 0.0)
        trailing_stop_pct = config.get('trailing_stop_pct', 0.0)

        capital = initial_capital
        position = 0
        buy_price = 0.0          # 买入成交价
        peak_price = 0.0         # 持仓期间最高价（用于移动止损）
        trades = []
        net_value = []

        for date, row in df.iterrows():
            current_price = row['close']
            signal = row.get('signal', 0)
            total_asset = capital + position * current_price

            # 更新持仓期间最高点（移动止损用）
            if position > 0 and current_price > peak_price:
                peak_price = current_price

            # ── 卖出优先判断：止损 / 止盈 / 移动止损（优先级高于信号）──────
            forced_sell = False
            sell_reason = ""
            if position > 0 and buy_price > 0:
                pnl_pct = (current_price - buy_price) / buy_price
                # 固定止损
                if stop_loss_pct > 0 and pnl_pct <= -stop_loss_pct:
                    forced_sell = True
                    sell_reason = "固定止损"
                # 固定止盈
                elif take_profit_pct > 0 and pnl_pct >= take_profit_pct:
                    forced_sell = True
                    sell_reason = "固定止盈"
                # 移动止损
                elif trailing_stop_pct > 0:
                    drawdown_from_peak = (peak_price - current_price) / peak_price
                    if drawdown_from_peak >= trailing_stop_pct:
                        forced_sell = True
                        sell_reason = "移动止损"

            if forced_sell:
                sell_price = current_price * (1 - slippage)
                revenue = position * sell_price * (1 - commission_rate)
                capital += revenue
                pnl_amount = revenue - (position * buy_price * (1 + commission_rate))
                trades.append({
                    'date': date,
                    'type': 'sell',
                    'price': sell_price,
                    'volume': position,
                    'reason': sell_reason,
                    'pnl': pnl_amount,
                    'revenue': revenue,
                })
                self.log(f"⛔ {sell_reason}卖出: {date.date()} 价格{sell_price:.2f} 盈亏{pnl_amount:+.2f}元")
                position = 0
                buy_price = 0.0
                peak_price = 0.0

            # 卖出：信号为-1且持仓（非强制卖出已处理，此处只处理信号触发）
            elif signal == -1 and position > 0:
                sell_price = current_price * (1 - slippage)
                revenue = position * sell_price * (1 - commission_rate)
                capital += revenue
                trades.append({
                    'date': date,
                    'type': 'sell',
                    'price': sell_price,
                    'volume': position,
                    'reason': '信号卖出',
                    'revenue': revenue,
                })
                position = 0
                buy_price = 0.0
                peak_price = 0.0

            # 买入：信号为1且空仓
            elif signal == 1 and position == 0:
                buy_amount = total_asset * position_ratio
                buy_price = current_price * (1 + slippage)
                position = int(buy_amount / buy_price / 100) * 100  # 整手买入
                if position > 0:
                    cost = position * buy_price * (1 + commission_rate)
                    capital -= cost
                    peak_price = buy_price  # 重置最高点为买入价
                    trades.append({
                        'date': date,
                        'type': 'buy',
                        'price': buy_price,
                        'volume': position,
                        'cost': cost,
                    })

            # 记录每日净值
            daily_net = capital + position * current_price
            net_value.append({
                'date': date,
                'net_value': daily_net,
                'position': position,
                'cash': capital,
            })

        # 最终持仓市值
        final_price = df.iloc[-1]['close']
        final_asset = capital + position * final_price

        nv_df = pd.DataFrame(net_value).set_index('date')
        return {
            'initial_capital': initial_capital,
            'final_asset': final_asset,
            'total_return': (final_asset - initial_capital) / initial_capital,
            'trades': trades,
            'net_value_curve': nv_df,
            'final_position': position,
            'final_cash': capital,
        }

    # ------------------------------------------------------------------
    # 绩效指标计算
    # ------------------------------------------------------------------

    def calc_performance_metrics(self, backtest_result: Dict, df: pd.DataFrame) -> Dict:
        """计算完整绩效指标"""
        self.log("计算绩效指标...")

        nv = backtest_result['net_value_curve']['net_value']
        daily_returns = nv.pct_change().dropna()

        # 时间跨度
        days = (nv.index[-1] - nv.index[0]).days

        # 年化收益率
        annual_return = (1 + backtest_result['total_return']) ** (365 / days) - 1

        # 年化波动率
        annual_volatility = daily_returns.std() * np.sqrt(252)

        # 夏普比率（无风险利率2%）
        risk_free_rate = 0.02
        sharpe_ratio = (
            (annual_return - risk_free_rate) / annual_volatility
            if annual_volatility > 0 else 0
        )

        # 最大回撤
        cumulative_max = nv.cummax()
        drawdown = (nv - cumulative_max) / cumulative_max
        max_drawdown = drawdown.min()

        # 最大回撤持续天数
        max_drawdown_duration = self._calc_max_drawdown_duration(cumulative_max, drawdown)

        # 卡尔玛比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 交易统计
        trades = backtest_result['trades']
        buy_trades = [t for t in trades if t['type'] == 'buy']
        sell_trades = [t for t in trades if t['type'] == 'sell']

        profits = []
        # 配对完整的买卖回合
        for i in range(min(len(buy_trades), len(sell_trades))):
            profit = (sell_trades[i]['price'] - buy_trades[i]['price']) * buy_trades[i]['volume']
            profits.append(profit)

        # 若最后有未平仓持仓，以最后一根K线收盘价平仓，计入盈亏
        final_price = df.iloc[-1]['close']
        if backtest_result['final_position'] > 0:
            last_buy = buy_trades[-1]
            pnl = (final_price - last_buy['price']) * last_buy['volume']
            profits.append(pnl)
            self.log(f"📌 期末未平仓 {backtest_result['final_position']} 股，按 {final_price:.2f} 结算，盈亏 {pnl:+.2f} 元")

        win_count = len([p for p in profits if p > 0])
        loss_count = len([p for p in profits if p <= 0])
        win_rate = win_count / len(profits) if profits else 0
        avg_win = np.mean([p for p in profits if p > 0]) if win_count > 0 else 0
        avg_loss = abs(np.mean([p for p in profits if p <= 0])) if loss_count > 0 else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # 基准收益（买入持有）
        benchmark_return = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close']
        benchmark_annual = (1 + benchmark_return) ** (365 / days) - 1
        excess_return = annual_return - benchmark_annual

        return {
            'total_return': backtest_result['total_return'],
            'annual_return': annual_return,
            'annual_volatility': annual_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_drawdown_duration,
            'calmar_ratio': calmar_ratio,
            'total_trades': len(trades),
            'round_trips': len(profits),
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_win_profit': avg_win,
            'avg_loss': avg_loss,
            'benchmark_return': benchmark_return,
            'benchmark_annual_return': benchmark_annual,
            'excess_return': excess_return,
            'daily_returns': daily_returns,
        }

    @staticmethod
    def _calc_max_drawdown_duration(
        cumulative_max: pd.Series,
        drawdown: pd.Series,
    ) -> int:
        """计算最大回撤持续天数（从阶段峰值到谷底的天数）"""
        max_dd_idx = drawdown.idxmin()
        if pd.notna(max_dd_idx):
            dd_value = cumulative_max.loc[max_dd_idx]
            peak_idx = None
            for i, idx in enumerate(cumulative_max.index):
                if idx >= max_dd_idx:
                    break
                if i > 0:
                    prev_val = cumulative_max.iloc[i - 1]
                    curr_val = cumulative_max.iloc[i]
                    if prev_val < dd_value <= curr_val:
                        peak_idx = idx
                        break
            if peak_idx is None:
                peak_idx = cumulative_max.idxmax()
            return int(max(0, (max_dd_idx - peak_idx).days))
        return 0

    # ------------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------------

    def execute(self, state: dict) -> dict:
        df = state['data']
        config = state['task_config']

        backtest_result = self.run_backtest(df, config)
        metrics = self.calc_performance_metrics(backtest_result, df)
        backtest_result['metrics'] = metrics

        state['backtest_result'] = backtest_result
        self.log(
            f"回测完成，总收益: {backtest_result['total_return']:.2%}, "
            f"年化收益: {metrics['annual_return']:.2%}, "
            f"夏普比率: {metrics['sharpe_ratio']:.2f}, "
            f"最大回撤: {metrics['max_drawdown']:.2%}, "
            f"胜率: {metrics['win_rate']:.2%}"
        )
        return state
