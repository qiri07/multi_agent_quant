"""
项目常量：路径、配置默认值等
"""
from pathlib import Path

# 指向 trade-krono-cli 项目根目录
# agents/data_provider.py → parent = agents/ → parent = project_root → Work/ → trade-krono-cli
_KRONO_BASE = Path(__file__).resolve().parent.parent.parent / "trade-krono-cli"
KLINE_CACHE_DB = _KRONO_BASE / "outputs" / "cache" / "pipeline_cache.db"
