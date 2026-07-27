# -*- coding: utf-8 -*-
"""负债/房贷建模测试：A 净资产口径 + 负债录入；B 融资购房模式 + 购房落账。

工程规范 #8：全部用临时 data-dir，不碰真实契约。
"""
from __future__ import annotations

import types

from core import contract as contract_io
from modules import customize as cz
from modules import judge as mod_judge


def _contract(corpus: float, liabilities: list, monthly: float = 8000) -> dict:
    """最小契约 dict（供 judge 纯函数直接调用，验证口径）。"""
    return {
        "corpus": corpus,
        "liabilities": liabilities,
        "rigid_annual_expenses": [],
        "monthly_contribution": monthly,
        "safety_cushion": {"mode": "months", "months": 6,
                            "fixed": 100000, "ratio": 0.2},
        "cooldown_days": 3,
        "cooldown_threshold": "auto",
        "distribution_rules": {
            "invest_ratio": 0.5,
            "calc_params": {"inflation": 0.025, "drawdown_factor": 0.10,
                             "r_gross": 0.05},
            "living_baseline": {"mode": "auto", "manual": 0,
                                 "history3m_value": None},
        },
        "optimization_goal": "balanced",
        "objectives": [],
        "fast_track_whitelist": [],
    }


# ============================================================ A1 净资产口径
def test_net_assets_basis_without_liability():
    """无负债：15万支出对 20万 corpus → 净资产口径 remaining=5万 ≥ 垫 → A。"""
    c = _contract(200000, [])
    r = mod_judge.judge(c, amount=150000, category="合理享受", planned=False)
    assert r["decision"]["scene"] == "A"
    assert r["inputs"]["remaining_after"] == 50000.0


def test_net_assets_basis_with_liability_rejects():
    """同 corpus=20万 但负债 10万 → 净资产=10万，15万支出 remaining=-5万 → C。"""
    c = _contract(200000, [{"name": "房贷", "balance": 100000,
                             "monthly_payment": 5000, "annual_rate": 0.04}])
    r = mod_judge.judge(c, amount=150000, category="合理享受", planned=False)
    assert r["decision"]["scene"] == "C"
    assert r["inputs"]["remaining_after"] == -50000.0


# ============================================================ A2 负债录入
def _changes(**kw) -> dict:
    base = {"set": [], "add_objective": [], "whitelist_add": [],
             "whitelist_remove": [], "add_liability": [], "remove_liability": [],
             "add_rigid": [], "remove_rigid": [], "record_home_purchase": None}
    base.update(kw)
    return base


def test_customize_add_liability_and_judge_factors_it(tmp_data_dir, base_contract):
    """customize 增负债 → 落盘；随后 judge 同笔支出因净资产口径变 C。"""
    changes = _changes(add_liability=[{
        "name": "房贷", "balance": 800000, "monthly_payment": 5000,
        "annual_rate": 0.04}])
    pre = cz.preview(tmp_data_dir, changes)
    res = cz.apply(tmp_data_dir, changes, confirm=True, token=pre["token"],
                   reason="录入房贷")
    assert res["ok"] and res["applied"]
    c = contract_io.read_contract(tmp_data_dir)
    assert any(l["name"] == "房贷" and l["balance"] == 800000
               for l in c["liabilities"])
    # 同 corpus=20万，负债 80万 → 净资产=-60万，15万支出必 C（印证 A1 口径已生效）
    r = mod_judge.judge(c, amount=150000, category="投资", planned=False)
    assert r["decision"]["scene"] == "C"


def test_customize_remove_liability(tmp_data_dir, base_contract):
    changes = _changes(add_liability=[{
        "name": "车贷", "balance": 100000, "monthly_payment": 2000,
        "annual_rate": 0.05}])
    pre = cz.preview(tmp_data_dir, changes)
    cz.apply(tmp_data_dir, changes, confirm=True, token=pre["token"], reason="x")
    changes2 = _changes(remove_liability=["车贷"])
    pre2 = cz.preview(tmp_data_dir, changes2)
    cz.apply(tmp_data_dir, changes2, confirm=True, token=pre2["token"], reason="x")
    c = contract_io.read_contract(tmp_data_dir)
    assert not any(l["name"] == "车贷" for l in c["liabilities"])


def test_customize_add_rigid(tmp_data_dir, base_contract):
    changes = _changes(add_rigid=[{"name": "保费", "amount": 12000,
                                    "due_month": 3}])
    pre = cz.preview(tmp_data_dir, changes)
    res = cz.apply(tmp_data_dir, changes, confirm=True, token=pre["token"],
                   reason="x")
    assert res["applied"]
    c = contract_io.read_contract(tmp_data_dir)
    assert any(r["name"] == "保费" and r["amount"] == 12000
               for r in c["rigid_annual_expenses"])


# ============================================================ B1 融资购房
def test_financed_purchase_approved_when_feasible():
    """corpus=50万 / 月净 8000；100万房 70万贷(首付30万) → 流动垫足 + 月供可覆盖 → A。"""
    c = _contract(500000, [])
    r = mod_judge.judge(c, amount=1000000, category="投资", planned=False,
                        financed_amount=700000)
    assert r["decision"]["scene"] == "A"
    inp = r["inputs"]
    assert inp["financed"] is True
    assert inp["down_payment"] == 300000.0
    assert inp["actual_cash_out"] == 300000.0
    assert inp["debt_service_ok"] is True
    # 月供 ≈ 3341.91（700K/30y/4%）
    assert abs(inp["mortgage_monthly"] - 3341.91) < 1.0


def test_financed_purchase_rejected_when_down_exceeds_liquidity():
    """corpus=20万 / 月净 8000；100万房 70万贷(首付30万) → 首付超流动 → C。"""
    c = _contract(200000, [])
    r = mod_judge.judge(c, amount=1000000, category="投资", planned=False,
                        financed_amount=700000)
    assert r["decision"]["scene"] == "C"
    assert "安全垫" in r["decision"]["summary"]


def test_financed_purchase_rejected_when_debt_service_unsafe():
    """corpus=50万 / 月净 2000；100万房 90万贷 → 月供>月净 → C（债务无法覆盖）。"""
    c = _contract(500000, [], monthly=2000)
    r = mod_judge.judge(c, amount=1000000, category="投资", planned=False,
                        financed_amount=900000)
    assert r["decision"]["scene"] == "C"
    assert "月供" in r["decision"]["summary"]
    assert r["inputs"]["debt_service_ok"] is False


def test_financed_cooldown_uses_down_payment(tmp_data_dir, base_contract):
    """融资购房提交：冷静期触发额用首付(而非全额)。"""
    # base_contract corpus=20万；首付30万触发冷却（> 阈值），全额不会因阈值不同
    res = mod_judge.submit(tmp_data_dir, amount=1000000, category="投资",
                           planned=False, financed_amount=700000)
    assert res["ok"]
    # 首付 30万 > 阈值(auto≈24000) → 触发冷静期
    assert res["cooldown"]["triggered"] is True
    assert res["decision"]["scene"] == "C"


# ============================================================ B2 购房落账
def test_record_home_purchase_persists(tmp_data_dir, base_contract):
    """--record-home-purchase 1000000:0.3 → corpus-=30万 + 房贷负债 70万(月供~3341.91)。"""
    # 资金池设足（M4：首付须 ≤ 资金池），聚焦落账正确性
    c0 = contract_io.read_contract(tmp_data_dir)
    c0["corpus"] = 1_000_000
    contract_io.write_contract(tmp_data_dir, c0, actor="configurator", confirm=True)

    args = types.SimpleNamespace(
        set=None, add_objective=None, whitelist_add=None, per_tx_cap=None,
        annual_cap=None, whitelist_remove=None, add_liability=None,
        remove_liability=None, add_rigid=None, remove_rigid=None,
        record_home_purchase=["1000000:0.3"])
    changes = cz.build_changes(args)
    hp = changes["record_home_purchase"]
    assert hp["down_payment"] == 300000.0
    assert hp["financed"] == 700000.0
    assert abs(hp["mortgage_monthly"] - 3341.91) < 1.0

    pre = cz.preview(tmp_data_dir, changes)
    res = cz.apply(tmp_data_dir, changes, confirm=True, token=pre["token"],
                   reason="记录购房")
    assert res["ok"] and res["applied"]
    c = contract_io.read_contract(tmp_data_dir)
    assert c["corpus"] == 700000.0   # 1,000,000 - 300,000（M4：首付不得超资金池）
    assert any(l["name"] == "房贷" and l["balance"] == 700000
               and abs(l["monthly_payment"] - 3341.91) < 1.0
               for l in c["liabilities"])
