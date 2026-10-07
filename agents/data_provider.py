"""
DataProvider - 从 trade-krono-cli pipeline_cache.db 读取真实 K 线数据。
"""
from __future__ import annotations

import pickle
import sqlite3
from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger

from utils.constants import KLINE_CACHE_DB


def _normalize_ticker(ticker: str) -> str:
    """统一 ticker 格式：支持 000001.SZ / sz.000001 / 600519.SH / sh.600519 等写法。

    返回 database 中的标准格式（如 sz.000001 / sh.600519）。
    """
    t = ticker.strip().lower()
    if "." in t:
        code, exchange = t.split(".", 1)
        exchange = exchange.lower()
        if exchange in ("sz", "sh", "bj"):
            return f"{exchange}.{code}"
        # 兼容 .SZ / .SH 后缀
        if exchange == "sz":
            return f"sz.{code}"
        if exchange == "sh":
            return f"sh.{code}"
        if exchange == "bj":
            return f"bj.{code}"
    # 无前缀：根据代码段判断
    if t.startswith(("0", "3")):
        return f"sz.{t}"
    if t.startswith("6"):
        return f"sh.{t}"
    if t.startswith("8") or t.startswith("4"):
        return f"bj.{t}"
    return t  # 未知格式，原样返回


def fetch_kline_from_cache(
    ticker: str,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """从 pipeline_cache.db 加载指定股票的历史 K 线。

    Args:
        ticker:       股票代码（支持多种格式，如 000001.SZ / sz.000001）
        start_date:   开始日期，格式 YYYY-MM-DD
        end_date:     结束日期，格式 YYYY-MM-DD

    Returns:
        DataFrame（index=Timestamp，columns=open/high/low/close/volume），
        若未找到则返回 None。
    """
    if not KLINE_CACHE_DB.exists():
        logger.warning(f"K 线缓存数据库不存在: {KLINE_CACHE_DB}")
        return None

    norm = _normalize_ticker(ticker)
    conn = sqlite3.connect(str(KLINE_CACHE_DB))
    try:
        cur = conn.execute(
            "SELECT data FROM kline_cache WHERE ticker = ? LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row is None:
            logger.warning(f"未找到 ticker 数据: {norm}（可用 {ticker}）")
            return None

        df: pd.DataFrame = pickle.loads(row[0])

        # ── 列名标准化 ──────────────────────────────────────────────
        # timestamps 统一设为 index
        if "timestamps" in df.columns:
            df.index = pd.to_datetime(df["timestamps"])
            df.drop(columns=["timestamps"], inplace=True)
        elif df.index.name is None:
            df.index = pd.to_datetime(df.index)

        # 统一使用标准列名
        col_map = {}
        for c in df.columns:
            cl = c.lower().strip()
            if cl in ("open", "high", "low", "close", "volume", "amount"):
                col_map[c] = cl
        if col_map:
            df.rename(columns=col_map, inplace=True)

        # ── 日期范围过滤 ──────────────────────────────────────────────
        start = pd.Timestamp(start_date)
        end   = pd.Timestamp(end_date)
        mask = (df.index >= start) & (df.index <= end)
        df = df.loc[mask].copy()

        if df.empty:
            logger.warning(f"日期范围内无数据: {norm} {start_date} ~ {end_date}")
            return pd.DataFrame()  # 返回空 DataFrame 而非 None，区分"无ticker"和"无数据"

        # ── 基础清洗 ──────────────────────────────────────────────────
        # 1) 清除零成交量的异常日（无论价格是否异常，volume=0 本身就是数据错误标志）
        if "volume" in df.columns:
            df.loc[df["volume"] == 0, ["open", "high", "low", "close"]] = pd.NA

        # 2) 清除单日涨跌幅超过50%的异常价格（数据源错误）
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                pct = df[col].pct_change().abs()
                df.loc[pct > 0.50, col] = pd.NA

        # 3) 填充缺失值：先前向填充，再后向填充兜底
        df = df.ffill().bfill()

        logger.info(
            f"📥 K 线加载完成: {norm}  共 {len(df)} 条  "
            f"{df.index[0].date()} ~ {df.index[-1].date()}"
        )
        return df
    finally:
        conn.close()
