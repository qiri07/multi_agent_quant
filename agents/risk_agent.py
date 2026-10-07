"""
RiskAgent - 风控校验与报告生成模块
职责：风险指标评估、策略诊断、Markdown报告生成与保存
"""
from typing import Dict, List

from agents.base_agent import BaseAgent
from utils.config import REPORT_FILENAME
from utils.feishu import send_report_notification


class RiskAgent(BaseAgent):
    """
    风控与报告Agent
    职责：风险指标校验、策略风险诊断、生成最终回测报告、给出优化建议
    """

    def __init__(self):
        super().__init__("风控报告Agent")

    # ------------------------------------------------------------------
    # 风险评估
    # ------------------------------------------------------------------

    def risk_assessment(self, metrics: Dict) -> Dict:
        """多维度风险评估，返回风险等级与警告列表"""
        self.log("进行风险评估...")

        risk_warnings: List[str] = []
        risk_level = "低"
        priority = {"低": 0, "中": 1, "高": 2}

        def _update_level(new: str):
            nonlocal risk_level
            if priority.get(new, 0) > priority.get(risk_level, 0):
                risk_level = new

        # 最大回撤
        if metrics['max_drawdown'] < -0.2:
            risk_warnings.append("⚠️ 最大回撤超过20%，策略风险较高，建议优化止损机制")
            _update_level("高")
        elif metrics['max_drawdown'] < -0.1:
            risk_warnings.append("⚠️ 最大回撤超过10%，建议关注回撤控制")
            _update_level("中")

        # 夏普比率
        if metrics['sharpe_ratio'] < 0.5:
            risk_warnings.append("⚠️ 夏普比率低于0.5，策略性价比很低")
            _update_level("高")
        elif metrics['sharpe_ratio'] < 1:
            risk_warnings.append("⚠️ 夏普比率低于1，风险调整后收益一般")
            _update_level("中")

        # 胜率
        if metrics['win_rate'] < 0.4:
            risk_warnings.append("⚠️ 胜率低于40%，信号质量较差")
            _update_level("中")

        # 交易频率
        if metrics['total_trades'] > len(metrics['daily_returns']) * 0.1:
            risk_warnings.append("⚠️ 交易过于频繁，手续费损耗较大")

        # 超额收益
        if metrics['excess_return'] < 0:
            risk_warnings.append("⚠️ 策略未跑赢买入持有基准，需优化择时能力")

        if not risk_warnings:
            risk_warnings.append("✅ 各项风险指标正常")

        return {
            'risk_level': risk_level,
            'risk_warnings': risk_warnings,
            'pass_risk_check': risk_level != "高",
        }

    # ------------------------------------------------------------------
    # 优化建议
    # ------------------------------------------------------------------

    @staticmethod
    def generate_optimization_suggestions(metrics: Dict,
                                          risk_assessment: Dict) -> List[str]:
        """根据绩效指标生成针对性优化建议"""
        suggestions = []

        if metrics['max_drawdown'] < -0.15:
            suggestions.append(
                "建议增加移动止损或固定止损条件，控制单笔亏损幅度"
            )
        if metrics['win_rate'] < 0.5:
            suggestions.append(
                "建议优化信号过滤条件，增加趋势过滤（如大盘环境判断），减少假信号"
            )
        if metrics['profit_loss_ratio'] < 1.5:
            suggestions.append(
                "建议优化止盈逻辑，让盈利充分奔跑，提升盈亏比"
            )
        if metrics['total_trades'] > 100:
            suggestions.append(
                "建议提高信号确认阈值，减少无效交易，降低手续费损耗"
            )
        if metrics['sharpe_ratio'] < 1:
            suggestions.append(
                "建议引入更多低相关性因子进行融合，平滑收益曲线"
            )
        if not suggestions:
            suggestions.append(
                "策略表现良好，可考虑进行样本外测试和参数敏感性分析"
            )
        return suggestions

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------

    def generate_report(self, state: Dict) -> str:
        """生成 Markdown 格式回测报告"""
        config = state['task_config']
        bt = state['backtest_result']
        metrics = bt['metrics']
        risk = state['risk_report']['risk_assessment']
        suggestions = state['risk_report']['suggestions']

        warnings_block = "\n".join(f"  - {w}" for w in risk['risk_warnings'])
        suggestions_block = "\n".join(
            f"{i}. {s}" for i, s in enumerate(suggestions, 1)
        )

        return f"""\
# 📊 多Agent量化策略回测报告
---

## 基本信息
| 参数 | 值 |
|------|-----|
| 标的代码 | {config.get('symbol', 'DEMO')} |
| 回测区间 | {config.get('start_date')} 至 {config.get('end_date')} |
| 初始资金 | {bt['initial_capital']:,.2f} 元 |
| 最终资产 | {bt['final_asset']:,.2f} 元 |
| 策略模式 | 多因子融合策略（双均线+RSI+MACD+布林带） |
| 投票阈值 | {config.get('vote_threshold', 2)}个策略一致 |

---

## 核心绩效指标
| 指标 | 策略值 | 基准（买入持有） |
|------|--------|------------------|
| 总收益率 | {metrics['total_return']:.2%} | {metrics['benchmark_return']:.2%} |
| 年化收益率 | {metrics['annual_return']:.2%} | {metrics['benchmark_annual_return']:.2%} |
| 年化波动率 | {metrics['annual_volatility']:.2%} | - |
| 夏普比率 | {metrics['sharpe_ratio']:.2f} | - |
| 最大回撤 | {metrics['max_drawdown']:.2%} | - |
| 最大回撤持续天数 | {metrics['max_drawdown_duration']} 天 | - |
| 卡尔玛比率 | {metrics['calmar_ratio']:.2f} | - |
| 超额收益 | {metrics['excess_return']:.2%} | - |

---

## 交易统计
| 指标 | 值 |
|------|-----|
| 总交易次数 | {metrics['total_trades']}次 |
| 完整交易轮次 | {metrics['round_trips']}次 |
| 胜率 | {metrics['win_rate']:.2%} |
| 盈亏比 | {metrics['profit_loss_ratio']:.2f} |
| 平均盈利 | {metrics['avg_win_profit']:,.2f} 元 |
| 平均亏损 | {metrics['avg_loss']:,.2f} 元 |

---

## 风险评估
- **风险等级**: {risk['risk_level']}
- **风险提示**:
{warnings_block}

---

## 优化建议
{suggestions_block}

---

## 流水线执行信息
- 执行耗时: {state['duration']:.2f}秒
- 计算因子数: {len(state['factors'])}个
- 买入信号: {state['signals']['buy_count']}次
- 卖出信号: {state['signals']['sell_count']}次
- 执行状态: ✅ 成功

---
*报告由多Agent量化流水线自动生成，仅供策略研究参考，不构成投资建议*
"""

    # ------------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------------

    def execute(self, state: dict) -> dict:
        metrics = state['backtest_result']['metrics']

        risk_assessment = self.risk_assessment(metrics)
        suggestions = self.generate_optimization_suggestions(metrics, risk_assessment)

        state['risk_report'] = {
            'risk_assessment': risk_assessment,
            'suggestions': suggestions,
        }

        final_report = self.generate_report(state)
        state['final_report'] = final_report

        self.log("风控评估与报告生成完成")

        # 保存报告到文件
        report_path = REPORT_FILENAME
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(final_report)
        self.log(f"报告已保存至: {report_path}")

        # 推送飞书通知（批量筛选时跳过单票推送，避免触发限流）
        if not state.get("task_config", {}).get("_skip_feishu_push"):
            try:
                config = state.get("task_config", {})
                send_report_notification(
                    symbol=config.get("symbol", "UNKNOWN"),
                    metrics=metrics,
                    risk_level=risk_assessment["risk_level"],
                    suggestions=suggestions,
                )
            except Exception as e:
                self.log(f"⚠️ 飞书推送异常（已忽略）: {e}")

        return state
