# -*- coding: utf-8 -*-
"""§7.3 第三方导入测试：CSV 解析 / 候选推导 / 暂存 / 拦截 / 确认 / 取消 / token。

用法：python -m pytest scripts/tests/test_import_asset.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules import import_asset as mod


def _write_csv(path: Path, header: str, rows: list[str]) -> Path:
    path.write_text(header + "\n" + "\n".join(rows), encoding="utf-8")
    return path


# ---------------------------------------------------------------- CSV 解析
def test_parse_balances_csv(tmp_path):
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind,monthly", [
        "招行,120000,asset,",
        "支付宝,30000,asset,",
        "房贷,800000,liability,3341.91",
        "保险,6000,rigid,",
    ])
    rows = mod.parse_balances_csv(f)
    assert len(rows) == 4
    assets = [r for r in rows if r["kind"] == "asset"]
    assert sum(r["balance"] for r in assets) == 150000
    lia = [r for r in rows if r["kind"] == "liability"][0]
    assert lia["balance"] == 800000 and lia["monthly"] == 3341.91
    rigid = [r for r in rows if r["kind"] == "rigid"][0]
    assert rigid["balance"] == 6000


def test_parse_balances_csv_bad_kind(tmp_path):
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind", ["x,1,foo"])
    with pytest.raises(ValueError):
        mod.parse_balances_csv(f)


def test_parse_balances_csv_empty(tmp_path):
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind", [])
    with pytest.raises(ValueError):
        mod.parse_balances_csv(f)


# ---------------------------------------------------------------- 候选推导
def test_compute_candidates_basic():
    rows = [
        {"name": "a", "balance": 100000, "kind": "asset", "monthly": 0},
        {"name": "b", "balance": 50000, "kind": "asset", "monthly": 0},
        {"name": "房贷", "balance": 700000, "kind": "liability", "monthly": 3341.91},
        {"name": "保险", "balance": 6000, "kind": "rigid", "monthly": 0},
    ]
    c = mod.compute_candidates(rows)
    assert c["corpus"] == 150000
    assert len(c["liabilities"]) == 1 and c["liabilities"][0]["balance"] == 700000
    assert c["rigid_annual_expenses"][0]["amount"] == 6000
    assert c["monthly_contribution"] == 0  # 无流水


def test_compute_candidates_flows_avg_and_suspicious():
    rows = [{"name": "a", "balance": 100000, "kind": "asset", "monthly": 0}]
    flows = [
        ("2026-01-01", 8000), ("2026-01-15", -2000),   # net 6000
        ("2026-02-01", 8000), ("2026-02-15", -2000),   # net 6000
        ("2026-03-01", 8000), ("2026-03-15", -2000),   # net 6000
        ("2026-04-01", 80000),                          # 离群
    ]
    c = mod.compute_candidates(rows, flows)
    expected_avg = (6000 * 3 + 80000) / 4
    assert abs(c["monthly_contribution"] - expected_avg) < 1e-6
    assert any(s["month"] == "2026-04" for s in c["suspicious"])


# ---------------------------------------------------------------- 暂存 / 状态机
def _candidates(corpus=150000, monthly=8000, liabilities=None, rigid=None):
    return {
        "corpus": corpus, "monthly_contribution": monthly,
        "liabilities": liabilities or [],
        "rigid_annual_expenses": rigid or [],
        "suspicious": [], "summary": {},
    }


def test_stage_sets_pending_and_keeps_live_corpus(base_contract):
    res = mod.stage_import(base_contract, _candidates(), "custom-csv")
    assert res["ok"] and res["needs_confirm"]
    assert base_contract["corpus_status"] == "imported_pending"
    assert base_contract["corpus"] == 200000          # live 不动
    assert base_contract["pending_import"]["token"] == res["token"]


def test_judge_blocked_under_imported_pending(base_contract):
    from modules import judge as mod_judge
    mod.stage_import(base_contract, _candidates(), "x")
    r = mod_judge.judge(base_contract, amount=6000, category="合理享受",
                        planned=False, today=None)
    assert r["ok"] is False and r["error"] == "import_pending"


def test_confirm_applies_and_clears(base_contract):
    cand = _candidates(
        liabilities=[{"name": "房贷", "balance": 700000,
                      "monthly_payment": 3341.91, "annual_rate": 0.0}])
    tok = mod.stage_import(base_contract, cand, "x")["token"]
    r = mod.confirm_import(base_contract, tok)
    assert r["ok"] and r["confirmed"]
    assert base_contract["corpus_status"] == "imported_confirmed"
    assert base_contract["corpus"] == 150000
    assert base_contract["liabilities"][0]["balance"] == 700000
    assert base_contract["pending_import"] is None


def test_confirm_with_corrections(base_contract):
    tok = mod.stage_import(base_contract, _candidates(), "x")["token"]
    r = mod.confirm_import(base_contract, tok, {"corpus": 145000})
    assert base_contract["corpus"] == 145000           # 修正生效
    assert base_contract["monthly_contribution"] == 8000


def test_cancel_restores_prior_and_touchless(base_contract):
    assert base_contract["corpus_status"] == "manual"
    tok = mod.stage_import(base_contract, _candidates(), "x")["token"]
    r = mod.cancel_import(base_contract, tok)
    assert r["ok"] and base_contract["corpus_status"] == "manual"
    assert base_contract["corpus"] == 200000           # live 未污染
    assert base_contract["pending_import"] is None


def test_wrong_token_rejected(base_contract):
    mod.stage_import(base_contract, _candidates(), "x")
    r1 = mod.confirm_import(base_contract, "deadbeef")
    assert r1["ok"] is False and r1["error"] == "bad_token"
    r2 = mod.cancel_import(base_contract, "deadbeef")
    assert r2["ok"] is False and r2["error"] == "bad_token"
