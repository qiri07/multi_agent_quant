#!/usr/bin/env python3
"""
每日定时筛选入口脚本
由 GitHub Actions cron 触发，执行全量筛选并推送飞书。
可在本地直接运行：python scripts/daily_screening.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import run_screening


def main() -> None:
    try:
        result = run_screening(
            exchange_filter=["sh", "sz"],
            top_n=20,
            sort_by="total_return",
            push_feishu=True,
            save_to_file=True,
        )
        if len(result) == 0:
            print("⚠️ 筛选结果为空，请检查数据源（pipeline_cache.db）是否可用", file=sys.stderr)
            sys.exit(1)
        print(f"✅ 筛选完成，共 {len(result)} 只股票，已推送 Top 20 到飞书")
    except Exception as e:
        print(f"❌ 筛选失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
