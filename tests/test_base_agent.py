"""
测试 agents/base_agent.py —— Agent 基类
"""
import pytest
from agents.base_agent import BaseAgent


class TestBaseAgent:
    """测试基类的初始化、日志方法和 execute 接口"""

    def test_init_sets_name_and_log(self):
        agent = BaseAgent("TestAgent")
        assert agent.name == "TestAgent"
        assert agent.execution_log == []

    def test_execute_raises_not_implemented(self):
        agent = BaseAgent("Stub")
        with pytest.raises(NotImplementedError, match="execute"):
            agent.execute({})

    def test_log_appends_entry(self):
        agent = BaseAgent("Demo")
        agent.log("hello world")
        assert len(agent.execution_log) == 1
        assert "Demo" in agent.execution_log[0]
        assert "hello world" in agent.execution_log[0]

    def test_log_format_structure(self):
        agent = BaseAgent("MyAgent")
        entry = agent.log("test message")
        # 格式：[YYYY-MM-DD HH:MM:SS] [MyAgent] test message
        assert entry.startswith("[20")
        assert "[MyAgent]" in entry
        assert "test message" in entry
