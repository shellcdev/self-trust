# -*- coding: utf-8 -*-
"""校准模块测试（§6.2 缓冲/柔性/刚性/收入放松/回滚 + §6.4 生命周期）。

确定性可重放：全部显式传 today，不依赖真实时钟。
"""
from __future__ import annotations

import copy
from datetime import date

from core.contract import read_contract
from modules.calibrate import calibrate, run_calibrate, transition_objective


def _contract(objectives, monthly=8000, corpus=200000, override=None):
    """手工构造契约 dict（纯函数 calibrate 测试用，不落盘）。"""
    from core.contract import new_default_contract
    c = new_default_contract()
    c["corpus"] = corpus
    c["monthly_contribution"] = monthly
    c["objectives"] = objectives
    c["rebalance_override"] = override
    return c


def _obj(**kw):
    base = {"name": "FIRE", "weight": 1.0, "current_amount": 0.0,
            "start_date": "2026-01-01", "deadline": "2027-01-01",
            "target_amount": 100000, "lag_streak": 0,
            "reward_unlocked": False, "reward_quota": 0.0, "status": "active"}
    base.update(kw)
    return base


class TestLagStreakBuffer:
    """§6.2 缓冲期：连续 2 月 lag>0 才触发，单月不触发。"""

    def test_single_lag_month_no_override(self):
        c = _contract([_obj(current_amount=10000)])   # lag ≈ 0.5-0.1 > 0
        r = calibrate(c, [], today=date(2026, 7, 1))
        assert r["ok"] and not r["skipped"]
        assert c["objectives"][0]["lag_streak"] == 1
        assert c["rebalance_override"] is None        # 缓冲期：1 月不触发

    def test_two_consecutive_months_triggers_flex(self):
        """净月增 >0 → 柔性方案优先（target 下调/deadline 顺延建议层）。"""
        c = _contract([_obj(current_amount=10000, lag_streak=1)])
        r = calibrate(c, [], today=date(2026, 8, 1))
        assert c["objectives"][0]["lag_streak"] == 2
        ro = c["rebalance_override"]
        assert ro is not None and ro["reason"] == "lag_streak"
        assert ro["flex"] is not None and ro["flex"]["obj"] == "FIRE"
        assert any(ch["type"] == "flex_calibrate" for ch in r["changes"])
        # 原始配置区未被改（§10.3）
        assert c["objectives"][0]["target_amount"] == 100000
        assert c["objectives"][0]["deadline"] == "2027-01-01"

    def test_rigid_when_no_net_monthly(self):
        """净月增 ≤0（柔性不可行）→ 刚性 boost ≤ +15pct + 审批收紧。"""
        c = _contract([_obj(current_amount=10000, lag_streak=1)], monthly=0)
        calibrate(c, [], today=date(2026, 8, 1))
        ro = c["rebalance_override"]
        assert ro["reason"] == "lag_streak" and ro["flex"] is None
        assert ro["boosts"][0]["invest_boost_pct"] <= 15
        assert ro["approval_rate_adj"] <= 0

    def test_on_track_resets_streak(self):
        c = _contract([_obj(current_amount=60000, lag_streak=1)])  # 达成 60% > 时间 50%
        calibrate(c, [], today=date(2026, 7, 2))
        assert c["objectives"][0]["lag_streak"] == 0
        assert c["rebalance_override"] is None


class TestIncomeRelax:
    """§6.2 收入下跌自动放松：连续 2 月实绩 ≤ 基线×0.8 → 宽松态，优先于收紧。"""

    def test_income_drop_relaxes(self):
        c = _contract([_obj(current_amount=10000, lag_streak=1)])
        history = [{"month": "2026-05", "income": 8000},
                   {"month": "2026-06", "income": 6000},
                   {"month": "2026-07", "income": 6000}]
        r = calibrate(c, history, today=date(2026, 8, 1))
        ro = c["rebalance_override"]
        assert ro["reason"] == "income_drop"
        assert ro["invest_ratio_adj"] == -0.10
        assert ro["approval_rate_adj"] == 0.0     # 暂停收紧
        assert any(ch["type"] == "income_relax" for ch in r["changes"])
        # 原始 invest_ratio 不动
        assert c["distribution_rules"]["invest_ratio"] == 0.5

    def test_income_normal_no_relax(self):
        c = _contract([_obj(current_amount=60000)])
        history = [{"month": "2026-06", "income": 8000},
                   {"month": "2026-07", "income": 7900}]
        calibrate(c, history, today=date(2026, 8, 1))
        assert c["rebalance_override"] is None


class TestRollbackAndIdempotency:
    def test_next_month_auto_rollback(self):
        """次月自动回滚：上月临时层清空，原始权重从未被改。"""
        old = {"month": "2026-07", "reason": "lag_streak", "boosts": []}
        c = _contract([_obj(current_amount=60000)], override=copy.deepcopy(old))
        r = calibrate(c, [], today=date(2026, 8, 1))
        assert c["rebalance_override"] is None
        assert any(ch["type"] == "override_rollback" for ch in r["changes"])

    def test_same_month_skipped(self):
        c = _contract([_obj()])
        c["last_calibrate"] = "2026-07-01"
        r = calibrate(c, [], today=date(2026, 7, 15))
        assert r["skipped"] is True and r["changes"] == []

    def test_force_reruns_same_month(self):
        c = _contract([_obj(current_amount=60000)])
        c["last_calibrate"] = "2026-07-01"
        r = calibrate(c, [], today=date(2026, 7, 15), force=True)
        assert r["skipped"] is False


class TestLifecycle:
    """§6.4 生命周期：active→overdue 引擎确定性翻转；completed 仅建议。"""

    def test_overdue_flip(self):
        c = _contract([_obj(current_amount=50000)])
        r = calibrate(c, [], today=date(2027, 2, 1))   # 已过 deadline 且 <100%
        assert c["objectives"][0]["status"] == "overdue"
        flip = [ch for ch in r["changes"] if ch["type"] == "lifecycle"]
        assert flip and flip[0]["to"] == "overdue"

    def test_overdue_exits_lag_calibration(self):
        """超期目标退出常规校准（F4 超期守卫），不再累计 lag_streak。"""
        c = _contract([_obj(current_amount=50000, lag_streak=5)])
        calibrate(c, [], today=date(2027, 2, 1))
        assert c["rebalance_override"] is None   # overdue 不触发收紧

    def test_completed_only_suggested(self):
        c = _contract([_obj(current_amount=100000)])
        r = calibrate(c, [], today=date(2026, 7, 1))
        assert c["objectives"][0]["status"] == "active"   # 引擎不代决
        assert any(ch["type"] == "lifecycle_suggestion" for ch in r["changes"])

    def test_reward_unlock_via_calibrate(self):
        """≥120% → F6 解锁 reward_quota（运行态子字段）。"""
        c = _contract([_obj(current_amount=130000)])
        r = calibrate(c, [], today=date(2026, 7, 1))
        o = c["objectives"][0]
        assert o["reward_unlocked"] is True
        assert o["reward_quota"] == 6000.0   # (130000-100000)×0.2
        assert any(ch["type"] == "reward_unlocked" for ch in r["changes"])


class TestPersistence:
    def test_run_calibrate_persists_runtime(self, tmp_data_dir, base_contract):
        r = run_calibrate(tmp_data_dir, today=date(2026, 8, 1))
        assert r["ok"]
        saved = read_contract(tmp_data_dir)
        assert saved["last_calibrate"] == "2026-08-01"

    def test_transition_requires_confirm(self, tmp_data_dir, base_contract):
        r = transition_objective(tmp_data_dir, "FIRE", "archived", confirm=False)
        assert r["ok"] is False and r["error"] == "need_confirm"
        assert read_contract(tmp_data_dir)["objectives"][0]["status"] == "active"

    def test_transition_archived_with_confirm(self, tmp_data_dir, base_contract):
        r = transition_objective(tmp_data_dir, "FIRE", "archived", confirm=True)
        assert r["ok"] and r["to"] == "archived"
        assert read_contract(tmp_data_dir)["objectives"][0]["status"] == "archived"

    def test_completed_requires_achievement(self, tmp_data_dir, base_contract):
        r = transition_objective(tmp_data_dir, "FIRE", "completed", confirm=True)
        assert r["ok"] is False and r["error"] == "not_achieved"
