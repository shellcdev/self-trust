# -*- coding: utf-8 -*-
"""治理模块（§5.2 申诉 / 人工覆写）测试。

核心断言：
- 未知 request_id 申诉 → request_not_found（不崩）；
- 覆写未开放（appeal_count < 3）→ override_not_open；
- 连续 3 次申诉被驳 → 第 3 次 override_open=True；随后 confirm 覆写 → 申请置 DECIDED。
  （被驳申请无 pending_spends 台账，台账联动由 judge 批准路径覆盖）
"""
from __future__ import annotations

from datetime import date

from core import contract as contract_io
from modules import governance as mod_gov

TODAY = date(2026, 7, 27)


def _inject_unaffordable_request(tmp_data_dir):
    """注入一笔远超资金池、必被 §4.4 判为场景 C 的冷静期申请。"""
    c = contract_io.read_contract(tmp_data_dir)
    rid = "govtest00001"
    c["pending_requests"].append({
        "request_id": rid,
        "time": "2026-07-27T00:00:00",
        "amount": 10_000_000,
        "category": "其他",
        "planned": False,
        "expire_at": "2026-08-27T00:00:00",
        "status": "cooling",
        "financed_amount": 0,
        "mortgage_monthly": None,
    })
    contract_io.write_contract(tmp_data_dir, c, actor="engine")
    return rid


def test_appeal_unknown_request(tmp_data_dir, base_contract):
    r = mod_gov.appeal(tmp_data_dir, request_id="nope", reason="测试", today=TODAY)
    assert r["ok"] is False and r["error"] == "request_not_found"


def test_override_not_open_without_appeals(tmp_data_dir, base_contract):
    rid = _inject_unaffordable_request(tmp_data_dir)
    r = mod_gov.override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
    assert r["ok"] is False and r["error"] == "override_not_open"


def test_appeal_chain_opens_override(tmp_data_dir, base_contract):
    rid = _inject_unaffordable_request(tmp_data_dir)
    last = None
    for _ in range(3):
        last = mod_gov.appeal(tmp_data_dir, request_id=rid, reason="测试", today=TODAY)
        assert last["ok"]
    assert last["appeal_count"] == 3
    assert last["override_open"] is True
    # 覆写放行：申请置 DECIDED（被驳申请无 pending_spends 台账，台账联动由 judge 批准路径覆盖）
    res = mod_gov.override(tmp_data_dir, request_id=rid, confirm=True, today=TODAY)
    assert res["ok"] and res["status"] == "decided"
    c = contract_io.read_contract(tmp_data_dir)
    entry = next(e for e in c["pending_requests"] if e["request_id"] == rid)
    assert entry["status"] == "decided"
