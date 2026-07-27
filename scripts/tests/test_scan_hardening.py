# -*- coding: utf-8 -*-
"""第二份扫描报告（Loomy/self-trust-硬伤扫描报告.md）严重项回归测试。

覆盖：
- H1  governance.appeal 重审须透传融资参数（financed_amount/down_payment/mortgage_monthly）
- H2  judge.withdraw 过期后禁止撤回（须走 expire 终裁）
- H3  judge._objective_impacts 多目标权重须归一化（share 除 total_weight）
- H4  customize._is_weakening 须覆盖 ratio/fixed 下调与模式切换（有效安全垫下降即削弱）
- H5  customize._risk_warnings 须用修改后契约（数字反映终态）
- H6  customize._apply_changes 须拒绝同名重复追加（防数据污染）
- H7  governance.override 放行后须闭环 request 状态（置 DECIDED + 记 decision + 同步台账）
"""
from __future__ import annotations

import pytest
from datetime import date

from core.contract import read_contract, write_contract
from modules.customize import _apply_changes, _is_weakening, _risk_warnings, preview
from modules.governance import appeal, override
from modules.judge import _objective_impacts, submit, withdraw

TODAY = date(2026, 7, 27)


# --------------------------------------------------------------------------- H1
class TestH1AppealFinancing:
    def _make_contract(self, tmp_data_dir):
        from modules.initialize import lazy_init
        lazy_init(tmp_data_dir, corpus=600_000, monthly_contribution=8_000,
                  objectives=[{"name": "FIRE", "target_amount": 3_000_000,
                               "deadline": "2036-01-01"}], today=TODAY)
        return read_contract(tmp_data_dir)

    def _inject_financed(self, contract, financed_amount, down_payment,
                         mortgage_monthly):
        entry = {
            "request_id": "fin1",
            "time": "2026-07-27T00:00:00",
            "amount": 1_000_000,
            "category": "房产",
            "planned": False,
            "expire_at": "2026-07-30T00:00:00",
            "status": "cooling",
            "decision": {"scene": "A", "result": "批准", "summary": "x"},
            "financed_amount": financed_amount,
            "down_payment": down_payment,
            "mortgage_monthly": mortgage_monthly,
        }
        contract.setdefault("pending_requests", []).append(entry)
        return contract

    def test_appeal_uses_financing_not_full_amount(self, tmp_data_dir):
        """融资购房（首付 10 万、月供 2 千可覆盖）重审应放行；若按全款 100 万判定则必驳回。"""
        c = self._make_contract(tmp_data_dir)
        self._inject_financed(c, 900_000, 100_000, 2_000)
        write_contract(tmp_data_dir, c, actor="engine")
        v = appeal(tmp_data_dir, request_id="fin1", reason="融资购房申诉",
                   today=TODAY)
        assert v["ok"]
        # 修复后带融资参数：首付仅 10 万、月供可覆盖 → 不应维持驳回
        assert v["upheld"] is False
        assert v["decision"]["scene"] in ("A", "B")

    def test_appeal_without_financing_params_rejects(self, tmp_data_dir):
        """对照：financed_amount=0（模拟 H1 修复前的退化口径）→ 按全款判定必维持驳回。"""
        c = self._make_contract(tmp_data_dir)
        self._inject_financed(c, 0, 1_000_000, 0)
        write_contract(tmp_data_dir, c, actor="engine")
        v = appeal(tmp_data_dir, request_id="fin1", reason="x", today=TODAY)
        assert v["ok"]
        assert v["upheld"] is True   # 全款 100 万 > corpus 60 万 → 维持驳回
        assert v["decision"]["scene"] == "C"


# --------------------------------------------------------------------------- H3
class TestH3WeightNormalization:
    def _two_obj_contract(self, w1, w2):
        return {
            "objectives": [
                {"name": "A", "target_amount": 200_000,
                 "deadline": "2036-01-01", "current_amount": 0,
                 "weight": w1, "status": "active"},
                {"name": "B", "target_amount": 200_000,
                 "deadline": "2036-01-01", "current_amount": 0,
                 "weight": w2, "status": "active"},
            ]
        }

    def test_shares_sum_to_amount_and_split_equally(self):
        contract = self._two_obj_contract(1.0, 1.0)
        impacted, _, _ = _objective_impacts(
            contract, 10_000, False, 4_000, 4_000, 0.025, TODAY)
        shares = [i["amount_share"] for i in impacted]
        # 两目标等权 → 各摊 5,000，合计 = 实际支出 10,000（H3 修复前各 10,000 合计翻倍）
        assert shares == [5_000.0, 5_000.0]
        assert sum(shares) == 10_000.0

    def test_scaling_all_weights_keeps_shares(self):
        """所有权重等比放大不应改变各目标 share（相对权重语义）。"""
        c1 = self._two_obj_contract(1.0, 1.0)
        c2 = self._two_obj_contract(3.0, 3.0)
        s1, _, _ = _objective_impacts(c1, 10_000, False, 4_000, 4_000, 0.025, TODAY)
        s2, _, _ = _objective_impacts(c2, 10_000, False, 4_000, 4_000, 0.025, TODAY)
        assert [i["amount_share"] for i in s1] == [i["amount_share"] for i in s2]


# --------------------------------------------------------------------------- H7
class TestH7OverrideClosesLoop:
    def _open_override(self, tmp_data_dir):
        rid = submit(tmp_data_dir, amount=199_000, category="合理享受",
                     planned=False, today=TODAY)["request_id"]
        for i in range(3):
            appeal(tmp_data_dir, request_id=rid, reason=f"{i}", today=TODAY)
        return rid

    def test_override_marks_request_decided_and_records_decision(self,
                                                                  tmp_data_dir,
                                                                  base_contract):
        rid = self._open_override(tmp_data_dir)
        r = override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
        assert r["ok"]
        assert r["status"] == "decided"          # H7 修复前无此字段（仍 cooling）
        saved = read_contract(tmp_data_dir)
        entry = next(e for e in saved["pending_requests"]
                     if e["request_id"] == rid)
        assert entry["status"] == "decided"
        assert entry.get("decision", {}).get("result") == "人工覆写放行"

    def test_override_decided_cannot_be_withdrawn(self, tmp_data_dir,
                                                   base_contract):
        """状态已闭环：DECIDED 申请不可再 withdraw（杜绝无限放行环）。"""
        from modules.judge import withdraw
        rid = self._open_override(tmp_data_dir)
        override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
        w = withdraw(tmp_data_dir, request_id=rid, today=TODAY)
        assert w["ok"] is False
        assert w["error"] == "invalid_transition"


# --------------------------------------------------------------------------- H2
class TestH2WithdrawExpiry:
    def _cooling_request(self, tmp_data_dir, base_contract):
        return submit(tmp_data_dir, amount=199_000, category="合理享受",
                      planned=False, today=TODAY)["request_id"]

    def test_withdraw_before_expiry_ok(self, tmp_data_dir, base_contract):
        rid = self._cooling_request(tmp_data_dir, base_contract)
        r = withdraw(tmp_data_dir, request_id=rid, today=TODAY)
        assert r["ok"] and r["status"] == "withdrawn"

    def test_withdraw_after_expiry_rejected(self, tmp_data_dir, base_contract):
        """H2 修复：过期后状态机仍 cooling（终裁懒惰），撤回须被拒、改走 expire。"""
        rid = self._cooling_request(tmp_data_dir, base_contract)
        r = withdraw(tmp_data_dir, request_id=rid, today=date(2026, 8, 1))
        assert r["ok"] is False
        assert r["error"] == "already_expired"


# --------------------------------------------------------------------------- H4
class TestH4Weakening:
    def test_ratio_down_triggers_cooldown(self, base_contract):
        c = base_contract
        changed = {"safety_cushion": {
            "from": {"mode": "ratio", "ratio": 0.3},
            "to": {"mode": "ratio", "ratio": 0.1}}}
        assert _is_weakening(changed, c) is True

    def test_ratio_up_does_not_weaken(self, base_contract):
        c = base_contract
        changed = {"safety_cushion": {
            "from": {"mode": "ratio", "ratio": 0.1},
            "to": {"mode": "ratio", "ratio": 0.3}}}
        assert _is_weakening(changed, c) is False

    def test_fixed_down_triggers_cooldown(self, base_contract):
        c = base_contract
        changed = {"safety_cushion": {
            "from": {"mode": "fixed", "fixed": 100_000},
            "to": {"mode": "fixed", "fixed": 50_000}}}
        assert _is_weakening(changed, c) is True

    def test_mode_switch_months_to_fixed_weaker_triggers(self, base_contract):
        """months(6)×基线 若 > fixed 值 → 模式切换也是削弱，须进冷却窗。"""
        c = base_contract
        changed = {"safety_cushion": {
            "from": {"mode": "months", "months": 6},
            "to": {"mode": "fixed", "fixed": 1_000}}}
        assert _is_weakening(changed, c) is True

    def test_non_guard_change_not_weakening(self, base_contract):
        c = base_contract
        changed = {"optimization_goal": {"from": "balanced", "to": "wealth"}}
        assert _is_weakening(changed, c) is False


# --------------------------------------------------------------------------- H5
class TestH5RiskWarningsNewContract:
    def test_warnings_reflect_new_monthly_contribution(self):
        old = {"safety_cushion": {"mode": "months", "months": 6},
               "monthly_contribution": 8_000,
               "living_baseline": 5_000,
               "distribution_rules": {"invest_ratio": 0.5},
               "objectives": [], "fast_track_whitelist": []}
        new = dict(old)
        new["monthly_contribution"] = 4_000
        changed = {"distribution_rules": {
            "from": {"invest_ratio": 0.5}, "to": {"invest_ratio": 0.2}}}
        warns_old = _risk_warnings(old, changed)
        warns_new = _risk_warnings(new, changed)
        # 旧 m=8000 → 0.2×8000=1600；新 m=4000 → 0.2×4000=800（H5 修复前都用旧值）
        assert any("1600" in w for w in warns_old)
        assert any("800" in w for w in warns_new)
        assert warns_new != warns_old


# --------------------------------------------------------------------------- H6
class TestH6Dedup:
    def test_add_objective_duplicate_rejected(self, base_contract):
        # 同一次变更内同名 => 第二次追加应被拒（不依赖契约既有条目）
        changes = {"add_objective": ["旅行基金:200000:2030-01-01",
                                     "旅行基金:200000:2030-01-01"]}
        with pytest.raises(ValueError):
            _apply_changes(base_contract, changes)

    def test_add_liability_duplicate_rejected(self, base_contract):
        changes = {"add_liability": [
            {"name": "车贷", "balance": 100_000, "monthly_payment": 3_000,
             "annual_rate": 0.04},
            {"name": "车贷", "balance": 50_000, "monthly_payment": 1_500,
             "annual_rate": 0.04}]}
        with pytest.raises(ValueError):
            _apply_changes(base_contract, changes)

    def test_add_distinct_names_ok(self, base_contract):
        changes = {"add_objective": ["旅行基金:200000:2030-01-01"]}
        new, _ = _apply_changes(base_contract, changes)
        assert any(o.get("name") == "旅行基金" for o in new["objectives"])
