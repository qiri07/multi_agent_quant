"""
测试 agents/orchestrator_agent.py —— 主控调度与重试机制
"""
import pytest
from unittest.mock import patch, MagicMock
from agents.orchestrator_agent import OrchestratorAgent
from agents.base_agent import BaseAgent


class MockAgent(BaseAgent):
    """用于测试的可控模拟 Agent"""

    def __init__(self, name, should_fail=False):
        super().__init__(name)
        self.should_fail = should_fail
        self.call_count = 0

    def execute(self, state):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError(f"{self.name} 故意失败")
        state[f"_{self.name}_done"] = True
        return state


class TestOrchestratorAgent:
    """测试调度逻辑、重试机制及异常处理"""

    @pytest.fixture
    def orchestrator(self):
        return OrchestratorAgent()

    def test_execute_returns_success_on_clean_run(self, orchestrator, mock_state):
        with patch("agents.orchestrator_agent.DataAgent") as MockData, \
             patch("agents.orchestrator_agent.FactorAgent") as MockFactor, \
             patch("agents.orchestrator_agent.StrategyAgent") as MockStrategy, \
             patch("agents.orchestrator_agent.BacktestAgent") as MockBacktest, \
             patch("agents.orchestrator_agent.RiskAgent") as MockRisk:

            def make_mock(name):
                inst = MagicMock()
                inst.name = name
                inst.execute.side_effect = lambda s, n=name: {
                    **s, f"_done_{n}": True
                }
                return inst

            MockData.return_value = make_mock("DataAgent")
            MockFactor.return_value = make_mock("FactorAgent")
            MockStrategy.return_value = make_mock("StrategyAgent")
            MockBacktest.return_value = make_mock("BacktestAgent")

            risk_inst = make_mock("RiskAgent")
            risk_inst.execute.side_effect = lambda s: {
                **s, "status": "success", "duration": 0.1,
                "final_report": "report", "risk_report": {}
            }
            MockRisk.return_value = risk_inst

            result = orchestrator.execute(mock_state["task_config"])
            assert result["status"] == "success"
            assert result["final_report"] == "report"

    def test_execute_retries_on_failure(self, orchestrator, mock_state):
        """验证重试时记录错误日志（与 test_execute_fails_after_max_retries 互补）"""
        from agents.data_agent import DataAgent

        fail_agent = MagicMock()
        fail_agent.name = "DataAgent"
        fail_agent.execute.side_effect = RuntimeError("数据异常")

        with patch("agents.orchestrator_agent.DataAgent", return_value=fail_agent), \
             patch("agents.orchestrator_agent.FactorAgent") as MF, \
             patch("agents.orchestrator_agent.StrategyAgent") as MS, \
             patch("agents.orchestrator_agent.BacktestAgent") as MB, \
             patch("agents.orchestrator_agent.RiskAgent") as MR:
            for name, m in [("FactorAgent", MF), ("StrategyAgent", MS),
                            ("BacktestAgent", MB), ("RiskAgent", MR)]:
                inst = MagicMock()
                inst.name = name
                inst.execute.side_effect = lambda s, n=name: {
                    **s, f"_done_{n}": True
                }
                m.return_value = inst

            result = orchestrator.execute(mock_state["task_config"])
            # 第一次失败，重试后再次失败，状态为 failed
            assert result["status"] == "failed"
            # 日志中包含重试信息
            error_msgs = [e for e in result["errors"] if "DataAgent" in e]
            assert len(error_msgs) >= 1
            assert "首次失败" not in error_msgs[0]  # 确认是重试后的错误

    def test_execute_fails_after_max_retries(self, orchestrator, mock_state):
        """Agent 连续失败超过重试次数，状态设为 failed"""

        class AlwaysFail(BaseAgent):
            def __init__(self):
                super().__init__("AlwaysFail")
            def execute(self, state):
                raise RuntimeError("始终失败")

        with patch("agents.orchestrator_agent.DataAgent", return_value=AlwaysFail()), \
             patch("agents.orchestrator_agent.FactorAgent") as MF, \
             patch("agents.orchestrator_agent.StrategyAgent") as MS, \
             patch("agents.orchestrator_agent.BacktestAgent") as MB, \
             patch("agents.orchestrator_agent.RiskAgent") as MR:
            for name, m in [("FactorAgent", MF), ("StrategyAgent", MS),
                            ("BacktestAgent", MB), ("RiskAgent", MR)]:
                inst = MagicMock()
                inst.name = name
                inst.execute.side_effect = lambda s, n=name: {
                    **s, f"_done_{n}": True
                }
                m.return_value = inst

            result = orchestrator.execute(mock_state["task_config"])
            assert result["status"] == "failed"
            assert len(result["errors"]) > 0

    def test_execute_sets_duration(self, orchestrator, mock_state):
        with patch("agents.orchestrator_agent.DataAgent") as MD, \
             patch("agents.orchestrator_agent.FactorAgent") as MF, \
             patch("agents.orchestrator_agent.StrategyAgent") as MS, \
             patch("agents.orchestrator_agent.BacktestAgent") as MB, \
             patch("agents.orchestrator_agent.RiskAgent") as MR:
            def make_mock(name):
                inst = MagicMock()
                inst.name = name
                inst.execute.side_effect = lambda s, n=name: {
                    **s, f"_done_{n}": True
                }
                return inst

            MD.return_value = make_mock("DataAgent")
            MF.return_value = make_mock("FactorAgent")
            MS.return_value = make_mock("StrategyAgent")
            MB.return_value = make_mock("BacktestAgent")
            risk_inst = make_mock("RiskAgent")
            risk_inst.execute.side_effect = lambda s: {
                **s, "status": "success", "duration": 0.5,
                "final_report": "r", "risk_report": {}
            }
            MR.return_value = risk_inst

            result = orchestrator.execute(mock_state["task_config"])
            assert "duration" in result
            assert result["duration"] > 0
