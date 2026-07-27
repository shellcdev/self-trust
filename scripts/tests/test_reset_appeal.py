# -*- coding: utf-8 -*-
"""重置 + 申诉/覆写 + 对账测试（§7.1.1 / §5.2 / §3.2）。"""
from __future__ import annotations

from datetime import date

from core import audit
from core.contract import read_contract, contract_path
from modules.governance import appeal, override, reset_contract, reconcile
from modules.judge import submit

TODAY = date(2026, 7, 27)


def _rejected_request(tmp_data_dir):
    """造一个必被驳回（场景 C）且入冷静期的申请。"""
    r = submit(tmp_data_dir, amount=199000, category="合理享受",
               planned=False, today=TODAY)
    assert r["decision"]["scene"] == "C" and r.get("request_id")
    return r["request_id"]


class TestAppeal:
    def test_appeal_upheld_increments_count(self, tmp_data_dir, base_contract):
        rid = _rejected_request(tmp_data_dir)
        r = appeal(tmp_data_dir, request_id=rid, reason="真的很需要", today=TODAY)
        assert r["ok"] and r["upheld"] is True
        assert r["appeal_count"] == 1 and r["override_open"] is False
        assert read_contract(tmp_data_dir)["appeal_count"] == 1
        logs = audit.read_all(tmp_data_dir, "appeal_log")
        assert logs[-1]["result"] == "维持驳回"

    def test_three_appeals_open_override(self, tmp_data_dir, base_contract):
        rid = _rejected_request(tmp_data_dir)
        for i in range(1, 4):
            r = appeal(tmp_data_dir, request_id=rid, reason=f"第{i}次", today=TODAY)
        assert r["appeal_count"] == 3 and r["override_open"] is True

    def test_different_request_resets_count(self, tmp_data_dir, base_contract):
        rid1 = _rejected_request(tmp_data_dir)
        appeal(tmp_data_dir, request_id=rid1, reason="a", today=TODAY)
        appeal(tmp_data_dir, request_id=rid1, reason="b", today=TODAY)
        rid2 = _rejected_request(tmp_data_dir)
        r = appeal(tmp_data_dir, request_id=rid2, reason="换申请", today=TODAY)
        assert r["appeal_count"] == 1   # 换 request_id 自动归零后重计

    def test_appeal_unknown_request(self, tmp_data_dir, base_contract):
        r = appeal(tmp_data_dir, request_id="ghost", reason="x", today=TODAY)
        assert r["ok"] is False and r["error"] == "request_not_found"


class TestOverride:
    def _open_override(self, tmp_data_dir):
        rid = _rejected_request(tmp_data_dir)
        for i in range(3):
            appeal(tmp_data_dir, request_id=rid, reason=f"{i}", today=TODAY)
        return rid

    def test_override_before_threshold_rejected(self, tmp_data_dir, base_contract):
        rid = _rejected_request(tmp_data_dir)
        appeal(tmp_data_dir, request_id=rid, reason="1", today=TODAY)
        r = override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
        assert r["ok"] is False and r["error"] == "override_not_open"

    def test_override_requires_confirm_with_impact(self, tmp_data_dir, base_contract):
        rid = self._open_override(tmp_data_dir)
        r = override(tmp_data_dir, request_id=rid, confirm=False, today=TODAY)
        assert r["ok"] is False and r["error"] == "need_confirm"
        assert "target_impact" in r   # 必须先看清目标延后代价

    def test_override_consumes_count_and_logs(self, tmp_data_dir, base_contract):
        rid = self._open_override(tmp_data_dir)
        r = override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
        assert r["ok"] and r["appeal_count"] == 0
        assert read_contract(tmp_data_dir)["appeal_count"] == 0   # 消耗归零
        logs = audit.read_all(tmp_data_dir, "override_log")
        assert logs[-1]["event"] == "manual_override"
        assert logs[-1]["target_impact"]["delay_months_simple"] is not None
        # 再次覆写须重新积累 3 次
        r2 = override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
        assert r2["ok"] is False and r2["error"] == "override_not_open"


class TestReset:
    def test_reset_requires_confirm(self, tmp_data_dir, base_contract):
        r = reset_contract(tmp_data_dir, confirm=False)
        assert r["ok"] is False and r["error"] == "need_confirm"
        assert read_contract(tmp_data_dir)["corpus"] == 200000   # 未动

    def test_reset_rebuilds_and_keeps_audit(self, tmp_data_dir, base_contract):
        # 先造审计历史
        submit(tmp_data_dir, amount=6000, category="合理享受",
               planned=False, today=TODAY)
        before = len(audit.read_all(tmp_data_dir, "approval_log"))
        assert before >= 1
        r = reset_contract(
            tmp_data_dir, confirm=True, corpus=50000, monthly_contribution=5000,
            objectives=[{"name": "新目标", "target_amount": 500000,
                         "deadline": "2030-01-01"}], today=TODAY)
        assert r["ok"] and r["reset"] is True and r["old_contract_sha256"]
        saved = read_contract(tmp_data_dir)
        assert saved["corpus"] == 50000
        assert saved["objectives"][0]["name"] == "新目标"
        # 审计不丢：旧记录仍在 + 新增 contract_reset 事件
        assert len(audit.read_all(tmp_data_dir, "approval_log")) == before
        ov = audit.read_all(tmp_data_dir, "override_log")
        assert ov[-1]["event"] == "contract_reset"
        assert ov[-1]["old_contract_sha256"] == r["old_contract_sha256"]

    def test_reset_missing_params(self, tmp_data_dir, base_contract):
        r = reset_contract(tmp_data_dir, confirm=True)
        assert r["ok"] is False and r["error"] == "missing_params"
        assert contract_path(tmp_data_dir).is_file()   # 未删旧契约


class TestReconcile:
    def test_reconcile_updates_corpus_and_anchor(self, tmp_data_dir, base_contract):
        r = reconcile(tmp_data_dir, corpus=210000, today=TODAY)
        assert r["ok"] and r["changes"]["corpus"]["to"] == 210000
        saved = read_contract(tmp_data_dir)
        assert saved["corpus"] == 210000
        assert saved["reconcile"]["last_reconcile"] == "2026-07-27"
        assert saved["reconcile"]["reminder_streak"] == 0

    def test_reconcile_appends_income_snapshot(self, tmp_data_dir, base_contract):
        r = reconcile(tmp_data_dir, income=8000, invest=4000,
                      living=3000, impulse=0, today=TODAY)
        assert r["snapshot_appended"]["income"] == 8000
        records = audit.read_all(tmp_data_dir, "monthly_history")
        assert records[-1]["source"] == "reconcile"
