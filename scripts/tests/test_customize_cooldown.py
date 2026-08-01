# -*- coding: utf-8 -*-
"""§5.4 冷却窗（削弱自身修改）生命周期测试。

覆盖：削弱→进冷却窗不落盘 / 非削弱→立即落盘 / 窗内撤回 / 过期自动生效 /
过期后撤回拒绝 / 确认 token 防漂移 / 预览 cooldown_required 标志 / 多类削弱字段。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core import audit as audit_io
from core import contract as contract_io
from modules import customize as cz


def _set(path: str, value):
    return {"set": [{"path": path, "value": value}],
            "add_objective": [], "whitelist_add": [], "whitelist_remove": []}


def _pending_rid(res):
    assert res["ok"] and res["pending"], res
    return res["request_id"], res["withdraw_token"]


def test_weakening_safety_cushion_goes_to_cooldown(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)  # 6 → 3（下调，削弱自身）
    prev = cz.preview(tmp_data_dir, ch)
    assert prev["cooldown_required"] is True
    tok = prev["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, _ = _pending_rid(res)
    c = contract_io.read_contract(tmp_data_dir)
    assert c["safety_cushion"]["months"] == 6, "冷却窗内配置区未变动"
    assert any(e["request_id"] == rid and e["status"] == "pending"
               for e in c.get("pending_config_changes", []))


def test_weakening_invest_ratio_goes_to_cooldown(tmp_data_dir, base_contract):
    ch = _set("distribution_rules.invest_ratio", 0.3)  # 0.5 → 0.3（下调）
    prev = cz.preview(tmp_data_dir, ch)
    assert prev["cooldown_required"] is True
    tok = prev["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, _ = _pending_rid(res)
    c = contract_io.read_contract(tmp_data_dir)
    assert c["distribution_rules"]["invest_ratio"] == 0.5, "冷却窗内未落盘"
    assert any(e["request_id"] == rid for e in c.get("pending_config_changes", []))


def test_non_weakening_guard_applies_immediately(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 9)  # 上调，非削弱
    prev = cz.preview(tmp_data_dir, ch)
    assert prev["cooldown_required"] is False
    tok = prev["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    assert res["ok"] and res["applied"] is True
    c = contract_io.read_contract(tmp_data_dir)
    assert c["safety_cushion"]["months"] == 9


def test_optimization_goal_switch_not_cooldown(tmp_data_dir, base_contract):
    ch = _set("optimization_goal", "wealth")  # 护栏字段但非「下调」削弱
    prev = cz.preview(tmp_data_dir, ch)
    assert prev["cooldown_required"] is False
    tok = prev["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    assert res["applied"] is True
    assert contract_io.read_contract(tmp_data_dir)["optimization_goal"] == "wealth"


def test_withdraw_within_window(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, wtok = _pending_rid(res)
    wres = cz.withdraw_config(tmp_data_dir, rid, wtok)
    assert wres["ok"] and wres["withdrawn"] is True
    c = contract_io.read_contract(tmp_data_dir)
    assert c["safety_cushion"]["months"] == 6
    assert not any(e["request_id"] == rid for e in c.get("pending_config_changes", []))


def test_withdraw_bad_token_rejected(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, _ = _pending_rid(res)
    wres = cz.withdraw_config(tmp_data_dir, rid, "deadbeefdeadbeef")
    assert wres["ok"] is False and wres["error"] == "bad_token"


def test_sweep_applies_after_expiry(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, _ = _pending_rid(res)
    future = datetime.now() + timedelta(days=2)
    swept = cz.sweep_pending_config(tmp_data_dir, now=future)
    assert rid in swept["applied"]
    c = contract_io.read_contract(tmp_data_dir)
    assert c["safety_cushion"]["months"] == 3, "过期后自动生效"
    logs = audit_io.read_all(tmp_data_dir, "override_log")
    assert any(l.get("event") == "contract_customize_cooled" for l in logs)


def test_sweep_removes_applied_from_queue(tmp_data_dir, base_contract):
    # M5：到期自动生效的条目应从 pending_config_changes 移除（历史沉淀在 override_log），
    # 避免队列无限堆积脏数据。
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    future = datetime.now() + timedelta(days=2)
    cz.sweep_pending_config(tmp_data_dir, now=future)
    c = contract_io.read_contract(tmp_data_dir)
    assert not c.get("pending_config_changes"), "已生效条目应已清空"


def test_withdraw_after_expiry_rejected(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rid, wtok = _pending_rid(res)
    future = datetime.now() + timedelta(days=2)
    wres = cz.withdraw_config(tmp_data_dir, rid, wtok, now=future)
    assert wres["ok"] is False and wres["error"] == "expired"


def test_sweep_multiple_expired_all_applied(tmp_data_dir, base_contract):
    # 多个 pending 过期项一同扫描：验证在 work 深拷贝链上 pcc 引用一致，
    # 全部生效 + 全部移出队列（regression for 深浅引用混用 #1）。
    ch1 = _set("safety_cushion.months", 3)        # 6 → 3
    r1 = cz.apply(tmp_data_dir, ch1, confirm=True,
                  token=cz.preview(tmp_data_dir, ch1)["token"], reason="")
    rid1 = r1["request_id"]
    ch2 = _set("distribution_rules.invest_ratio", 0.3)  # 0.5 → 0.3
    r2 = cz.apply(tmp_data_dir, ch2, confirm=True,
                  token=cz.preview(tmp_data_dir, ch2)["token"], reason="")
    rid2 = r2["request_id"]
    future = datetime.now() + timedelta(days=2)
    swept = cz.sweep_pending_config(tmp_data_dir, now=future)
    assert set(swept["applied"]) == {rid1, rid2}, swept
    c = contract_io.read_contract(tmp_data_dir)
    assert c["safety_cushion"]["months"] == 3, "过期项1已生效"
    assert c["distribution_rules"]["invest_ratio"] == 0.3, "过期项2已生效"
    assert c.get("pending_config_changes", []) == [], "全部生效后队列清空"


def test_stale_token_no_pending_created(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    res = cz.apply(tmp_data_dir, ch, confirm=True, token="wrong" + tok[5:], reason="")
    assert res["ok"] is False and res["error"] == "stale_token"
    c = contract_io.read_contract(tmp_data_dir)
    assert not c.get("pending_config_changes"), "token 错误不应建 pending"


def test_review_lists_pending_and_sweeps(tmp_data_dir, base_contract):
    ch = _set("safety_cushion.months", 3)
    tok = cz.preview(tmp_data_dir, ch)["token"]
    cz.apply(tmp_data_dir, ch, confirm=True, token=tok, reason="")
    rev = cz.review_config(tmp_data_dir)
    assert rev["ok"]
    assert len(rev["pending"]) == 1
    assert rev["pending"][0]["kind"] in ("cooling", "expiring")
    # 过期后复查应自动生效并清空 pending
    future = datetime.now() + timedelta(days=2)
    rev2 = cz.review_config(tmp_data_dir, now=future)
    assert rev2["swept"] and not rev2["pending"]
