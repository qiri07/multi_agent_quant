"""
BaseAgent 基类
定义所有 Agent 的统一接口规范，子类必须实现 execute() 方法
"""
from typing import Dict, List


class BaseAgent:
    """Agent 基类，定义统一接口规范"""

    def __init__(self, name: str):
        self.name = name
        self.execution_log: List[str] = []

    def log(self, message: str) -> str:
        """记录执行日志（线程安全）

        Args:
            message: 日志消息

        Returns:
            格式化后的日志条目
        """
        from utils.logger import Logger
        return Logger.log(self.name, message, self.execution_log)

    def execute(self, state: Dict) -> Dict:
        """执行 Agent 任务，子类必须实现

        Args:
            state: 全局共享状态字典

        Returns:
            更新后的状态字典
        """
        raise NotImplementedError("子类必须实现 execute 方法")
