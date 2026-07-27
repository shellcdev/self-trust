# -*- coding: utf-8 -*-
"""judge 补全测试：lag 恶化 / optimization_goal 调度 / imported_pending 拦截 /
pending_requests 入队落盘（§4.4 / §5.1 / §7 / §7.3）。
"""
from __future__ import annotations

import copy
from datetime import date

from core import audit
from core.contract import read_contract, write_contract
from modules.judge import judge, submit

TODAY = date(2026, 7, 27)


class TestImportedPendingGate:
    """§7.3 corpus_status=imported_pending → 拒绝一切审批。"""

    def test_import_pending_blocks_judge(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["corpus_status"] = "imported_pending"
        r = judge(c, amount=100, category="食品", planned=True, today=TODAY)
        assert r["ok"] is False and r["error"] == "import_pending"

    def test_import_confirmed_allows(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["corpus_status"] = "imported_confirmed"
        r = judge(c, amount=100, category="食品", planned=True, today=TODAY)
        assert r["ok"] is True


class TestLagImpact:
    """§4.4 场景 A 条件 2：目标进度不恶化（F4+F7 遍历）。"""

    def _lagging_contract(self, base_contract):
        # 时间进度 ~55%，达成 10% → lag 大（实质落后）
        c = copy.deepcopy(base_contract)
        c["objectives"][0].update({
            "start_date": "2026-01-01", "deadline": "2027-01-01",
            "target_amount": 100000, "current_amount": 10000})
        return c

    def test_planned_spend_no_impact_flag(self, base_contract):
        c = self._lagging_contract(base_contract)
        r = judge(c, amount=20000, category="食品", planned=True, today=TODAY)
        assert r["impacted_objectives"] == []   # 计划内不算 lag 恶化

    def test_unplanned_impact_downgrades_a_to_b(self, base_contract):
        """资金面在垫上，但拖累实质落后目标 ≥1 月 → A 降 B。"""
        c = self._lagging_contract(base_contract)
        # 20000 / invest_real(≈3607) ≈ 5.5 月 ≥ 1 月，lag>5pct → worsened
        r = judge(c, amount=20000, category="合理享受", planned=False, today=TODAY)
        assert r["inputs"]["remaining_after"] >= r["inputs"]["effective_cushion"]
        assert len(r["impacted_objectives"]) == 1
        assert r["impacted_objectives"][0]["material_lag"] is True
        assert r["decision"]["scene"] == "B"

    def test_severe_delay_scene_c(self, base_contract):
        """实质落后目标再延 ≥6 月 → 严重拖慢，场景 C（即便资金面在垫上）。"""
        c = self._lagging_contract(base_contract)
        r = judge(c, amount=30000, category="合理享受", planned=False, today=TODAY)
        # 30000/3607.5 ≈ 8.3 月 ≥ 6
        assert r["decision"]["scene"] == "C"
        assert "严重拖慢" in r["decision"]["summary"]

    def test_healthy_objective_no_downgrade(self, base_contract):
        """目标超前（lag≤0）时非计划支出不降级（impacted 但非 material）。"""
        c = copy.deepcopy(base_contract)
        c["objectives"][0].update({
            "start_date": "2026-01-01", "deadline": "2027-01-01",
            "target_amount": 100000, "current_amount": 80000})
        r = judge(c, amount=20000, category="合理享受", planned=False, today=TODAY)
        assert r["decision"]["scene"] == "A"


class TestOptimizationGoal:
    """§7 三档调度：wealth/objective 收紧 B/C 判定边界（乘数修正）。"""

    def test_balanced_multiplier_is_one(self, base_contract):
        r = judge(base_contract, amount=100, category="食品",
                  planned=False, today=TODAY)
        assert r["optimization_applied"]["goal"] == "balanced"
        assert r["optimization_applied"]["cushion_multiplier"] == 1.0

    def test_wealth_tightens_boundary(self, base_contract):
        """base: corpus=200000, 垫=24000。amount=173000 → remaining=27000：
        balanced 下 A（27000≥24000）；wealth 下判定垫=28800 → 跌破 → B。"""
        c = copy.deepcopy(base_contract)
        r_bal = judge(c, amount=173000, category="合理享受",
                      planned=False, today=TODAY)
        assert r_bal["decision"]["scene"] == "A"
        c["optimization_goal"] = "wealth"
        r_w = judge(c, amount=173000, category="合理享受",
                    planned=False, today=TODAY)
        assert r_w["optimization_applied"]["cushion_multiplier"] == 1.2
        assert r_w["decision"]["scene"] == "B"

    def test_objective_tightens_unplanned_only(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["optimization_goal"] = "objective"
        r_unplanned = judge(c, amount=173000, category="合理享受",
                            planned=False, today=TODAY)
        assert r_unplanned["optimization_applied"]["cushion_multiplier"] == 1.3
        r_planned = judge(c, amount=173000, category="食品",
                          planned=True, today=TODAY)
        assert r_planned["optimization_applied"]["cushion_multiplier"] == 1.0


class TestSubmitPersistence:
    """submit 编排：冷静期入队落盘 + F8 快照 + 白名单额度记账。"""

    def test_cooldown_enqueues_pending_request(self, tmp_data_dir, base_contract):
        r = submit(tmp_data_dir, amount=6000, category="合理享受",
                   planned=False, today=TODAY)
        assert r["ok"] and r["cooldown"]["triggered"]
        assert r["request_id"] and r["expire_at"] == "2026-07-30T00:00:00"
        saved = read_contract(tmp_data_dir)
        pr = saved["pending_requests"]
        assert len(pr) == 1 and pr[0]["status"] == "cooling"
        assert pr[0]["request_id"] == r["request_id"]

    def test_small_amount_no_enqueue(self, tmp_data_dir, base_contract):
        r = submit(tmp_data_dir, amount=100, category="食品",
                   planned=True, today=TODAY)
        assert r["ok"] and not r["cooldown"]["triggered"]
        assert "request_id" not in r
        assert read_contract(tmp_data_dir)["pending_requests"] == []

    def test_fast_track_updates_used_annual(self, tmp_data_dir, base_contract):
        r = submit(tmp_data_dir, amount=6000, category="医疗",
                   planned=False, today=TODAY)
        assert r["whitelist"]["fast_track"] is True
        saved = read_contract(tmp_data_dir)
        med = next(i for i in saved["fast_track_whitelist"] if i["name"] == "医疗")
        assert med["used_annual"] == 6000
        assert saved["whitelist_cap_year"] == 2026

    def test_whitelist_annual_reset_on_year_change(self, tmp_data_dir, base_contract):
        submit(tmp_data_dir, amount=6000, category="医疗",
               planned=False, today=TODAY)
        # 次年首笔 → used_annual 先归零再记账（§5.1.2 跨年重置）
        submit(tmp_data_dir, amount=1000, category="医疗",
               planned=False, today=date(2027, 1, 5))
        saved = read_contract(tmp_data_dir)
        med = next(i for i in saved["fast_track_whitelist"] if i["name"] == "医疗")
        assert med["used_annual"] == 1000
        assert saved["whitelist_cap_year"] == 2027

    def test_financed_whitelist_records_down_payment_not_full_price(self, tmp_data_dir, base_contract):
        # H3 修复：融资购房走白名单极速放行时，年度额度应记「首付」而非全款，
        # 与限额闸门口径一致（闸门口径用 actual_cash_out = 首付）。
        c = read_contract(tmp_data_dir)
        c["corpus"] = 5000000                       # 足够支付首付，确保场景 A 批准
        c["fast_track_whitelist"] = [{"name": "购房", "per_tx_cap": 1000000,
                                      "annual_cap": 1000000, "used_annual": 0}]
        write_contract(tmp_data_dir, c, actor="configurator", confirm=True)
        # 100万房款，首付 30%（30万），融资 70万 → 实际现金流出 30万
        r = submit(tmp_data_dir, amount=1000000, category="购房",
                   planned=False, financed_amount=700000, today=TODAY)
        assert r["ok"]
        assert r["whitelist"]["fast_track"] is True
        saved = read_contract(tmp_data_dir)
        item = next(i for i in saved["fast_track_whitelist"] if i["name"] == "购房")
        assert item["used_annual"] == 300000        # 首付（修复前 = 1,000,000）
        # 次年再买一套：年度 cap 1,000,000 应还能容纳首付，而非被全款吃光
        submit(tmp_data_dir, amount=800000, category="购房",
               planned=False, financed_amount=560000, today=date(2027, 1, 5))
        saved2 = read_contract(tmp_data_dir)
        item2 = next(i for i in saved2["fast_track_whitelist"] if i["name"] == "购房")
        # 跨年重置后按首付 800000*0.3=240000 记账
        assert item2["used_annual"] == 240000

    def test_f8_snapshot_appended(self, tmp_data_dir, base_contract):
        submit(tmp_data_dir, amount=6000, category="合理享受",
               planned=False, today=TODAY)
        records = audit.read_all(tmp_data_dir, "approval_log")
        assert len(records) == 1
        snap = records[0]
        assert snap["request_id"] is not None
        for key in ("corpus", "net_assets", "effective_cushion",
                    "monthly_invest_nominal", "monthly_invest_real"):
            assert key in snap["inputs"], f"F8 快照缺 {key}"

    def test_not_stub_anymore(self, base_contract):
        r = judge(base_contract, amount=100, category="食品",
                  planned=True, today=TODAY)
        assert r["stub"] is False
