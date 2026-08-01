# -*- coding: utf-8 -*-
"""§7.3 第三方导入测试：CSV 解析 / 候选推导 / 暂存 / 拦截 / 确认 / 取消 / token。

用法：python -m pytest scripts/tests/test_import_asset.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from modules import import_asset as mod
from cli import build_parser, cmd_import_asset
from core import audit as audit_io
from core import contract as contract_io


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


def test_confirm_after_live_change_rejected(base_contract):
    # stage 后若 live 契约被改动（如中途 customize），confirm 须拒绝，
    # 防陈旧暂存覆盖 live 编辑（M9 加固）
    tok = mod.stage_import(base_contract, _candidates(), "x")["token"]
    base_contract["corpus"] = base_contract["corpus"] + 1   # 模拟 customize 改动
    r = mod.confirm_import(base_contract, tok)
    assert r["ok"] is False and r["error"] == "contract_changed"
    assert base_contract["pending_import"] is not None      # 暂存仍在，未误落盘


# ---------------------------------------------------------------- #1 修复：来源缺类不得静默清空 live
def _candidates_with_provided(corpus=150000, monthly=8000, liabilities=None, rigid=None,
                              provided=None):
    c = _candidates(corpus, monthly, liabilities, rigid)
    c["provided"] = provided or {
        "corpus": True, "monthly_contribution": True,
        "liabilities": True, "rigid_annual_expenses": True,
    }
    return c


def _seed_live_liab_rigid(contract):
    contract["liabilities"] = [{"name": "旧房贷", "balance": 500000,
                                "monthly_payment": 3000.0, "annual_rate": 0.0}]
    contract["rigid_annual_expenses"] = [{"name": "旧保费", "amount": 6000, "due_month": None}]
    contract["monthly_contribution"] = 8000


def test_csv_assets_only_preserves_live_liabilities(base_contract):
    # 契约已录入房贷/保费；CSV 只含资产行（无 liability/rigid 行）
    _seed_live_liab_rigid(base_contract)
    rows = [{"name": "招行", "balance": 120000, "kind": "asset", "monthly": 0},
            {"name": "支付宝", "balance": 30000, "kind": "asset", "monthly": 0}]
    cand = mod.compute_candidates(rows)            # provided.liabilities/rigid = False
    assert cand["provided"]["liabilities"] is False
    assert cand["provided"]["rigid_annual_expenses"] is False
    tok = mod.stage_import(base_contract, cand, "qianji")["token"]
    r = mod.confirm_import(base_contract, tok)
    assert r["ok"]
    # 资产更新，负债/刚性/月供保留旧值，未被清空（#1）
    assert base_contract["corpus"] == 150000
    assert len(base_contract["liabilities"]) == 1
    assert base_contract["liabilities"][0]["name"] == "旧房贷"
    assert base_contract["rigid_annual_expenses"][0]["name"] == "旧保费"
    assert base_contract["monthly_contribution"] == 8000


def test_csv_with_liability_row_overwrites(base_contract):
    _seed_live_liab_rigid(base_contract)
    rows = [{"name": "招行", "balance": 150000, "kind": "asset", "monthly": 0},
            {"name": "新房贷", "balance": 700000, "kind": "liability", "monthly": 3341.91}]
    cand = mod.compute_candidates(rows)
    assert cand["provided"]["liabilities"] is True
    tok = mod.stage_import(base_contract, cand, "qianji")["token"]
    mod.confirm_import(base_contract, tok)
    assert len(base_contract["liabilities"]) == 1
    assert base_contract["liabilities"][0]["name"] == "新房贷"   # 显式提供 → 覆盖


def test_manual_corpus_only_preserves_others(base_contract):
    _seed_live_liab_rigid(base_contract)
    cand = _candidates_with_provided(
        corpus=180000, provided={"corpus": True, "monthly_contribution": False,
                                  "liabilities": False, "rigid_annual_expenses": False})
    tok = mod.stage_import(base_contract, cand, "manual")["token"]
    r = mod.confirm_import(base_contract, tok)     # 无 corrections
    assert r["ok"]
    assert base_contract["corpus"] == 180000
    assert base_contract["liabilities"][0]["name"] == "旧房贷"
    assert base_contract["rigid_annual_expenses"][0]["name"] == "旧保费"
    assert base_contract["monthly_contribution"] == 8000


# ---------------------------------------------------------------- H1 修复：同名重复行去重合并
def test_duplicate_asset_rows_deduped():
    # 同一账户在 CSV 中重复列出 → 不应双倍计入 corpus（修复前 = 1,000,000）
    rows = [
        {"name": "招行", "balance": 500000, "kind": "asset", "monthly": 0},
        {"name": "招行", "balance": 500000, "kind": "asset", "monthly": 0},
    ]
    c = mod.compute_candidates(rows)
    assert c["corpus"] == 500000
    assert c["warnings"] == []                      # 完全重复静默丢弃，无告警


def test_duplicate_liability_rows_deduped():
    rows = [
        {"name": "房贷", "balance": 800000, "kind": "liability", "monthly": 5000},
        {"name": "房贷", "balance": 800000, "kind": "liability", "monthly": 5000},
    ]
    c = mod.compute_candidates(rows)
    assert len(c["liabilities"]) == 1
    assert c["liabilities"][0]["balance"] == 800000
    assert c["liabilities"][0]["monthly_payment"] == 5000


def test_same_name_diff_balance_merges_with_warning():
    # 同账户余额不同 → 取「最新出现值」覆盖（不再求和翻倍）+ 告警交由人工核对（M8）
    rows = [
        {"name": "招行", "balance": 500000, "kind": "asset", "monthly": 0},
        {"name": "招行", "balance": 200000, "kind": "asset", "monthly": 0},
    ]
    c = mod.compute_candidates(rows)
    assert c["corpus"] == 200000   # 后出现者覆盖（最新快照），不再 500k+200k 翻倍
    assert any(w["name"] == "招行" for w in c["warnings"])


def test_duplicate_rows_in_csv_deduped(tmp_path):
    # 端到端：CSV 里招行/房贷各重复一行，导入后 cor/负债不翻倍
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind,monthly", [
        "招行,500000,asset,", "招行,500000,asset,",
        "房贷,800000,liability,5000", "房贷,800000,liability,5000",
    ])
    rows = mod.parse_balances_csv(f)
    c = mod.compute_candidates(rows)
    assert c["corpus"] == 500000
    assert len(c["liabilities"]) == 1 and c["liabilities"][0]["balance"] == 800000


# ---------------------------------------------------------------- M1：金额精度（币种/千分位/容差）
def test_parse_money_strips_currency_and_thousands():
    # 容忍 ¥ $ ￥ 与千分位逗号（M2 币种容错同源）
    assert mod.parse_money("¥1,000,000") == 1000000.0
    assert mod.parse_money("$800,000.50") == 800000.50
    assert mod.parse_money("￥500000") == 500000.0
    assert mod.parse_money(" 3000 ") == 3000.0
    assert mod.parse_money("0") == 0.0


def test_parse_money_invalid_raises():
    import pytest
    with pytest.raises(ValueError):
        mod.parse_money("abc")


def test_near_equal_balances_treated_as_duplicate():
    # 浮点亚分差异不应误判为非重复行（M1 容差比较）
    rows = [
        {"name": "招行", "balance": 500000.0, "kind": "asset", "monthly": 0},
        {"name": "招行", "balance": 500000.0001, "kind": "asset", "monthly": 0},
    ]
    c = mod.compute_candidates(rows)
    assert c["corpus"] == 500000
    assert c["warnings"] == []                       # 视为完全重复，无告警


def test_parse_csv_currency_and_thousands(tmp_path):
    # M2：CSV 余额带币种符号/千分位 → 正确解析，不报错
    # （含逗号的字段须按 CSV 规范加引号，否则会被当成分隔符）
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind,monthly", [
        '招行,"¥1,000,000",asset,',
        '房贷,"$800,000",liability,5000',
    ])
    rows = mod.parse_balances_csv(f)
    assert rows[0]["balance"] == 1000000.0
    assert rows[1]["balance"] == 800000.0


# ---------------------------------------------------------------- M2：流水日期多格式容错
def test_parse_flows_multi_date_format(tmp_path):
    f = _write_csv(tmp_path / "f.csv", "date,amount", [
        "2026/01/05,8000",          # 斜杠
        "2026.02.05,9000",          # 点
        "2026-03-05,7000",          # 标准
    ])
    flows = mod.parse_flows_csv(f)
    months = sorted(ds[:7] for ds, _ in flows)
    assert months == ["2026-01", "2026-02", "2026-03"]


def test_parse_flows_bad_date_rejected(tmp_path):
    import pytest
    f = _write_csv(tmp_path / "f.csv", "date,amount", ["03/05/2026,8000"])  # 美式歧义
    with pytest.raises(ValueError):
        mod.parse_flows_csv(f)


# ---------------------------------------------------------------- M3：rigid due_month 透传
def test_rigid_due_month_parsed(tmp_path):
    f = _write_csv(tmp_path / "b.csv", "name,balance,kind,monthly,due_month", [
        "保费,6000,rigid,,3",
        "旅费,12000,rigid,,",
    ])
    rows = mod.parse_balances_csv(f)
    c = mod.compute_candidates(rows)
    by_name = {r["name"]: r for r in c["rigid_annual_expenses"]}
    assert by_name["保费"]["due_month"] == 3          # M3：到期月透传（不再恒 None）
    assert by_name["旅费"]["due_month"] is None        # 缺省仍 None


# ---------------------------------------------------------------- M6：部分负债修正按名合并
def test_partial_liability_correction_merges_not_replaces(base_contract):
    # 暂存含 房贷 + 车贷；仅修正 房贷 余额，车贷应保留（不被整表覆盖丢掉）
    cand = _candidates(
        liabilities=[
            {"name": "房贷", "balance": 700000, "monthly_payment": 3341.91, "annual_rate": 0.0},
            {"name": "车贷", "balance": 200000, "monthly_payment": 4000, "annual_rate": 0.0},
        ])
    tok = mod.stage_import(base_contract, cand, "x")["token"]
    r = mod.confirm_import(base_contract, tok, corrections={
        "liabilities": [{"name": "房贷", "balance": 750000,
                         "monthly_payment": 3500.0, "annual_rate": 0.0}]})
    assert r["ok"]
    by_name = {l["name"]: l for l in base_contract["liabilities"]}
    assert set(by_name) == {"房贷", "车贷"}            # 车贷未丢
    assert by_name["房贷"]["balance"] == 750000         # 修正生效
    assert by_name["车贷"]["balance"] == 200000         # 未提及者保留


# ---------------------------------------------------------------- #2 修复：审计时间对齐逻辑 today
def test_import_confirm_audit_time_uses_logical_today(base_contract, tmp_data_dir):
    # 修复前 _now_import() 用 datetime.now()，--today 重放下审计时间不一致；
    # 现改用 audit_io.now_iso(_today(args))，须对齐逻辑 today。
    logical = "2026-07-27"
    stage_args = build_parser().parse_args([
        "--data-dir", str(tmp_data_dir), "--today", logical,
        "import-asset", "--corpus", "150000", "--monthly", "8000"])
    assert cmd_import_asset(stage_args) == 0
    tok = contract_io.read_contract(tmp_data_dir)["pending_import"]["token"]
    confirm_args = build_parser().parse_args([
        "--data-dir", str(tmp_data_dir), "--today", logical,
        "import-asset", "--confirm", "--token", tok])
    assert cmd_import_asset(confirm_args) == 0
    logs = audit_io.read_all(tmp_data_dir, "override_log")
    confirmed = [l for l in logs if l.get("event") == "asset_import_confirmed"]
    assert confirmed, "应有确认审计条目"
    assert confirmed[0]["time"] == "2026-07-27T00:00:00", confirmed[0]
