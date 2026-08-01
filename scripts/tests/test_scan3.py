# -*- coding: utf-8 -*-
"""第三轮扫描修复回归测试：N1/N2/N3/N4/N5 + R1/R2/R3。

与 test_ml_regressions.py（M/L 项）分离，专测本轮 7 个修复点。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from core import audit as audit_io
from core import formulas as F
from core.contract import read_contract, write_contract
from modules import calibrate as mod_cal
from modules import governance as mod_gov
from modules import import_asset as mod_import
from modules import judge as mod_judge
from modules.initialize import lazy_init
from modules.judge import _boost_pct_to_frac


@pytest.fixture()
def cdir(tmp_path):
    d = tmp_path / "selftrust-data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _init(cdir, today=date(2026, 7, 27)):
    r = lazy_init(cdir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=today)
    assert r["ok"], r
    return read_contract(cdir)


def _candidates(corpus=150000, monthly=8000, liabilities=None, rigid=None):
    return {"corpus": corpus, "monthly_contribution": monthly,
            "liabilities": liabilities or [], "rigid_annual_expenses": rigid or [],
            "suspicious": [], "summary": {}}


# --------------------------------------------------------------------------- N1
class TestN1UppercaseCushionMode:
    def test_f1_uppercase_mode(self):
        """F.f1_effective_cushion 须对 mode 大小写不敏感（L5/N1）。"""
        assert F.f1_effective_cushion("Months", 5000, months=6) == 30000.0
        assert F.f1_effective_cushion("MONTHS", 5000, months=6) == 30000.0

    def test_judge_uppercase_mode_ok(self, cdir):
        """原 bug：preview（_eff_cushion 已 lower）通过，但 judge（f1）报错。
        f1 已补 .lower()，大写 mode 下 judge 应正常返回判定。"""
        c = _init(cdir)
        c["safety_cushion"]["mode"] = "Months"
        r = mod_judge.judge(c, amount=1000, category="合理享受",
                            planned=False, today=date(2026, 7, 27))
        assert r["ok"] and "decision" in r


# --------------------------------------------------------------------------- N2
class TestN2ReconcileWithdrawnCount:
    def test_withdrawn_excluded_from_count_and_total(self, cdir):
        c = _init(cdir)
        c["pending_spends"] = [
            {"request_id": "a", "time": "2026-07-27T00:00:00", "amount": 100.0,
             "actual_cash_out": 100.0, "category": "x", "planned": False,
             "scene": "A", "financed_amount": 0.0, "status": "approved"},
            {"request_id": "b", "time": "2026-07-27T00:00:00", "amount": 200.0,
             "actual_cash_out": 200.0, "category": "y", "planned": False,
             "scene": "A", "financed_amount": 0.0, "status": "withdrawn"},
        ]
        write_contract(cdir, c, actor="engine")
        res = mod_gov.reconcile(cdir, today=date(2026, 7, 27))
        cleared = res["pending_spends_cleared"]
        # N2：count 与 total 口径一致，均排除 withdrawn
        assert cleared["count"] == 1
        assert cleared["total_actual_cash_out"] == 100.0


# --------------------------------------------------------------------------- N3 / N4
class TestN3N4AuditTimeDeterministic:
    def test_now_iso_replay_deterministic_midnight(self):
        """N4：重放（显式 past today）时间部分固定午夜，秒级可复现。"""
        d = date(2026, 7, 27)
        assert audit_io.now_iso(d) == "2026-07-27T00:00:00"
        assert audit_io.now_iso(d) == audit_io.now_iso(d)  # 可复现

    def test_now_iso_real_run_keeps_wall_clock(self):
        """真实运行（today=None）保留真实墙钟日期。"""
        ts = audit_io.now_iso(None)
        assert ts.startswith(date.today().isoformat())

    def test_transition_audit_time_uses_today(self, cdir):
        """N3：归档审计时间对齐逻辑 today（且因 today≠真实今日而确定性午夜）。"""
        _init(cdir)
        mod_cal.transition_objective(cdir, "FIRE", "archived", confirm=True,
                                     today=date(2026, 7, 27))
        recs = audit_io.read_all(cdir, "approval_log")
        ev = [r for r in recs if r.get("event") == "objective_archived"]
        assert ev, "应有归档审计记录"
        assert ev[-1]["time"] == "2026-07-27T00:00:00"


# --------------------------------------------------------------------------- N5
class TestN5BoostPctSemantics:
    def test_pct_to_frac_valid(self):
        assert _boost_pct_to_frac(15) == 0.15
        assert _boost_pct_to_frac(0) == 0.0
        assert _boost_pct_to_frac(100) == 1.0

    def test_pct_to_frac_rejects_ratio_misuse(self):
        """N5：误传比率（0.15）或越界（150）应报错，避免静默误用。"""
        with pytest.raises(ValueError):
            _boost_pct_to_frac(0.15)
        with pytest.raises(ValueError):
            _boost_pct_to_frac(150)


# --------------------------------------------------------------------------- R1
class TestR1RebalanceOverrideApplied:
    def test_income_drop_relaxes_invest_ratio(self, cdir):
        c = _init(cdir)
        c["rebalance_override"] = {
            "month": "2026-07", "reason": "income_drop", "boosts": [],
            "invest_ratio_adj": -0.10, "approval_rate_adj": 0.0,
            "flex": None, "expire": "次月",
        }
        r = mod_judge.judge(c, amount=1000, category="合理享受",
                            planned=False, today=date(2026, 7, 27))
        oa = r["optimization_applied"]
        assert oa["rebalance_override"] is not None
        ir = c["distribution_rules"]["invest_ratio"]
        assert oa["effective_invest_ratio"] == pytest.approx(ir - 0.10)
        assert oa["effective_invest_ratio"] < ir

    def test_approval_tightening_raises_hurdle(self, cdir):
        c = _init(cdir)
        c["rebalance_override"] = {
            "month": "2026-07", "reason": "lag_streak", "boosts": [],
            "invest_ratio_adj": 0.0, "approval_rate_adj": -0.30,
            "flex": None, "expire": "次月",
        }
        r = mod_judge.judge(c, amount=1000, category="合理享受",
                            planned=False, today=date(2026, 7, 27))
        oa = r["optimization_applied"]
        assert oa["approval_adj"] == -0.30
        assert oa["judge_cushion_eff"] > oa["judge_cushion"]

    def test_boost_reduces_lagging_objective_delay(self, cdir):
        c = _init(cdir)
        # 无 boost 基线
        r0 = mod_judge.judge(c, amount=80000, category="合理享受",
                             planned=False, today=date(2026, 7, 27))

        def _delay(res):
            for im in res["impacted_objectives"]:
                if im["name"] == "FIRE":
                    return im["delay_months_real"]
            return None

        d0 = _delay(r0)
        # 加 boost（投资加成 15%）
        c["rebalance_override"] = {
            "month": "2026-07", "reason": "lag_streak",
            "boosts": [{"obj": "FIRE", "invest_boost_pct": 15}],
            "invest_ratio_adj": 0.0, "approval_rate_adj": 0.0,
            "flex": None, "expire": "次月",
        }
        r1 = mod_judge.judge(c, amount=80000, category="合理享受",
                             planned=False, today=date(2026, 7, 27))
        d1 = _delay(r1)
        if d0 is None:
            pytest.skip("FIRE 无 impact，无法对比（不应发生）")
        # boost 后真实延时应更小，或不再被判定为 impacted
        assert d1 is None or d1 < d0


# --------------------------------------------------------------------------- R2
class TestR2ArchivedWeightReleased:
    def test_archived_zeroes_weight(self, cdir):
        before = _init(cdir)["objectives"][0]["weight"]
        r = mod_cal.transition_objective(cdir, "FIRE", "archived", confirm=True,
                                         today=date(2026, 7, 27))
        assert r["ok"]
        assert r["released_weight"] == before  # 返回释放前的原权重
        assert read_contract(cdir)["objectives"][0]["weight"] == 0


# --------------------------------------------------------------------------- R3
class TestR3StageImportNoOverwrite:
    def test_duplicate_stage_rejected(self, cdir):
        c = _init(cdir)
        res1 = mod_import.stage_import(c, _candidates(), "x")
        assert res1["ok"] and res1["needs_confirm"]
        res2 = mod_import.stage_import(c, _candidates(), "x")
        assert not res2["ok"] and res2["error"] == "already_staged"


# --------------------------------------------------------------------------- N5/R1
def test_boost_map_merges_duplicate_objs(base_contract):
    # #3 修复：rebalance_override.boosts 同名 obj 重复条目须求和合并，
    # 而非 dict comprehension 静默覆盖（覆盖会丢失一笔加成且零告警）。
    import copy
    c_dup = copy.deepcopy(base_contract)
    c_dup["rebalance_override"] = {
        "month": "2026-07", "reason": "x",
        "boosts": [{"obj": "FIRE", "invest_boost_pct": 15},
                   {"obj": "FIRE", "invest_boost_pct": 10}],
        "invest_ratio_adj": 0.0, "approval_rate_adj": 0.0, "flex": None, "expire": "次月"}
    c_uniq = copy.deepcopy(base_contract)
    c_uniq["rebalance_override"] = {
        "month": "2026-07", "reason": "x",
        "boosts": [{"obj": "FIRE", "invest_boost_pct": 15}],
        "invest_ratio_adj": 0.0, "approval_rate_adj": 0.0, "flex": None, "expire": "次月"}
    r_dup = mod_judge.judge(c_dup, amount=6000, category="合理享受",
                            planned=False, today=date(2026, 7, 27))
    r_uniq = mod_judge.judge(c_uniq, amount=6000, category="合理享受",
                             planned=False, today=date(2026, 7, 27))
    warnings = r_dup["optimization_applied"]["boost_warnings"]
    assert warnings, "同名 obj 重复应发告警"
    assert any("FIRE" in w and "合并" in w for w in warnings)
    assert r_uniq["optimization_applied"]["boost_warnings"] == [], "唯一 obj 不应告警"
