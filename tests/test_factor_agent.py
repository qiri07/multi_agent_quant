"""
测试 agents/factor_agent.py —— 多因子并行计算
"""
import pandas as pd
import pytest

from agents.factor_agent import FactorAgent


class TestFactorAgent:
    """测试各因子计算函数及 execute 并行执行"""

    @pytest.fixture
    def agent(self):
        return FactorAgent()

    @pytest.fixture
    def df(self, sample_with_factors):
        """注入少量因子用于部分单独测试"""
        return sample_with_factors

    # ---- 均线因子 ----

    def test_calc_ma_factors(self, agent, sample_ohlcv):
        factors = agent.calc_ma_factors(sample_ohlcv)
        expected_keys = {"MA5", "MA10", "MA20", "MA60", "MA_bull"}
        assert expected_keys.issubset(factors.keys())
        for key in ["MA5", "MA10", "MA20", "MA60"]:
            # 前几个值为 NaN（rolling 窗口不足），取第一个非 NaN 值验证
            valid = factors[key].dropna()
            assert len(valid) > 0
            assert valid.iloc[0] > 0

    def test_ma_bull_is_binary(self, agent, sample_ohlcv):
        factors = agent.calc_ma_factors(sample_ohlcv)
        vals = factors["MA_bull"].dropna()
        assert set(vals.unique()).issubset({0, 1})

    # ---- 动量因子 ----

    def test_calc_momentum_factors(self, agent, sample_ohlcv):
        factors = agent.calc_momentum_factors(sample_ohlcv)
        assert "RSI" in factors
        assert "MACD_DIF" in factors
        assert "MACD_DEA" in factors
        assert "MACD_HIST" in factors
        for w in [5, 10, 20]:
            assert f"momentum_{w}d" in factors

    def test_rsi_range(self, agent, sample_ohlcv):
        factors = agent.calc_momentum_factors(sample_ohlcv)
        rsi = factors["RSI"].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_momentum_initial_values_are_nan(self, agent, sample_ohlcv):
        factors = agent.calc_momentum_factors(sample_ohlcv)
        # 前4天 momentum_5d 应为 NaN（ rolling window 不足）
        assert factors["momentum_5d"].isna().sum() >= 4

    # ---- 波动率因子 ----

    def test_calc_volatility_factors(self, agent, sample_ohlcv):
        factors = agent.calc_volatility_factors(sample_ohlcv)
        expected = {"BOLL_MID", "BOLL_STD", "BOLL_UPPER", "BOLL_LOWER",
                    "BOLL_POS", "volatility_20d", "ATR"}
        assert expected.issubset(factors.keys())

    def test_boll_position_range(self, agent, sample_ohlcv):
        factors = agent.calc_volatility_factors(sample_ohlcv)
        pos = factors["BOLL_POS"].dropna()
        # BOLL_POS 理论上在 0~1 附近，允许边界略超出
        assert (pos >= -0.5).all() and (pos <= 1.5).all()

    def test_atr_positive(self, agent, sample_ohlcv):
        factors = agent.calc_volatility_factors(sample_ohlcv)
        atr = factors["ATR"].dropna()
        assert (atr > 0).all()

    # ---- 量价因子 ----

    def test_calc_volume_factors(self, agent, sample_ohlcv):
        factors = agent.calc_volume_factors(sample_ohlcv)
        assert "VOL_MA5" in factors
        assert "VOL_MA10" in factors
        assert "VOL_RATIO" in factors
        assert "VWAP" in factors

    def test_vol_ratio_no_division_by_zero(self, agent, sample_ohlcv):
        factors = agent.calc_volume_factors(sample_ohlcv)
        ratio = factors["VOL_RATIO"].dropna()
        assert (ratio > 0).all()

    # ---- CCI 因子 ----

    def test_calc_cci_factors(self, agent, sample_ohlcv):
        factors = agent.calc_cci_factors(sample_ohlcv)
        assert "CCI" in factors
        valid = factors["CCI"].dropna()
        assert len(valid) > 0
        # CCI 理论上无界，但实际应在合理范围内
        assert valid.min() > -1000 and valid.max() < 1000

    # ---- KDJ 因子 ----

    def test_calc_kdj_factors(self, agent, sample_ohlcv):
        factors = agent.calc_kdj_factors(sample_ohlcv)
        assert {"KDJ_K", "KDJ_D", "KDJ_J"}.issubset(factors.keys())
        for key in ["KDJ_K", "KDJ_D"]:
            valid = factors[key].dropna()
            assert len(valid) > 0
            # K/D 应在 0~100 范围内
            assert valid.min() >= -10 and valid.max() <= 110

    # ---- ADX 因子 ----

    def test_calc_adx_factors(self, agent, sample_ohlcv):
        factors = agent.calc_adx_factors(sample_ohlcv)
        assert {"PLUS_DI", "MINUS_DI", "ADX"}.issubset(factors.keys())
        for key in ["PLUS_DI", "MINUS_DI", "ADX"]:
            valid = factors[key].dropna()
            assert len(valid) > 0
            assert valid.min() >= 0 and valid.max() <= 200

    # ---- execute（集成） ----

    def test_execute_adds_factors_to_state(self, agent, mock_state, sample_ohlcv):
        mock_state["data"] = sample_ohlcv
        result = agent.execute(mock_state)
        assert len(result["factors"]) == 30  # MA(5)+Momentum(7)+Volatility(7)+Volume(4)+CCI(1)+KDJ(3)+ADX(3)
        assert isinstance(result["data"], pd.DataFrame)

    def test_execute_drops_na_rows(self, agent, mock_state, sample_ohlcv):
        mock_state["data"] = sample_ohlcv
        result = agent.execute(mock_state)
        assert result["data"].notna().all().all()  # 无 NaN 行
