"""
测试 utils/logger.py —— 线程安全日志工具
"""
import threading
from utils.logger import Logger


class TestLogger:
    """测试日志记录功能及线程安全"""

    def test_log_returns_formatted_string(self):
        log = []
        entry = Logger.log("TestAgent", "hello", log)
        assert "[TestAgent]" in entry
        assert "hello" in entry
        assert entry in log

    def test_log_appends_to_list(self):
        log = []
        Logger.log("A", "msg1", log)
        Logger.log("A", "msg2", log)
        assert len(log) == 2
        assert "msg1" in log[0]
        assert "msg2" in log[1]

    def test_thread_safety(self):
        """多线程并发写入，验证无异常且条目数正确"""
        log = []
        threads = []
        for i in range(50):
            t = threading.Thread(target=Logger.log, args=("Thread", f"msg-{i}", log))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        assert len(log) == 50

    def test_log_with_empty_message(self):
        log = []
        entry = Logger.log("Agent", "", log)
        assert "Agent" in entry
        assert len(log) == 1
