"""
ScreeningAgent - 多股票批量筛选模块
职责：遍历可用股票池，对每只股票执行完整量化流水线，汇总并排序结果
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from agents.base_agent import BaseAgent
from utils.constants import KLINE_CACHE_DB
from utils.config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE,
    DEFAULT_POSITION_RATIO,
    DEFAULT_VOTE_THRESHOLD,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    DEFAULT_TRAILING_STOP_PCT,
)

# 保留 _DB_PATH 供 get_available_tickers 使用（兼容旧代码）
_DB_PATH = KLINE_CACHE_DB


class ScreeningAgent(BaseAgent):
    """
    批量筛选Agent
    职责：遍历股票池，串行执行单票流水线，汇总排名输出
    """

    def __init__(self):
        super().__init__("批量筛选Agent")

    # ------------------------------------------------------------------
    # 股票池管理
    # ------------------------------------------------------------------

    @staticmethod
    def get_available_tickers(
        db_path: Optional[Path] = None,
        exchange_filter: Optional[List[str]] = None,
    ) -> List[str]:
        """从 pipeline_cache.db 获取所有可用 ticker 列表。

        Args:
            db_path:           数据库路径，默认自动定位
            exchange_filter:   交易所过滤（如 ["sh", "sz"]），None 表示全市场
        """
        if db_path is None:
            db_path = _DB_PATH
        if not db_path.exists():
            logger.warning(f"数据库不存在: {db_path}")
            return []

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM kline_cache ORDER BY ticker"
            ).fetchall()
        finally:
            conn.close()

        tickers = [r[0] for r in rows]
        if exchange_filter is not None:
            filt = set(exchange_filter)
            tickers = [t for t in tickers if t.split(".")[0] in filt]

        logger.info(f"股票池共 {len(tickers)} 只，交易所过滤: {exchange_filter or '全部'}")
        return tickers

    # ------------------------------------------------------------------
    # 单票流水线（复用已有 Agent）
    # ------------------------------------------------------------------

    def run_single(self, symbol: str, config: Dict) -> Optional[Dict]:
        """对单只股票执行完整流水线，返回结果字典或 None（失败时）。"""
        try:
            from agents.orchestrator_agent import OrchestratorAgent

            # 将当前股票的 symbol 写入 config，复用 OrchestratorAgent
            task_config = config.copy()
            task_config["symbol"] = symbol
            task_config["_skip_feishu_push"] = True  # 筛选模式跳过单票飞书推送

            orchestrator = OrchestratorAgent()
            state = orchestrator.execute(task_config)

            if state.get("status") != "success" or state.get("backtest_result") is None:
                logger.warning(f"⏭️ 跳过 {symbol}：流水线执行失败")
                return None

            metrics = state["backtest_result"]["metrics"]
            risk = state["risk_report"]["risk_assessment"] if state.get("risk_report") else {"risk_level": "未知", "risk_warnings": []}

            self.log(
                f"✅ {symbol}: 总收益={metrics['total_return']:.2%}  "
                f"年化={metrics['annual_return']:.2%}  夏普={metrics['sharpe_ratio']:.2f}  "
                f"回撤={metrics['max_drawdown']:.2%}  胜率={metrics['win_rate']:.0%}"
            )
            return {
                "symbol": symbol,
                "metrics": metrics,
                "risk_level": risk["risk_level"],
                "risk_warnings": risk["risk_warnings"],
                "trades": state["backtest_result"]["trades"],
                "final_asset": state["backtest_result"]["final_asset"],
            }

        except Exception as e:
            logger.error(f"❌ {symbol} 流水线异常: {e}")
            return None

    # ------------------------------------------------------------------
    # 批量筛选
    # ------------------------------------------------------------------

    def run_screening(
        self,
        symbols: List[str],
        start_date: str = "2023-01-01",
        end_date: str = "2026-09-30",
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        vote_threshold: int = DEFAULT_VOTE_THRESHOLD,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        slippage: float = DEFAULT_SLIPPAGE,
        position_ratio: float = DEFAULT_POSITION_RATIO,
        stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
        take_profit_pct: float = DEFAULT_TAKE_PROFIT_PCT,
        trailing_stop_pct: float = DEFAULT_TRAILING_STOP_PCT,
        sort_by: str = "total_return",
        top_n: Optional[int] = None,
        min_sharpe: Optional[float] = None,
        max_workers: int = 4,
    ) -> pd.DataFrame:
        """
        对指定股票列表执行批量筛选（支持并行）。

        Args:
            symbols:           股票列表
            start_date:        回测起始日期
            end_date:          回测结束日期
            initial_capital:   初始资金
            vote_threshold:    投票阈值
            commission_rate:   手续费率
            slippage:          滑点率
            position_ratio:    仓位比例
            stop_loss_pct:     固定止损比例
            take_profit_pct:   固定止盈比例
            trailing_stop_pct: 移动止损比例
            sort_by:           排序字段（total_return / sharpe_ratio / annual_return / max_drawdown）
            top_n:             仅返回前N只，None 表示全部
            min_sharpe:        最小夏普比率过滤，None 表示不过滤
            max_workers:       并行线程数，默认 4

        Returns:
            排序后的结果 DataFrame
        """
        task_config = {
            "symbol": "",
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
        }

        results: List[Dict] = []
        total = len(symbols)
        self.log(f"📊 开始批量筛选，共 {total} 只股票，并行度: {max_workers}")

        # 并行执行单票流水线
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(self.run_single, symbol, task_config): symbol
                for symbol in symbols
            }
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                except Exception as e:
                    logger.error(f"❌ {symbol} 并行执行异常: {e}")
                    continue
                if result is not None:
                    results.append(result)
                    logger.info(
                        f"✅ {symbol}: 总收益={result['metrics']['total_return']:.2%}  "
                        f"夏普={result['metrics']['sharpe_ratio']:.2f}  "
                        f"回撤={result['metrics']['max_drawdown']:.2%}"
                    )
                else:
                    logger.warning(f"⏭️ 跳过 {symbol}：流水线执行失败")

        if not results:
            logger.warning("所有股票均筛选失败")
            return pd.DataFrame()

        # 构建结果 DataFrame
        rows = []
        for r in results:
            m = r["metrics"]
            rows.append({
                "symbol": r["symbol"],
                "total_return": m["total_return"],
                "annual_return": m["annual_return"],
                "annual_volatility": m["annual_volatility"],
                "sharpe_ratio": m["sharpe_ratio"],
                "max_drawdown": m["max_drawdown"],
                "calmar_ratio": m["calmar_ratio"],
                "win_rate": m["win_rate"],
                "profit_loss_ratio": m["profit_loss_ratio"],
                "total_trades": m["total_trades"],
                "round_trips": m["round_trips"],
                "benchmark_return": m["benchmark_return"],
                "excess_return": m["excess_return"],
                "risk_level": r["risk_level"],
                "final_asset": r["final_asset"],
            })

        df_result = pd.DataFrame(rows)

        # 过滤
        if min_sharpe is not None:
            df_result = df_result[df_result["sharpe_ratio"] >= min_sharpe]

        # 所有指标均为"越大越好"，统一降序排列
        df_result = df_result.sort_values(sort_by, ascending=False).reset_index(drop=True)

        # 取 top N
        if top_n is not None:
            df_result = df_result.head(top_n).reset_index(drop=True)

        self.log(f"筛选完成，有效股票 {len(df_result)} 只，按 {sort_by} 排序")
        return df_result

    # ------------------------------------------------------------------
    # 结果展示
    # ------------------------------------------------------------------

    @staticmethod
    def print_summary(df: pd.DataFrame) -> str:
        """生成 Markdown 格式的筛选结果汇总表。"""
        if df.empty:
            return "暂无筛选结果。"

        lines = [
            "# 📊 多Agent量化筛选结果",
            "",
            f"**有效标的数**: {len(df)} 只",
            "",
            "| # | 代码 | 总收益 | 年化收益 | 夏普 | 最大回撤 | 胜率 | 交易次数 | 风险等级 |",
            "|---|------|--------|---------|------|---------|------|---------|---------|",
        ]
        for idx, row in df.iterrows():
            lines.append(
                f"| {idx + 1} | {row['symbol']} | "
                f"{row['total_return']:.2%} | "
                f"{row['annual_return']:.2%} | "
                f"{row['sharpe_ratio']:.2f} | "
                f"{row['max_drawdown']:.2%} | "
                f"{row['win_rate']:.0%} | "
                f"{int(row['total_trades'])} | "
                f"{row['risk_level']} |"
            )

        return "\n".join(lines)

    @staticmethod
    def save_results(df: pd.DataFrame, output_path: str = "筛选结果.md") -> None:
        """将筛选结果保存为 Markdown 文件。"""
        content = ScreeningAgent.print_summary(df)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"筛选结果已保存至: {output_path}")

    # ------------------------------------------------------------------
    # 飞书聚合推送
    # ------------------------------------------------------------------

    def push_screening_summary(self, df: pd.DataFrame, top_n: int = 20) -> None:
        """将筛选结果摘要推送到飞书。"""
        from utils.feishu import _send_feishu_webhook

        rows = df.head(top_n)
        lines = [
            f"**筛选标的数**: {len(df)} 只",
            "",
            f"**Top {top_n} 推荐**:",
        ]
        for idx, row in rows.iterrows():
            lines.append(
                f"{idx + 1}. {row['symbol']}  "
                f"收益{row['total_return']:.1%}  "
                f"夏普{row['sharpe_ratio']:.2f}  "
                f"回撤{row['max_drawdown']:.1%}"
            )

        text = "\n".join(lines)
        _send_feishu_webhook(text, title="📊 多股票量化筛选结果")

    # ------------------------------------------------------------------
    # 执行入口（供 Orchestrator 调用）
    # ------------------------------------------------------------------

    def execute(self, state: dict) -> dict:
        """批量筛选执行入口。"""
        screening_config = state.get("screening_config", {})
        symbols = screening_config.get("symbols", [])
        if not symbols:
            logger.warning("未提供待筛选股票列表")
            state["screening_result"] = pd.DataFrame()
            return state

        result_df = self.run_screening(symbols, **screening_config)
        state["screening_result"] = result_df
        self.log(f"批量筛选完成，有效结果 {len(result_df)} 只")
        return state
