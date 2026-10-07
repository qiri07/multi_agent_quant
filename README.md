# 🤖 多Agent量化交易流水线

===============================

## 架构概述

本项目采用业界最成熟的**Pipeline串行流水线+并行因子计算**架构，共6个分工明确的专属Agent协同工作，实现从数据获取到策略回测、风控报告的全流程自动化。

### 👥 Agent角色分工

| Agent名称 | 核心职责 | 设计模式 |
| --- | --- | --- |
| **OrchestratorAgent（主控调度）** | 接收用户任务、拆分调度子任务、异常重试、结果汇总 | 监督者模式（Supervisor） |
| **DataAgent（数据获取）** | 行情数据获取/生成、数据清洗、缺失值处理、标准化、复权 | 专职执行者 |
| **FactorAgent（多因子计算）** | 4大类因子并行计算（均线、动量、波动率、量价），共18+个量化因子 | 并行Map模式 |
| **StrategyAgent（信号生成）** | 4个子策略独立生成信号，多策略投票融合，信号过滤 | 投票融合机制 |
| **BacktestAgent（回测执行）** | 模拟交易执行（含手续费、滑点、整手交易）、净值曲线计算、绩效指标统计 | 事件驱动回测 |
| **RiskAgent（风控报告）** | 风险等级评估、风险点识别、优化建议生成、Markdown报告输出 | 审核者模式 |
| **ScreeningAgent（批量筛选）** | 遍历股票池执行单票流水线，汇总排名输出 | 批处理编排器 |

---

## 📦 目录结构

`多Agent量化流水线/`\
`├── main.py                  # 入口文件，run_quant_pipeline() / run_screening()`\
`├── __init__.py              # 包初始化，导出 run_quant_pipeline`\
`├── README.md                # 使用说明文档`\
`├── 回测报告.md              # 运行后自动生成的回测报告`\
`├── 筛选结果.md              # 批量筛选后自动生成的排名报告`\
`├── agents/                  # Agent 模块目录`\
`│   ├── __init__.py`\
`│   ├── base_agent.py        # BaseAgent 基类，统一输入输出规范`\
`│   ├── orchestrator_agent.py # OrchestratorAgent，主控调度`\
`│   ├── data_agent.py        # DataAgent，数据获取与清洗`\
`│   ├── data_provider.py     # DataProvider，从 trade-krono-cli 缓存读取真实K线`\
`│   ├── factor_agent.py      # FactorAgent，多因子并行计算`\
`│   ├── strategy_agent.py    # StrategyAgent，信号生成与融合`\
`│   ├── backtest_agent.py    # BacktestAgent，回测执行与绩效指标`\
`│   ├── risk_agent.py        # RiskAgent，风控校验与报告生成`\
`│   └── screening_agent.py   # ScreeningAgent，批量筛选与排名`\
`└── utils/                   # 工具模块目录`\
`    ├── __init__.py`\
`    ├── logger.py            # 线程安全日志工具`\
`    ├── config.py            # 配置常量（默认参数、路径等）`\
`    └── feishu.py            # 飞书机器人 Webhook 推送`

---

## 🚀 快速开始

### 环境依赖

仅需numpy和pandas，无需复杂依赖：

`pip install numpy pandas`

### 一键运行

```bash
cd 多Agent量化流水线
python3 -m multi_agent_quant   # 单票回测（默认 000001.SZ）
python3 -m multi_agent_quant screen  # 多票批量筛选
```

### 自定义参数运行（单票）

```python
from multi_agent_quant import run_quant_pipeline

# 自定义参数运行
result = run_quant_pipeline(
    symbol="600519.SH",        # 标的代码
    start_date="2022-01-01",   # 回测开始日期
    end_date="2026-09-30",     # 回测结束日期
    initial_capital=200000,    # 初始资金20万
    vote_threshold=3,          # 信号投票阈值（3个策略同时看多/空才交易）
    commission_rate=0.0003,    # 手续费率（默认万三）
    slippage=0.0001,           # 滑点率（默认万分之一）
    position_ratio=1.0,        # 仓位比例（默认全仓）
    stop_loss_pct=0.08,        # 固定止损 8%
    take_profit_pct=0.15,      # 固定止盈 15%
    trailing_stop_pct=0.05,    # 移动止损（从最高点回撤5%触发）
)

# 打印最终报告
print(result['final_report'])
```

### 批量筛选（多票排名）

```python
from multi_agent_quant import run_screening

# 方式1：指定股票列表
result = run_screening(
    symbols=["sz.000001", "sh.600519", "sz.000858"],
    sort_by="total_return",   # 按总收益排序
    top_n=20,                 # 取前20名
)

# 方式2：从缓存自动加载全部可用股票（沪深 + 北交所）
result = run_screening(
    exchange_filter=["sh", "sz"],  # 只筛选沪深A股
    top_n=50,
    sort_by="sharpe_ratio",        # 按夏普比率排序
    min_sharpe=0.5,                # 夏普>=0.5才入选
)
```

### 筛选结果输出

批量筛选完成后自动生成以下文件：
- `筛选结果.md` — Markdown 格式的排名汇总表
- 飞书群机器人通知（Top 5 推荐股票）
`    slippage=0.0001,           # 滑点率（默认万分之一）`\
`    position_ratio=1.0         # 仓位比例（默认全仓）`\
`)`\
\
`# 打印最终报告`\
`print(result['final_report'])`

---

## 📊 已实现的因子库

FactorAgent采用多线程并行计算，目前支持4大类共**23个量化因子**：

### 1. 均线类因子（5个）

- MA5/MA10/MA20/MA60：不同周期移动平均线
- MA_bull：均线多头排列判断因子

### 2. 动量类因子（7个）

- RSI(14)：相对强弱指标
- MACD_DIF/MACD_DEA/MACD_HIST：MACD指标
- momentum_5d/10d/20d：多周期收益率动量

### 3. 波动率类因子（7个）

- BOLL_MID/BOLL_UPPER/BOLL_LOWER/BOLL_POS：布林带指标及位置
- BOLL_STD：布林带标准差
- volatility_20d：20日年化波动率
- ATR(14)：真实波动幅度均值

### 4. 量价类因子（4个）

- VOL_MA5/VOL_MA10/VOL_RATIO：成交量均线及量比
- VWAP：成交量加权平均价

---

## 🎯 已实现的策略

### 多因子融合策略（多数投票机制）

默认集成4个经典量化策略，采用投票机制融合：

1. **双均线金叉死叉策略**：MA5上穿MA10买入，下穿卖出
2. **RSI超买超卖策略**：RSI&lt;30超卖买入，RSI&gt;70超买卖出
3. **MACD金叉死叉策略**：DIF上穿DEA买入，下穿卖出
4. **布林带突破策略**：价格跌破下轨买入，突破上轨卖出

**投票规则**：默认至少2个策略同时给出买入/卖出信号才执行交易，可通过`vote_threshold`参数调整，阈值越高信号越少但质量越高。

---

## 📈 绩效指标体系

BacktestAgent计算完整的量化绩效指标：

| 指标类别 | 具体指标 |
| --- | --- |
| 收益指标 | 总收益率、年化收益率、基准收益率、超额收益 |
| 风险指标 | 年化波动率、最大回撤、最大回撤持续天数、卡尔玛比率 |
| 风险调整收益 | 夏普比率（无风险利率2%） |
| 交易统计 | 总交易次数、胜率、盈亏比、平均盈利/亏损 |

---

## ⚠️ 风控体系

RiskAgent自动进行多维度风险校验：

- ✅ 最大回撤校验（&gt;20%高风险）
- ✅ 夏普比率校验（&lt;0.5低性价比）
- ✅ 胜率校验（&lt;40%信号质量差）
- ✅ 交易频率校验（过度交易警告）
- ✅ 超额收益校验（是否跑赢基准）
- 🔔 自动生成针对性优化建议

---

## 🔧 扩展指南

### 1. 接入真实行情数据

替换`DataAgent.generate_demo_data()`方法，接入FinScope/Tushare/AkShare API即可获取真实行情：

`# 示例：接入真实数据（需安装对应库）`\
`import akshare as ak`\
`df = ak.stock_zh_a_hist(symbol="000001", period="daily", `\
`                        start_date="20230101", end_date="20260930")`

### 2. 添加自定义因子

在FactorAgent中添加新的因子计算函数，并加入factor_tasks列表即可自动并行计算：

`def calc_my_factor(self, df):`\
`    factors = {}`\
`    factors['我的因子'] = df['close'] / df['MA20']`\
`    return factors`

### 3. 添加自定义策略

在StrategyAgent中添加新的策略信号函数，并加入信号融合列表即可：

`def my_strategy(self, df):`\
`    signal = pd.Series(0, index=df.index)`\
`    # 你的策略逻辑`\
`    return signal`

### 4. 对接实盘交易

在流水线末尾添加ExecutionAgent，对接券商API即可实现自动交易，建议先经过3个月以上模拟盘验证再上实盘。

---

## 🛡️ 工程化特性

1. **异常重试机制**：单个Agent执行失败自动重试1次，避免偶发错误导致流水线崩溃
2. **全链路日志**：每个Agent都有详细执行日志，方便排查问题
3. **可观测性**：所有中间状态都保存在全局state中，可随时查看任意环节输出
4. **可复现性**：固定随机种子，相同参数每次运行结果一致
5. **低依赖**：仅需numpy+pandas即可运行，不需要安装重型量化框架

---

## ⚠️ 免责声明

本项目仅用于量化策略学习和研究，不构成任何投资建议。股市有风险，投资需谨慎。实盘交易前请充分回测验证，自行承担交易风险。