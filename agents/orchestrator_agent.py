"""
OrchestratorAgent - 主控调度模块
职责：接收任务、初始化流水线状态、按序调度各Agent、异常重试、汇总结果
"""
import json
from datetime import datetime
from typing import Dict

from agents.base_agent import BaseAgent
from agents.data_agent import DataAgent
from agents.factor_agent import FactorAgent
from agents.strategy_agent import StrategyAgent
from agents.backtest_agent import BacktestAgent
from agents.risk_agent import RiskAgent
from utils.config import MAX_RETRIES


class OrchestratorAgent(BaseAgent):
    """
    主控调度Agent（监督者模式）
    职责：接收用户任务、拆分调度子任务、异常重试、结果汇总
    """

    def __init__(self):
        super().__init__("主控调度Agent")
        self.max_retries = MAX_RETRIES

    def execute(self, task_config: Dict) -> Dict:
        """启动完整量化流水线"""
        self.log(
            f"收到量化任务，开始初始化流水线: "
            f"{json.dumps(task_config, ensure_ascii=False, indent=2)}"
        )

        # 初始化全局共享状态
        state: Dict = {
            "task_config": task_config,
            "start_time": datetime.now(),
            "status": "running",
            "errors": [],
            "data": None,
            "factors": {},
            "signals": None,
            "backtest_result": None,
            "risk_report": None,
            "final_report": None,
        }

        # 按流水线顺序调度各 Agent
        agents = [
            DataAgent(),
            FactorAgent(),
            StrategyAgent(),
            BacktestAgent(),
        ]

        for agent in agents:
            retry_count = 0
            while retry_count <= self.max_retries:
                try:
                    self.log(f"开始调度 {agent.name} 执行...")
                    state = agent.execute(state)
                    self.log(f"{agent.name} 执行完成")
                    break
                except Exception as e:
                    retry_count += 1
                    error_msg = f"{agent.name} 执行失败(第{retry_count}次): {str(e)}"
                    self.log(error_msg)
                    state["errors"].append(error_msg)
                    if retry_count > self.max_retries:
                        state["status"] = "failed"
                        self.log(f"流水线执行失败，错误: {str(e)}")
                        return state

        # 计算执行时长
        state["end_time"] = datetime.now()
        state["duration"] = (
            state["end_time"] - state["start_time"]
        ).total_seconds()

        # 最后执行风控报告
        risk_agent = RiskAgent()
        state = risk_agent.execute(state)

        state["status"] = "success"
        self.log(f"流水线全部执行完成，总耗时: {state['duration']:.2f}秒")
        return state
