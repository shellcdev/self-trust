# -*- coding: utf-8 -*-
"""冷静期生命周期测试（§5.1 状态机落盘 + §5.1.1 撤回激励 + 到期终裁 + 双阶段提醒）。"""
from __future__ import annotations

from datetime import date

from core import audit
from core.contract import read_contract
from modules.judge import (
    submit, withdraw, finalize, expire, list_due_reminders,
)

TODAY = date(2026, 7, 27)


def _enqueue(tmp_data_dir, amount=6000, category="合理享受"):
    r = submit(tmp_data_dir, amount=amount, category=category,
               planned=False, today=TODAY)
    assert r["ok"] and r.get("request_id"), r
    return r["request_id"]


class TestWithdraw:
    def test_withdraw_transitions_and_persists(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        r = withdraw(tmp_data_dir, rid, today=TODAY)
        assert r["ok"] and r["status"] == "withdrawn"
        saved = read_contract(tmp_data_dir)
        assert saved["pending_requests"][0]["status"] == "withdrawn"

    def test_withdraw_feedback_is_formula_based(self, tmp_data_dir, base_contract):
        """§5.1.1 正向激励：提前月数 = 公式估算（F5/F7），非硬编码。

        base: invest_nominal=4000 → ahead_simple = 6000/4000 = 1.5（F5 可复算）。
        """
        rid = _enqueue(tmp_data_dir, amount=6000)
        r = withdraw(tmp_data_dir, rid, today=TODAY)
        fb = r["feedback"]
        assert fb["withdrawn_amount"] == 6000
        assert fb["ahead_months_simple"] == 6000 / fb["monthly_invest_nominal"]
        assert fb["objective"] == "FIRE"
        assert fb["ahead_months_real"] is not None
        # 真实口径 = 金额/净月增（F7），逐式复算
        assert abs(fb["ahead_months_real"]
                   - 6000 / fb["monthly_invest_real"]) < 1e-9
        assert "估算" in fb["estimation_note"]

    def test_withdraw_no_cashflow_gives_relative_note(self, tmp_data_dir):
        """无自由现金流 → 不给具体月数，给相对表述（严禁编造数字）。"""
        from modules.initialize import lazy_init
        d = tmp_data_dir / "nocash"
        lazy_init(d, corpus=200000, monthly_contribution=0,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        rid = submit(d, amount=6000, category="合理享受",
                     planned=False, today=TODAY)["request_id"]
        r = withdraw(d, rid, today=TODAY)
        fb = r["feedback"]
        assert fb["ahead_months_simple"] is None
        assert "相对表述" in fb["estimation_note"]

    def test_double_withdraw_rejected(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        withdraw(tmp_data_dir, rid, today=TODAY)
        r = withdraw(tmp_data_dir, rid, today=TODAY)
        assert r["ok"] is False and r["error"] == "invalid_transition"

    def test_withdraw_appends_reverse_audit(self, tmp_data_dir, base_contract):
        """撤回以追加反向记录表达，不抹原快照（§10.1）。"""
        rid = _enqueue(tmp_data_dir)
        withdraw(tmp_data_dir, rid, today=TODAY)
        records = audit.read_all(tmp_data_dir, "approval_log")
        assert len(records) == 2   # 原 F8 快照 + withdrawn 反向记录
        assert records[1]["event"] == "withdrawn"


class TestFinalizeExpire:
    def test_finalize_decided(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        r = finalize(tmp_data_dir, rid, today=TODAY)
        assert r["ok"] and r["status"] == "decided"
        assert r["decision"]["scene"] in ("A", "B", "C")

    def test_expire_before_due_rejected(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        r = expire(tmp_data_dir, rid, today=date(2026, 7, 28))  # 3 天未满
        assert r["ok"] is False and r["error"] == "not_due"

    def test_expire_after_due_rules_by_original_decision(
            self, tmp_data_dir, base_contract):
        """到期惰性终裁：原判 A/B → decided；原判 C → expired（维持驳回）。"""
        rid_b = _enqueue(tmp_data_dir, amount=6000)          # 场景 A → decided
        rid_c = _enqueue(tmp_data_dir, amount=199000)        # 场景 C → expired
        r = expire(tmp_data_dir, today=date(2026, 8, 5))     # 全部到期
        assert r["ok"] and len(r["processed"]) == 2
        by_id = {p["request_id"]: p for p in r["processed"]}
        assert by_id[rid_b]["final_status"] == "decided"
        assert by_id[rid_c]["final_status"] == "expired"
        saved = read_contract(tmp_data_dir)
        statuses = {p["request_id"]: p["status"] for p in saved["pending_requests"]}
        assert statuses[rid_b] == "decided" and statuses[rid_c] == "expired"

    def test_expire_skips_withdrawn(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        withdraw(tmp_data_dir, rid, today=TODAY)
        r = expire(tmp_data_dir, today=date(2026, 8, 5))
        assert r["ok"] and r["processed"] == []

    def test_request_not_found(self, tmp_data_dir, base_contract):
        r = withdraw(tmp_data_dir, "no-such-id", today=TODAY)
        assert r["ok"] is False and r["error"] == "request_not_found"


class TestReminders:
    def test_two_stage_reminders(self, tmp_data_dir, base_contract):
        """双阶段：冷静中（cooling 锚定）→ 到期前 ≤1 天（expiring 二次确认）。"""
        _enqueue(tmp_data_dir)   # expire_at = 2026-07-30
        c = read_contract(tmp_data_dir)
        day1 = list_due_reminders(c, today=date(2026, 7, 27))
        assert day1[0]["kind"] == "cooling" and day1[0]["days_left"] == 3
        due = list_due_reminders(c, today=date(2026, 7, 29))
        assert due[0]["kind"] == "expiring" and due[0]["days_left"] == 1

    def test_terminal_states_not_reminded(self, tmp_data_dir, base_contract):
        rid = _enqueue(tmp_data_dir)
        withdraw(tmp_data_dir, rid, today=TODAY)
        c = read_contract(tmp_data_dir)
        assert list_due_reminders(c, today=TODAY) == []
