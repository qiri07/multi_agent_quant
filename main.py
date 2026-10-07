"""
多Agent量化交易流水线 - 入口模块
================================
采用 Pipeline 串行编排 + 并行因子计算架构，
共 6 个专属 Agent 分工协作：
  1. DataAgent          - 数据获取与清洗
  2. FactorAgent        - 多因子并行计算
  3. StrategyAgent      - 信号生成与融合
  4. BacktestAgent      - 回测执行与绩效指标
  5. RiskAgent          - 风控校验与报告生成
  6. OrchestratorAgent  - 主控调度（监督者模式）
"""
import warnings
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from agents.orchestrator_agent import OrchestratorAgent
from agents.screening_agent import ScreeningAgent

warnings.filterwarnings("ignore")


def run_quant_pipeline(
    symbol: str = "000001.SZ",
    start_date: str = "2023-01-01",
    end_date: str = "2026-09-30",
    initial_capital: float = 100_000,
    vote_threshold: int = 2,
    commission_rate: float = 0.0003,
    slippage: float = 0.0001,
    position_ratio: float = 1.0,
    stop_loss_pct: float = 0.08,
    take_profit_pct: float = 0.15,
    trailing_stop_pct: float = 0.05,
    push_feishu: bool = False,
) -> Dict:
    """
    运行单只股票的量化流水线

    Args:
        symbol:            标的代码
        start_date:        回测开始日期
        end_date:          回测结束日期
        initial_capital:   初始资金
        vote_threshold:    多策略投票阈值
        commission_rate:   手续费率（默认万三）
        slippage:          滑点率（默认万分之一）
        position_ratio:    仓位比例（默认全仓）
        stop_loss_pct:     固定止损比例（默认8%）
        take_profit_pct:   固定止盈比例（默认15%）
        trailing_stop_pct: 移动止损比例（默认5%）
        push_feishu:       是否在回测完成后推送飞书通知（默认关闭）

    Returns:
        包含 final_report、backtest_result、risk_report 等字段的完整结果字典
    """
    task_config = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "commission_rate": commission_rate,
        "slippage": slippage,
        "position_ratio": position_ratio,
        "vote_threshold": vote_threshold,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "trailing_stop_pct": trailing_stop_pct,
        "trend_filter": True,
        "trend_ma_window": 60,
        "_skip_feishu_push": not push_feishu,
    }

    orchestrator = OrchestratorAgent()
    return orchestrator.execute(task_config)


def run_screening(
    symbols: Optional[List[str]] = None,
    start_date: str = "2023-01-01",
    end_date: str = "2026-09-30",
    initial_capital: float = 100_000,
    vote_threshold: int = 2,
    commission_rate: float = 0.0003,
    slippage: float = 0.0001,
    position_ratio: float = 1.0,
    stop_loss_pct: float = 0.08,
    take_profit_pct: float = 0.15,
    trailing_stop_pct: float = 0.05,
    sort_by: str = "total_return",
    top_n: Optional[int] = None,
    min_sharpe: Optional[float] = None,
    exchange_filter: Optional[List[str]] = None,
    save_to_file: bool = True,
    push_feishu: bool = True,
) -> pd.DataFrame:
    """
    批量筛选多只股票，返回排序后的结果 DataFrame。

    Args:
        symbols:         股票代码列表，None 则从缓存自动加载全部可用 ticker
        start_date:      回测起始日期
        end_date:        回测结束日期
        initial_capital: 初始资金
        vote_threshold:  投票阈值
        commission_rate: 手续费率
        slippage:        滑点率
        position_ratio:  仓位比例
        stop_loss_pct:   固定止损比例
        take_profit_pct: 固定止盈比例
        trailing_stop_pct: 移动止损比例
        sort_by:         排序字段（total_return / sharpe_ratio / annual_return / max_drawdown）
        top_n:           仅返回前N只，None 表示全部
        min_sharpe:      最小夏普比率过滤
        exchange_filter: 交易所过滤（如 ["sh", "sz"]）
        save_to_file:    是否保存 Markdown 报告
        push_feishu:     是否推送飞书通知

    Returns:
        排序后的筛选结果 DataFrame
    """
    screening_agent = ScreeningAgent()

    # 确定股票列表
    if symbols is None:
        symbols = screening_agent.get_available_tickers(
            exchange_filter=exchange_filter,
        )
    else:
        # 标准化 ticker 格式
        from agents.data_provider import _normalize_ticker
        symbols = [_normalize_ticker(s) for s in symbols]

    logger.info(f"开始批量筛选，目标股票数: {len(symbols)}")

    screening_config = {
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "vote_threshold": vote_threshold,
        "commission_rate": commission_rate,
        "slippage": slippage,
        "position_ratio": position_ratio,
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "trailing_stop_pct": trailing_stop_pct,
        "sort_by": sort_by,
        "top_n": top_n,
        "min_sharpe": min_sharpe,
    }

    result_df = screening_agent.run_screening(symbols, **screening_config)

    # 输出结果
    if not result_df.empty:
        summary = ScreeningAgent.print_summary(result_df)
        print(summary)

        if save_to_file:
            ScreeningAgent.save_results(result_df)

        if push_feishu:
            screening_agent.push_screening_summary(result_df)
    else:
        print("筛选结果为空，请检查股票列表或数据源。")

    return result_df


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "screen":
        # 批量筛选模式
        print("=" * 60)
        print("📊 多股票量化筛选启动")
        print("=" * 60)

        # 示例：只筛选沪深主板（可选 top_n 限制数量加速）
        result = run_screening(
            exchange_filter=["sh", "sz"],
            top_n=20,
            sort_by="total_return",
        )
    else:
        # 单票回测模式（原有逻辑）
        print("=" * 60)
        print("🚀 多Agent量化交易流水线启动")
        print("=" * 60)

        result = run_quant_pipeline()

        print("\n" + "=" * 60)
        print("✅ 流水线执行完成，最终报告如下：")
        print("=" * 60)
        print(result["final_report"])
