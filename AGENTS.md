# AGENTS.md — multi_agent_quant 项目宪法

> AI 编程助理会话开始时自动加载。所有生成/修改的代码必须遵守本文件。

## 项目概览
- **用途**：A 股量化策略回测 + 批量筛选流水线，基于真实 K 线缓存数据（trade-krono-cli pipeline_cache.db）
- **语言**：Python 3.10+
- **包管理**：`uv`（禁止 `pip` / `poetry` / `virtualenv`）
- **测试**：pytest（全绿门槛）
- **数据存储**：SQLite 缓存（`../trade-krono-cli/outputs/cache/pipeline_cache.db`）

## 命令（Commands）
```bash
uv sync                          # 安装全部依赖（含 dev）
uv add <pkg>                     # 添加运行时依赖
uv add --dev <pkg>               # 添加开发依赖
uv run python main.py            # 单票回测（默认 000001.SZ）
uv run python main.py screen     # 全量批量筛选（沪深 A 股 Top 20）
uv run ruff check .              # Lint 检查
uv run ruff check --fix .        # Lint + 自动修复
uv run mypy .                    # 类型检查
uv run pytest                    # 跑全部测试
uv run pytest -x                 # 首个失败即停
```
提交前必须全绿：`uv run ruff check . && uv run mypy . && uv run pytest`

## 项目结构
```
multi_agent_quant/
├── main.py                 # 入口模块（run_quant_pipeline / run_screening）
├── pyproject.toml          # 项目配置（uv + pytest）
├── AGENTS.md               # 本文件
├── agents/
│   ├── base_agent.py       # Agent 基类（统一接口：execute + log）
│   ├── orchestrator_agent.py  # 主控调度 Agent（监督者模式）
│   ├── data_agent.py       # 数据获取 Agent（从 pipeline_cache.db 读取）
│   ├── data_provider.py    # 数据源层（K 线加载 + 清洗 + ticker 规范化）
│   ├── factor_agent.py     # 多因子计算 Agent（均线/动量/波动率/量价/CCI/KDJ/ADX）
│   ├── strategy_agent.py   # 信号生成 Agent（多策略投票融合 + 趋势过滤）
│   ├── backtest_agent.py   # 回测执行 Agent（事件驱动引擎 + 绩效指标）
│   ├── risk_agent.py       # 风控报告 Agent（风险评估 + Markdown 报告）
│   └── screening_agent.py  # 批量筛选 Agent（并行遍历股票池，聚合排名）
├── utils/
│   ├── config.py           # 配置常量（回测默认参数、飞书 Webhook）
│   ├── constants.py        # 路径常量（KLINE_CACHE_DB）
│   ├── feishu.py           # 飞书 Webhook 推送（无签名，direct POST）
│   └── logger.py           # 线程安全日志工具（全局锁）
└── tests/
    ├── conftest.py         # 共享 fixture
    └── test_*.py           # 扁平化测试文件（每个模块对应一个）
outputs/                    # （由 trade-krono-cli 生成，本目录不产出文件）
筛选结果.md                 # 批量筛选结果汇总（Markdown 报告）
回测报告.md                 # 单票回测报告（RiskAgent 生成）
```

### 核心数据流
```
[任务配置（symbol + 日期范围 + 回测参数）]
  → [OrchestratorAgent]（初始化 state 字典，编排流水线）
  → [DataAgent]
       ├─ data_provider.fetch_kline_from_cache()（读取 pipeline_cache.db）
       ├─ 清洗：volume=0 异常日清零、涨跌幅 >50% 异常日清零
       ├─ ffill + bfill 填充缺失值
       └─ clean_data()：补充 pct_chg，处理异常值
  → [FactorAgent]（并行计算 18 个因子：MA/RSI/MACD/布林带/ATR/量比/VWAP）
  → [StrategyAgent]
       ├─ 4 个子策略：双均线交叉 / RSI 超买超卖 / MACD 金叉死叉 / 布林带突破
       ├─ 多数投票融合（默认 threshold=2）
       └─ 趋势过滤（价格 vs MA60，顺势而为）
  → [BacktestAgent]
       ├─ 事件驱动回测：手续费万三 + 滑点万分之一 + 整手交易
       ├─ 风控：固定止损 8% / 固定止盈 15% / 移动止损回撤 5%
       └─ 绩效指标：总收益/年化/夏普/最大回撤/胜率/盈亏比/卡尔玛/超额收益
  → [RiskAgent]
       ├─ 风险评估（回撤/夏普/胜率/交易频率/超额收益 → 低/中/高）
       ├─ 优化建议生成
       ├─ Markdown 报告生成（回测报告.md）
       └─ 飞书推送（单票模式，批量筛选模式跳过）
  → [最终结果 state dict]
```

### 批量筛选数据流
```
[全量 ticker 列表（从 pipeline_cache.db 读取）]
  → [ScreeningAgent.run_screening()]
       ├─ ThreadPoolExecutor(max_workers=4) 并行执行
       ├─ 每只股票复用 OrchestratorAgent（_skip_feishu_push=True）
       └─ 汇总 → 排序（total_return/sharpe_ratio/annual_return/max_drawdown）
  → 输出 Top N DataFrame + 飞书聚合推送 + Markdown 文件保存
```

## 关键规则（Critical Rules）
1. 所有命令前缀 `uv run` —— 禁止裸 `python`/`pytest`
2. 添加依赖只能用 `uv add`，禁止手编辑 `pyproject.toml` 的 dependencies
3. **所有函数签名必须有类型注解**；模块顶部加 `from __future__ import annotations`
4. 使用现代类型语法：`X | None` 而非 `Optional[X]`；`list[str]` 而非 `List[str]`
5. 禁止 `Any`，除非有注释说明原因；禁止 `# type: ignore`
6. 测试一律用 pytest，禁止 `unittest.TestCase`
7. 库代码禁止 `print()`，必须用 `loguru.logger`（`from loguru import logger`）
8. 错误处理：捕获具体异常，禁止 `except Exception: pass`
9. **日志规范**：关键节点 `info`，异常 `error`；禁止输出 API Key/Token
10. **密钥安全**：飞书 Webhook URL 在 `utils/config.py` 统一管理，禁止硬编码到其他文件
11. **测试隔离**：禁止直接读写生产数据库路径；测试中使用 mock 替代真实网络/文件 IO
12. **公共函数/类必须有 Google 风格 docstring**

## 数据源说明

本项目的 K 线数据来源于 **trade-krono-cli** 项目的 `pipeline_cache.db`（SQLite）。
路径常量定义在 `utils/constants.py` 的 `KLINE_CACHE_DB`。

### 数据库结构
- 表：`kline_cache`，列：`ticker`（TEXT）、`data`（BLOB，pickle 序列化 DataFrame）
- DataFrame 列：`open`/`high`/`low`/`close`/`volume`/`timestamps`（或 index 为时间戳）
- ticker 格式：`sz.000001` / `sh.600519` / `bj.8xxxxx`

### 数据清洗规则（`data_provider.py` 中强制执行）
1. **零成交量异常日**：`volume == 0` 时，将 OHLC 全部置为 NaN（历史已知问题：重复索引覆盖导致错误价格）
2. **单日涨跌幅超过 50%**：视为数据源错误，将异常价格置为 NaN
3. **缺失值填充**：先 `ffill()` 再 `bfill()` 兜底

> ⚠️ 严禁绕过上述清洗直接读取原始数据，此前 sz.000659 虚假 1314% 收益即因违反此规则导致。

## 策略引擎说明

### 因子体系（30 个因子）
| 类别 | 因子 |
|------|------|
| 均线 | MA5, MA10, MA20, MA60, MA_bull |
| 动量 | RSI(14), MACD_DIF, MACD_DEA, MACD_HIST, momentum_5d/10d/20d |
| 波动率 | BOLL_MID/UPPER/LOWER, BOLL_POS, volatility_20d, ATR(14) |
| 量价 | VOL_MA5, VOL_MA10, VOL_RATIO, VWAP |
| CCI | CCI(14) |
| KDJ | KDJ_K, KDJ_D, KDJ_J(9,3,3) |
| ADX | PLUS_DI, MINUS_DI, ADX(14) |

### 投票融合策略
- 默认阈值 `vote_threshold=2`：至少 2 个策略同时发出买入/卖出信号才确认
- 趋势过滤：价格 > MA60 时取消卖出信号，价格 ≤ MA60 时取消买入信号

#### 8 个子策略

| 策略 | 买入条件 | 卖出条件 |
|------|---------|---------|
| 双均线交叉 | MA5 上穿 MA10 | MA5 下穿 MA10 |
| RSI | RSI < 30（超卖） | RSI > 70（超买） |
| MACD | DIF 上穿 DEA | DIF 下穿 DEA |
| 布林带 | 价格 < BOLL_LOWER | 价格 > BOLL_UPPER |
| CCI | CCI 从下方穿越 -100 | CCI 从上方穿越 +100 |
| KDJ | K 上穿 D 且 K < 30（超卖区金叉） | K 下穿 D 且 K > 70（超买区死叉） |
| ADX 趋势 | +DI 上穿 -DI 且 ADX > 20 | -DI 上穿 +DI 且 ADX > 20 |
| 量价背离 | 价格创新低(20日) + 放量(VOL_RATIO>1.5) | 价格创新高(20日) + 缩量(VOL_RATIO<0.5) |

### 回测引擎参数（默认值见 `utils/config.py`）
| 参数 | 默认值 | 说明 |
|------|--------|------|
| initial_capital | 100,000 | 初始资金（元） |
| commission_rate | 0.0003 | 手续费率（万三） |
| slippage | 0.0001 | 滑点率（万分之一） |
| position_ratio | 1.0 | 仓位比例 |
| stop_loss_pct | 0.08 | 固定止损（8%，0=不启用） |
| take_profit_pct | 0.15 | 固定止盈（15%，0=不启用） |
| trailing_stop_pct | 0.05 | 移动止损回撤比例（5%） |

## 飞书推送（Feishu Webhook）

- 位置：`utils/feishu.py`
- 配置：`utils/config.py` 中的 `FEISHU_WEBHOOK_URL`
- 模式：**无签名验证**，直接 POST 到机器人 Webhook
- 触发时机：
  - 单票回测：**默认不推送**，需显式传 `push_feishu=True` 才发送
  - 批量筛选：自动跳过单票推送，仅在完成后推送 Top N 聚合卡片
- 批量筛选模式自动跳过单票推送（`_skip_feishu_push=True`），避免触发限流（code 9499）

## 测试约定（Testing）
- 测试文件：`tests/test_<module>.py`（扁平结构）
- 当前测试数：**136 个**，全绿为合并门槛
- 每个新 Agent 必须有对应测试文件
- 禁止在单元测试中发起真实网络请求或读写生产数据库，必须 mock

## 架构约定（Architecture）
- **分层依赖**（由外向内）：`main.py → agents/orchestrator_agent.py → [data/factor/strategy/backtest/risk/screening_agent] → utils/`
- Agent 之间通过 `state: dict` 传递数据，禁止 Agent 之间直接互相调用
- 数据源抽象：`data_provider.py` 封装所有数据库读写，Agent 不直接访问 SQLite
- 配置集中：`utils/config.py` 管理所有默认参数，`utils/constants.py` 管理路径常量

## 禁止事项（What NOT To Do）
- 禁止 `pip install` / `poetry` / `virtualenv`；禁止手动编辑 `uv.lock`
- 禁止可变默认参数：`def f(x: list = [])` ❌，改用 `None` 哨兵；禁止裸 `except:`
- 禁止在库代码中使用 `print()` 调试
- 禁止在模块顶层直接实例化重型对象（大 DataFrame 等），使用懒加载
- 禁止硬编码数据库路径，必须通过 `utils/constants.py` 的常量引用
- 禁止修改 `data_provider.py` 中的数据清洗逻辑（volume=0 和 >50% 涨跌幅两条规则是数据质量底线）

## 提交与 PR
- 提交前必须跑通：`uv run ruff check . && uv run mypy . && uv run pytest`
- Commit message 遵循 Conventional Commits（`feat:` / `fix:` / `chore:` 等）
- 一次逻辑变更一个 commit；新增依赖必须同 commit 更新 `uv.lock`

## 维护约定
- 本文件是"活文档"：项目结构变化时必须同步更新
- 发现 AI 重复犯同一错误时，把对应禁令加入"禁止事项"
