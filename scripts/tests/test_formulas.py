# -*- coding: utf-8 -*-
"""F0~F8 逐式测试 + 除零/null/超期 clamp 边界（设计文档 §2.0；测试价值序第 2）。"""
from __future__ import annotations

import doctest
from datetime import date

import pytest

from core import formulas as F


def test_doctests_all_pass():
    """doctest 用文档示例数字，防文档代码漂移。"""
    results = doctest.testmod(F)
    assert results.failed == 0, f"{results.failed} doctest 失败"


# ---------------- F0 ----------------
class TestF0:
    def test_basic(self):
        r = F.f0_net_position(
            200000,
            [{"balance": 800000, "monthly_payment": 5000}],
            [{"amount": 12000}],
            8000)
        assert r["net_assets"] == -600000.0
        assert r["rigid_monthly"] == 1000.0
        assert r["monthly_net"] == 8000.0

    def test_empty_lists_and_none(self):
        r = F.f0_net_position(100000, None, None, 5000)
        assert r["net_assets"] == 100000.0
        assert r["liabilities_sum"] == 0.0
        assert r["rigid_monthly"] == 0.0

    def test_missing_keys_treated_as_zero(self):
        r = F.f0_net_position(1000, [{"name": "无余额字段"}], [{}], 0)
        assert r["liabilities_sum"] == 0.0
        assert r["rigid_monthly"] == 0.0


# ---------------- F1 ----------------
class TestF1:
    def test_months(self):
        assert F.f1_effective_cushion("months", 5000, months=6) == 30000.0

    def test_fixed(self):
        assert F.f1_effective_cushion("fixed", 5000, fixed=100000) == 100000.0

    def test_ratio_positive_net(self):
        assert F.f1_effective_cushion("ratio", 5000, ratio=0.2,
                                      net_assets=500000) == 100000.0

    def test_ratio_negative_net_clamps_to_zero(self):
        """资不抵债时 max(净资产,0) → 垫收敛为 0，不虚高。"""
        assert F.f1_effective_cushion("ratio", 5000, ratio=0.2,
                                      net_assets=-1) == 0.0

    def test_unknown_mode_falls_back_to_zero(self):
        # 未知模式兜底返回 0（不抛），避免 bogus 模式让 judge/report 全崩；
        # 非法模式由 customize 边界拒绝。
        assert F.f1_effective_cushion("bogus", 5000) == 0.0


# ---------------- F2 ----------------
class TestF2:
    def test_normal(self):
        # (30000/30)*3 = 3000，落在 [1000, 15000] 内
        assert F.f2_cooldown_threshold(30000, 3, 5000) == 3000.0

    def test_clamp_upper(self):
        assert F.f2_cooldown_threshold(10**7, 3, 5000) == 15000.0

    def test_clamp_lower(self):
        assert F.f2_cooldown_threshold(0, 3, 5000) == 1000.0


# ---------------- F3 / F3.5 ----------------
class TestF3:
    def test_nominal(self):
        assert F.f3_monthly_invest_nominal(8000, 0.5) == 4000.0

    def test_zero_or_negative_net(self):
        assert F.f3_monthly_invest_nominal(0, 0.5) == 0.0
        assert F.f3_monthly_invest_nominal(-100, 0.5) == 0.0

    def test_real_default_params(self):
        # 4000 × 0.9 × (1 + 0.025/12) = 3607.5
        assert F.f3_5_monthly_invest_real(4000) == pytest.approx(3607.5)

    def test_real_zero(self):
        assert F.f3_5_monthly_invest_real(0) == 0.0


# ---------------- F4 ----------------
class TestF4:
    def test_lag_positive(self):
        r = F.f4_lag(42, 100, date(2026, 1, 1), date(2026, 1, 11),
                     date(2026, 1, 6))
        assert r["lag"] == pytest.approx(0.08)
        assert not r["overdue"]

    def test_overdue_time_clamped_to_one(self):
        r = F.f4_lag(80, 100, date(2026, 1, 1), date(2026, 1, 11),
                     date(2027, 1, 1))
        assert r["time_progress"] == 1.0
        assert r["overdue"] is True

    def test_no_deadline_disabled(self):
        assert F.f4_lag(42, None, None, None, date(2026, 1, 1)) is None
        assert F.f4_lag(42, 100, date(2026, 1, 1), None, date(2026, 1, 2)) is None

    def test_zero_period_disabled(self):
        d = date(2026, 1, 1)
        assert F.f4_lag(42, 100, d, d, d) is None


# ---------------- F5 ----------------
class TestF5:
    def test_doc_example(self):
        assert F.f5_impact_simple(10000, 5000) == 2.0

    def test_zero_invest_returns_none(self):
        assert F.f5_impact_simple(10000, 0) is None
        assert F.f5_impact_simple(10000, None) is None


# ---------------- F6 ----------------
class TestF6:
    def test_unlock_at_120(self):
        r = F.f6_reward(360000, 300000, False)
        assert r["unlockable"] and r["reward_max"] == 12000.0

    def test_below_120_not_unlockable(self):
        assert not F.f6_reward(359999, 300000, False)["unlockable"]

    def test_already_unlocked(self):
        assert not F.f6_reward(360000, 300000, True)["unlockable"]

    def test_null_target(self):
        r = F.f6_reward(100, None, False)
        assert not r["unlockable"] and r["achieve_ratio"] is None


# ---------------- F7 ----------------
class TestF7:
    def test_no_deadline_disabled(self):
        assert F.f7_real_pace(1, 0, 100, None, date(2026, 1, 1), 100) is None
        assert F.f7_real_pace(1, 0, None, date(2036, 1, 1),
                              date(2026, 1, 1), 100) is None

    def test_zero_net_monthly_no_division(self):
        r = F.f7_real_pace(10000, 100000, 300000, date(2036, 1, 1),
                           date(2026, 1, 1), 0)
        assert r["real_delay_months"] is None
        assert r["coverage_months"] is None

    def test_inflation_raises_target(self):
        r = F.f7_real_pace(0, 0, 100000, date(2036, 1, 3),
                           date(2026, 1, 1), 1000, inflation=0.025)
        assert r["target_amount_adj"] > 100000

    def test_past_deadline_clamps_years(self):
        r = F.f7_real_pace(0, 0, 100000, date(2020, 1, 1),
                           date(2026, 1, 1), 1000)
        assert r["remaining_years"] == 0.0
        assert r["target_amount_adj"] == pytest.approx(100000)


# ---------------- F8 ----------------
class TestF8:
    def test_snapshot_structure(self):
        snap = F.f8_audit_snapshot(
            time="2026-07-27T00:00:00", amount=100, category="医疗", scene="A",
            inputs={"corpus": 1}, formulas_used=["F0"],
            decision={"scene": "A", "result": "批准", "summary": "ok"})
        assert snap["decision"]["result"] == "批准"

    def test_missing_decision_keys_raises(self):
        with pytest.raises(ValueError, match="缺少必备键"):
            F.f8_audit_snapshot(
                time="t", amount=1, category="c", scene="A",
                inputs={}, formulas_used=[], decision={"scene": "A"})
