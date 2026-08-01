# -*- coding: utf-8 -*-
"""报表模块测试（§6.1 双可视化 + monthly_history 快照 + §10.2 预警）。"""
from __future__ import annotations

import copy
from datetime import date

from core import audit
from core.contract import read_contract
from modules.report import render_report, run_report

TODAY = date(2026, 7, 27)


class TestRenderReport:
    def test_structured_output(self, base_contract):
        r = render_report(base_contract, [], today=TODAY)
        assert r["ok"] and r["stub"] is False
        assert r["corpus"] == 200000
        assert r["effective_cushion"] == 24000.0   # baseline 4000 × 6
        assert r["cushion_margin"] == 176000.0
        assert r["cushion_alert"] is False
        assert r["formulas_used"] == ["F0", "F1", "F4", "F6"]

    def test_progress_bar_dual_track(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0].update({"current_amount": 1260000})   # 42%
        r = render_report(c, [], today=TODAY)
        v = r["objectives"][0]
        assert v["lag"] is not None and v["color"] in ("绿", "黄", "红")
        assert "█" in v["ascii"] and "时间轴应达" in v["ascii"]

    def test_no_deadline_objective_savings_only(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"].append({"name": "生活质量", "weight": 0.4,
                                "current_amount": 3500, "target_amount": 10000,
                                "start_date": None, "deadline": None,
                                "status": "active"})
        r = render_report(c, [], today=TODAY)
        v = r["objectives"][1]
        assert v["lag"] is None and "攒钱占比 35%" in v["ascii"]

    def test_cushion_alert_red(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["corpus"] = 25000    # 垫 24000，余量 1000 < baseline 4000
        r = render_report(c, [], today=TODAY)
        assert r["cushion_alert"] is True
        assert any("安全垫预警" in n for n in r["notes"])

    def test_conversational_mode_note(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["mode"] = "conversational"
        r = render_report(c, [], today=TODAY)
        assert any("估算数据" in n for n in r["notes"])

    def test_trend_from_history(self, base_contract):
        history = [{"month": f"2026-0{i}", "income": 8000, "invest": 4000,
                    "living": 3000, "impulse": 500 if i == 3 else 0}
                   for i in range(1, 7)]
        r = render_report(base_contract, history, today=TODAY)
        assert "攒钱" in r["ascii"] and "安全垫红线" in r["ascii"]
        assert "月份" in r["ascii"]

    def test_empty_history_placeholder(self, base_contract):
        r = render_report(base_contract, [], today=TODAY)
        assert "暂无月度快照" in r["ascii"]

    def test_reward_badge(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0].update({"current_amount": 3700000,
                                   "reward_unlocked": True,
                                   "reward_quota": 140000.0})
        r = render_report(c, [], today=TODAY)
        assert "🏆" in r["objectives"][0]["ascii"]


class TestRunReport:
    def test_snapshot_appended_once_per_month(self, tmp_data_dir, base_contract):
        r1 = run_report(tmp_data_dir, today=TODAY)
        assert r1["snapshot_appended"] is not None
        assert r1["snapshot_appended"]["month"] == "2026-07"
        # 同月第二次不重复追加
        r2 = run_report(tmp_data_dir, today=date(2026, 7, 28))
        assert r2["snapshot_appended"] is None
        records = audit.read_all(tmp_data_dir, "monthly_history")
        assert len(records) == 1
        assert records[0]["corpus"] == 200000

    def test_last_report_date_updated(self, tmp_data_dir, base_contract):
        run_report(tmp_data_dir, today=TODAY)
        assert read_contract(tmp_data_dir)["last_report_date"] == "2026-07-27"

    def test_snapshot_does_not_fabricate_income(self, tmp_data_dir, base_contract):
        """引擎不虚构当月实绩：income/invest 等留 None 由对账补录。"""
        r = run_report(tmp_data_dir, today=TODAY)
        snap = r["snapshot_appended"]
        assert snap["income"] is None and snap["invest"] is None
