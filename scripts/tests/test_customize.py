# -*- coding: utf-8 -*-
"""记账自定义（§5.4 / §7.1 / §9）测试。

核心断言：
- 预览（confirm=False）不落盘，返回 needs_confirm + token + 护栏风险提示；
- 无/错 token 确认 → stale_token（防手滑，§5.4 单次确认不生效）；
- 带正确 token 确认 → 落盘 + override_log 追加（§5.4 步骤4）；
- 核心护栏字段（safety_cushion / invest_ratio / optimization_goal / objectives /
  fast_track_whitelist）修改触发风险提示；
- 白名单增删；
- 未知字段 / 审计字段 → GuardError（三区权限由底层强制）。
"""
from __future__ import annotations

from core import audit as audit_io
from core import contract as contract_io
from modules import customize as mod_customize


def _changes_for_set(path: str, value) -> dict:
    return {"set": [{"path": path, "value": value}],
            "add_objective": [], "whitelist_add": [], "whitelist_remove": []}


# ---------------------------------------------------------------- 预览不落盘
def test_preview_does_not_write(tmp_data_dir, base_contract):
    before = dict(base_contract)
    res = mod_customize.preview(tmp_data_dir, _changes_for_set(
        "distribution_rules.invest_ratio", 0.3))
    assert res["ok"] and res["needs_confirm"] and res["preview"]
    assert "token" in res
    # 契约未被改动
    after = contract_io.read_contract(tmp_data_dir)
    assert after["distribution_rules"]["invest_ratio"] == before["distribution_rules"]["invest_ratio"]


def test_preview_shows_risk_for_invest_ratio(tmp_data_dir, base_contract):
    res = mod_customize.preview(tmp_data_dir, _changes_for_set(
        "distribution_rules.invest_ratio", 0.0))
    assert res["touched_guard_fields"] == ["distribution_rules"]
    assert any("invest_ratio 归零" in w for w in res["risk_warnings"])


def test_preview_shows_risk_for_safety_cushion_down(tmp_data_dir, base_contract):
    res = mod_customize.preview(tmp_data_dir, _changes_for_set(
        "safety_cushion.months", 2))
    assert "safety_cushion" in res["touched_guard_fields"]
    assert any("安全垫月数" in w for w in res["risk_warnings"])


def test_preview_shows_risk_for_optimization_goal(tmp_data_dir, base_contract):
    res = mod_customize.preview(tmp_data_dir, _changes_for_set(
        "optimization_goal", "wealth"))
    assert "optimization_goal" in res["touched_guard_fields"]
    assert any("wealth" in w for w in res["risk_warnings"])


def test_preview_non_guard_field_no_risk(tmp_data_dir, base_contract):
    res = mod_customize.preview(tmp_data_dir, _changes_for_set("mode", "ledger"))
    assert res["touched_guard_fields"] == []
    assert res["risk_warnings"] == []


# ---------------------------------------------------------------- 确认落盘
def test_apply_without_token_rejected(tmp_data_dir, base_contract):
    res = mod_customize.apply(
        tmp_data_dir, _changes_for_set("mode", "ledger"),
        confirm=True, token=None, reason="")
    assert not res["ok"] and res["error"] == "stale_token"


def test_apply_with_wrong_token_rejected(tmp_data_dir, base_contract):
    preview = mod_customize.preview(tmp_data_dir, _changes_for_set("mode", "ledger"))
    res = mod_customize.apply(
        tmp_data_dir, _changes_for_set("mode", "ledger"),
        confirm=True, token="deadbeefdeadbeef", reason="")
    assert not res["ok"] and res["error"] == "stale_token"
    assert res["expected_token"] == preview["token"]


def test_apply_with_token_writes_and_logs(tmp_data_dir, base_contract):
    # 非削弱（0.5→0.7 上调）走立即落盘路径；削弱路径见 test_customize_cooldown.py
    preview = mod_customize.preview(
        tmp_data_dir, _changes_for_set("distribution_rules.invest_ratio", 0.7))
    res = mod_customize.apply(
        tmp_data_dir, _changes_for_set("distribution_rules.invest_ratio", 0.7),
        confirm=True, token=preview["token"], reason="测试调参")
    assert res["ok"] and res["applied"]
    after = contract_io.read_contract(tmp_data_dir)
    assert after["distribution_rules"]["invest_ratio"] == 0.7
    # override_log 追加
    logs = audit_io.read_all(tmp_data_dir, "override_log")
    assert any(r.get("event") == "contract_customize" for r in logs)
    assert logs[-1]["reason"] == "测试调参"


def test_token_stale_after_contract_change(tmp_data_dir, base_contract):
    preview = mod_customize.preview(
        tmp_data_dir, _changes_for_set("mode", "ledger"))
    # 契约被别的写操作改动后，旧 token 应失效
    mod_customize.apply(
        tmp_data_dir, _changes_for_set("mode", "ledger"),
        confirm=True, token=preview["token"], reason="")
    res2 = mod_customize.apply(
        tmp_data_dir, _changes_for_set("mode", "ledger"),
        confirm=True, token=preview["token"], reason="")
    assert not res2["ok"] and res2["error"] == "stale_token"


# ---------------------------------------------------------------- 白名单增删
def test_whitelist_add_and_remove(tmp_data_dir, base_contract):
    add = {"set": [], "add_objective": [],
           "whitelist_add": [{"name": "宠物急诊", "per_tx_cap": 5000.0,
                              "annual_cap": 20000.0}],
           "whitelist_remove": []}
    preview = mod_customize.preview(tmp_data_dir, add)
    assert "fast_track_whitelist" in preview["touched_guard_fields"]
    res = mod_customize.apply(tmp_data_dir, add, confirm=True,
                              token=preview["token"], reason="加宠物急诊")
    after = contract_io.read_contract(tmp_data_dir)
    assert any(w["name"] == "宠物急诊" for w in after["fast_track_whitelist"])

    remove = {"set": [], "add_objective": [], "whitelist_add": [],
              "whitelist_remove": ["宠物急诊"]}
    p2 = mod_customize.preview(tmp_data_dir, remove)
    mod_customize.apply(tmp_data_dir, remove, confirm=True,
                        token=p2["token"], reason="撤宠物急诊")
    after2 = contract_io.read_contract(tmp_data_dir)
    assert not any(w["name"] == "宠物急诊" for w in after2["fast_track_whitelist"])


def test_whitelist_remove_missing_raises(tmp_data_dir, base_contract):
    remove = {"set": [], "add_objective": [], "whitelist_add": [],
              "whitelist_remove": ["不存在类目"]}
    import pytest
    with pytest.raises(ValueError):
        mod_customize.preview(tmp_data_dir, remove)


# ---------------------------------------------------------------- 目标新增
def test_add_objective(tmp_data_dir, base_contract):
    changes = {"set": [], "add_objective": ["买房:1000000:2030-01-01"],
               "whitelist_add": [], "whitelist_remove": []}
    preview = mod_customize.preview(tmp_data_dir, changes)
    assert "objectives" in preview["touched_guard_fields"]
    assert any("新增目标 买房" in w for w in preview["risk_warnings"])
    mod_customize.apply(tmp_data_dir, changes, confirm=True,
                        token=preview["token"], reason="加买房目标")
    after = contract_io.read_contract(tmp_data_dir)
    assert any(o["name"] == "买房" for o in after["objectives"])


# ---------------------------------------------------------------- 权限护栏
def test_unknown_field_guard(tmp_data_dir, base_contract):
    import pytest
    from core.contract import GuardError
    with pytest.raises(GuardError):
        mod_customize.preview(tmp_data_dir, _changes_for_set("not_a_field", 1))


def test_audit_field_guard(tmp_data_dir, base_contract):
    import pytest
    from core.contract import GuardError
    with pytest.raises(GuardError):
        mod_customize.preview(tmp_data_dir, _changes_for_set("approval_log", []))


def test_build_changes_requires_something(tmp_data_dir):
    import pytest
    from argparse import Namespace
    empty = Namespace(set=None, add_objective=None, whitelist_add=None,
                      per_tx_cap=None, annual_cap=None, whitelist_remove=None)
    with pytest.raises(ValueError):
        mod_customize.build_changes(empty)


def test_build_changes_whitelist_add_needs_caps(tmp_data_dir):
    import pytest
    from argparse import Namespace
    bad = Namespace(set=None, add_objective=None, whitelist_add="X",
                    per_tx_cap=None, annual_cap=None, whitelist_remove=None)
    with pytest.raises(ValueError):
        mod_customize.build_changes(bad)
