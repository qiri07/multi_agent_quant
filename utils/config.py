"""
配置常量模块
集中管理各 Agent 的默认参数和配置项
"""

# 回测默认参数
DEFAULT_INITIAL_CAPITAL = 100000
DEFAULT_COMMISSION_RATE = 0.0003       # 手续费率万三
DEFAULT_SLIPPAGE = 0.0001              # 滑点万分之一
DEFAULT_POSITION_RATIO = 1.0           # 仓位比例（全仓）
DEFAULT_VOTE_THRESHOLD = 2             # 默认投票阈值
DEFAULT_RISK_FREE_RATE = 0.02          # 无风险利率 2%

# 风控参数（默认关闭，设为 >0 时启用）
DEFAULT_STOP_LOSS_PCT = 0.00           # 固定止损百分比（0=不启用）
DEFAULT_TAKE_PROFIT_PCT = 0.00         # 固定止盈百分比（0=不启用）
DEFAULT_TRAILING_STOP_PCT = 0.05       # 移动止损回撤比例（5%=从最高点回撤5%止损）

# 趋势过滤参数
DEFAULT_TREND_FILTER = True            # 是否启用大盘趋势过滤
DEFAULT_TREND_MA_WINDOW = 60           # 趋势均线周期（60日）

# 数据生成默认参数
DEFAULT_SYMBOL = "000001.SZ"
DEFAULT_START_DATE = "2023-01-01"
DEFAULT_END_DATE = "2026-09-30"

# OrchestratorAgent 参数
MAX_RETRIES = 1                        # 单节点最大重试次数
FACTORIZER_MAX_WORKERS = 4             # 因子计算并行线程数

# 报告保存路径
REPORT_FILENAME = "回测报告.md"

# 飞书机器人 Webhook
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/99c2539b-d5b5-42ff-99cd-ce2738b057e8"
