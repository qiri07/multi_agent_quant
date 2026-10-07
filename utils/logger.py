"""
线程安全的日志工具模块
提供全局日志锁，防止多线程并发调用时日志交错
"""
import threading
from datetime import datetime


# 全局日志锁，所有 Agent 共享
_log_lock = threading.Lock()


class Logger:
    """线程安全日志工具"""

    @staticmethod
    def log(agent_name: str, message: str, execution_log: list) -> str:
        """记录日志（线程安全），返回日志条目字符串

        Args:
            agent_name: Agent 名称
            message: 日志消息
            execution_log: Agent 的日志列表（就地追加）

        Returns:
            格式化后的日志条目字符串
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{agent_name}] {message}"
        with _log_lock:
            execution_log.append(log_entry)
            print(log_entry)
        return log_entry
