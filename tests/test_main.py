"""
测试 main.py —— 入口模块及 run_quant_pipeline API
"""
import pytest
from unittest.mock import patch, MagicMock
from main import run_quant_pipeline


class TestMain:
    """测试 run_quant_pipeline 的参数透传与返回结构"""

    def test_returns_dict_with_required_keys(self):
        """正常返回应包含 final_report、status 等关键字段"""
        mock_result = {
            "status": "success",
            "final_report": "# Report",
            "backtest_result": {"metrics": {}},
            "risk_report": {},
            "factors": ["MA5"],
            "signals": {"buy_count": 0, "sell_count": 0},
            "duration": 0.1,
        }
        with patch("main.OrchestratorAgent") as MockOrch:
            MockOrch.return_value.execute.return_value = mock_result
            result = run_quant_pipeline()
            assert isinstance(result, dict)
            assert result["status"] == "success"
            assert "final_report" in result

    def test_custom_parameters_passed_through(self):
        """自定义参数应正确传递到 task_config"""
        captured_config = {}

        def capture_execute(task_config):
            captured_config.update(task_config)
            return {
                "status": "success", "final_report": "report",
                "backtest_result": {"metrics": {}}, "risk_report": {},
                "factors": [], "signals": {}, "duration": 0.1,
            }

        with patch("main.OrchestratorAgent") as MockOrch:
            mock_inst = MagicMock()
            mock_inst.execute.side_effect = capture_execute
            MockOrch.return_value = mock_inst

            run_quant_pipeline(
                symbol="600519.SH",
                start_date="2022-01-01",
                end_date="2025-12-31",
                initial_capital=500_000,
                vote_threshold=3,
                commission_rate=0.0005,
                slippage=0.0002,
                position_ratio=0.8,
            )

            assert captured_config["symbol"] == "600519.SH"
            assert captured_config["start_date"] == "2022-01-01"
            assert captured_config["end_date"] == "2025-12-31"
            assert captured_config["initial_capital"] == 500_000
            assert captured_config["vote_threshold"] == 3
            assert captured_config["commission_rate"] == 0.0005
            assert captured_config["slippage"] == 0.0002
            assert captured_config["position_ratio"] == 0.8

    def test_default_parameters(self):
        """无参调用应使用所有默认值"""
        captured_config = {}

        def capture_execute(task_config):
            captured_config.update(task_config)
            return {
                "status": "success", "final_report": "r",
                "backtest_result": {"metrics": {}}, "risk_report": {},
                "factors": [], "signals": {}, "duration": 0.1,
            }

        with patch("main.OrchestratorAgent") as MockOrch:
            mock_inst = MagicMock()
            mock_inst.execute.side_effect = capture_execute
            MockOrch.return_value = mock_inst

            run_quant_pipeline()

            assert captured_config["symbol"] == "000001.SZ"
            assert captured_config["initial_capital"] == 100_000
            assert captured_config["vote_threshold"] == 2
            assert captured_config["commission_rate"] == 0.0003
            assert captured_config["slippage"] == 0.0001
            assert captured_config["position_ratio"] == 1.0
