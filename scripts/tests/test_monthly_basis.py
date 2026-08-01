# -*- coding: utf-8 -*-
"""月净流入口径（毛/净）显示优化 · 引擎层测试（phase 1 纯展示层）。

守护：
- models.monthly_basis() 标记优先 + 旧契约迁移推断；
- models.monthly_net_effective() 净口径分解数学；
- initialize 默认置 gross_estimate；
- customize 补负债/刚性 → 标记置 net（仅展示，不进判定）；
- report 持久毛口径提示 + 净口径分解；
- judge inputs 携带 monthly_basis / monthly_net_effective。
"""
from __future__ import annotations

from datetime import date

from core import models
from core.contract import read_contract
from modules import customize as mod_customize
from modules.judge import judge
from modules.report import render_report

TODAY = date(2026, 7, 27)


# ── models.monthly_basis ───────────────────────────────────────
class TestMonthlyBasis:
    def test_explicit_true_is_gross(self):
        assert models.monthly_basis({"monthly_is_gross_estimate": True}) == "gross_estimate"

    def test_explicit_false_is_net(self):
        assert models.monthly_basis({"monthly_is_gross_estimate": False}) == "net"

    def test_missing_no_liabilities_is_gross(self):
        # 旧契约缺省 + 无负债/刚性 → 推断为毛口径
        assert models.monthly_basis({}) == "gross_estimate"

    def test_missing_with_liability_is_net(self):
        assert models.monthly_basis({"liabilities": [{"name": "x", "balance": 1}]}) == "net"

    def test_missing_with_rigid_is_net(self):
        assert models.monthly_basis({"rigid_annual_expenses": [{"name": "x", "amount": 1}]}) == "net"


# ── models.monthly_net_effective ───────────────────────────────
class TestMonthlyNetEffective:
    def test_no_obligations_net_equals_entered(self):
        eff = models.monthly_net_effective({"monthly_contribution": 8000})
        assert eff["entered"] == 8000
        assert eff["debt_monthly"] == 0
        assert eff["rigid_monthly"] == 0
        assert eff["net"] == 8000

    def test_deduction_math(self):
        c = {
            "monthly_contribution": 8000,
            "liabilities": [{"name": "房贷", "balance": 1000000, "monthly_payment": 5000}],
            "rigid_annual_expenses": [{"name": "保费", "amount": 12000}],
        }
        eff = models.monthly_net_effective(c)
        assert eff["debt_monthly"] == 5000
        assert eff["rigid_monthly"] == 1000.0  # 12000 / 12
        assert eff["net"] == 2000.0  # 8000 - 5000 - 1000


# ── initialize 默认 ─────────────────────────────────────────────
class TestInitDefaultBasis:
    def test_base_contract_flag_true(self, base_contract):
        assert base_contract.get("monthly_is_gross_estimate") is True

    def test_lazy_init_returns_gross_basis(self, tmp_data_dir):
        from modules.initialize import lazy_init
        r = lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                      objectives=[{"name": "FIRE", "target_amount": 3000000,
                                   "deadline": "2036-01-01"}], today=TODAY)
        assert r["ok"]
        assert r["monthly_basis"] == "gross_estimate"


# ── customize 补负债 → net（仅展示，不进判定）───────────────────
class TestCustomizeBasisFlip:
    def _liab_changes(self):
        return {"add_liability": [{"name": "房贷", "balance": 1000000,
                                   "monthly_payment": 5000, "annual_rate": 0.04}]}

    def test_preview_consequence_present(self, tmp_data_dir, base_contract):
        res = mod_customize.preview(tmp_data_dir, self._liab_changes())
        assert res["ok"]
        assert res["monthly_consequence"] is not None
        assert "净口径" in res["monthly_consequence"]["note"]

    def test_apply_flips_flag_to_net(self, tmp_data_dir, base_contract):
        changes = self._liab_changes()
        preview = mod_customize.preview(tmp_data_dir, changes)
        res = mod_customize.apply(tmp_data_dir, changes, confirm=True,
                                  token=preview["token"], reason="测试补负债")
        assert res["ok"] and res["applied"]
        c = read_contract(tmp_data_dir)
        assert c["monthly_is_gross_estimate"] is False
        assert res["monthly_consequence"] is not None

    def test_remove_liability_flips_back_to_gross(self, tmp_data_dir, base_contract):
        liab = self._liab_changes()
        p1 = mod_customize.preview(tmp_data_dir, liab)
        mod_customize.apply(tmp_data_dir, liab, confirm=True, token=p1["token"], reason="x")
        assert read_contract(tmp_data_dir)["monthly_is_gross_estimate"] is False
        rm = {"remove_liability": ["房贷"]}
        p2 = mod_customize.preview(tmp_data_dir, rm)
        mod_customize.apply(tmp_data_dir, rm, confirm=True, token=p2["token"], reason="x")
        assert read_contract(tmp_data_dir)["monthly_is_gross_estimate"] is True


# ── report 展示 ─────────────────────────────────────────────────
class TestReportBasisDisplay:
    def test_gross_warning_and_effective(self, base_contract):
        r = render_report(base_contract, [], today=TODAY)
        assert r["monthly_basis"] == "gross_estimate"
        assert any("毛口径" in n for n in r["notes"])
        assert "net" in r["monthly_net_effective"]
        # 无负债 → 净=毛
        assert r["monthly_net_effective"]["net"] == 8000

    def test_net_decomposition(self, tmp_data_dir, base_contract):
        changes = {
            "add_liability": [{"name": "房贷", "balance": 1000000,
                               "monthly_payment": 5000, "annual_rate": 0.04}],
            "add_rigid": [{"name": "保费", "amount": 12000}],
        }
        p = mod_customize.preview(tmp_data_dir, changes)
        mod_customize.apply(tmp_data_dir, changes, confirm=True, token=p["token"], reason="x")
        c = read_contract(tmp_data_dir)
        r = render_report(c, [], today=TODAY)
        assert r["monthly_basis"] == "net"
        eff = r["monthly_net_effective"]
        assert eff["debt_monthly"] == 5000
        assert eff["rigid_monthly"] == 1000.0
        assert eff["net"] == 2000.0
        # 毛口径提示不应出现
        assert not any("毛口径" in n for n in r["notes"])


# ── judge inputs 携带口径 ───────────────────────────────────────
class TestJudgeBasisInputs:
    def test_inputs_carry_basis(self, base_contract):
        r = judge(base_contract, amount=6000, category="合理享受", planned=False,
                  today=TODAY)
        assert r["ok"]
        assert r["inputs"]["monthly_basis"] == "gross_estimate"
        assert "net" in r["inputs"]["monthly_net_effective"]
