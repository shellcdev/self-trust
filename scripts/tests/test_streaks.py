# -*- coding: utf-8 -*-
"""§3.1 平滑过渡计数器测试：递增/清零/阈值触发 + 挂载点（report/reconcile/judge）。"""
from __future__ import annotations

from datetime import date, timedelta

from core.contract import read_contract
from modules import streaks
from modules.governance import reconcile
from modules.judge import submit
from modules.report import run_report

TODAY = date(2026, 7, 27)


class TestRecordReport:
    def test_streak_increments_on_consecutive_days(self, base_contract):
        c = dict(base_contract)
        for i in range(3):
            streaks.record_report(c, TODAY + timedelta(days=i))
        assert c["report_streak"] == 3
        assert c["gap_streak"] == 0
        assert c["last_report_date"] == "2026-07-29"

    def test_same_day_idempotent(self, base_contract):
        c = dict(base_contract)
        streaks.record_report(c, TODAY)
        streaks.record_report(c, TODAY)
        assert c["report_streak"] == 1   # 同日重复不重计

    def test_streak_resets_on_gap(self, base_contract):
        """断档 → report_streak 重计为 1（§3.1「断则归零」后本次上报起算）。"""
        c = dict(base_contract)
        for i in range(5):
            streaks.record_report(c, TODAY + timedelta(days=i))
        assert c["report_streak"] == 5
        streaks.record_report(c, TODAY + timedelta(days=8))   # 隔 3 天
        assert c["report_streak"] == 1
        assert c["gap_streak"] == 0                           # 报则归零


class TestObserve:
    def test_gap_accumulates_without_report(self, base_contract):
        c = dict(base_contract)
        streaks.record_report(c, TODAY)
        streaks.observe(c, TODAY + timedelta(days=14))
        assert c["gap_streak"] == 14
        assert c["report_streak"] == 0    # 断档 → 连续上报归零

    def test_observe_same_day_keeps_streak(self, base_contract):
        c = dict(base_contract)
        streaks.record_report(c, TODAY)
        streaks.observe(c, TODAY)         # 当日观察不破坏连续
        assert c["report_streak"] == 1 and c["gap_streak"] == 0

    def test_observe_without_anchor_noop(self, base_contract):
        c = dict(base_contract)
        c["last_report_date"] = None
        assert streaks.observe(c, TODAY) is False


class TestTransitionHint:
    def test_ledger_hint_at_7_days(self, base_contract):
        c = dict(base_contract)
        for i in range(7):
            streaks.record_report(c, TODAY + timedelta(days=i))
        hint = streaks.transition_hint(c)
        assert hint is not None and hint["suggest_mode"] == "ledger"
        assert hint["report_streak"] == 7
        assert "连续 7 天" in hint["message"]      # 文案带真实计数

    def test_no_hint_below_threshold(self, base_contract):
        c = dict(base_contract)
        for i in range(6):
            streaks.record_report(c, TODAY + timedelta(days=i))
        assert streaks.transition_hint(c) is None

    def test_conversational_hint_at_14_gap(self, base_contract):
        c = dict(base_contract)
        streaks.record_report(c, TODAY)
        streaks.observe(c, TODAY + timedelta(days=14))
        hint = streaks.transition_hint(c)
        assert hint is not None and hint["suggest_mode"] == "conversational"
        assert hint["gap_streak"] == 14
        assert "14 天" in hint["message"]

    def test_only_hybrid_triggers(self, base_contract):
        """ledger / conversational 已定态不弹提示（§3.1）。"""
        for mode in ("ledger", "conversational"):
            c = dict(base_contract)
            c["mode"] = mode
            for i in range(10):
                streaks.record_report(c, TODAY + timedelta(days=i))
            assert streaks.transition_hint(c) is None


class TestMountPoints:
    def test_report_updates_and_persists(self, tmp_data_dir, base_contract):
        r = run_report(tmp_data_dir, today=TODAY)
        assert r["report_streak"] == 1
        c = read_contract(tmp_data_dir)
        assert c["report_streak"] == 1 and c["gap_streak"] == 0

    def test_report_hint_after_7_consecutive_days(self, tmp_data_dir, base_contract):
        for i in range(7):
            r = run_report(tmp_data_dir, today=TODAY + timedelta(days=i))
        assert r["report_streak"] == 7
        hint = r["mode_transition_hint"]
        assert hint and hint["suggest_mode"] == "ledger"
        assert any("连续 7 天" in n for n in r["notes"])

    def test_report_gap_hint_visible_despite_reset(self, tmp_data_dir, base_contract):
        """report 场景先观察后记录：缺报 14 天后首报仍能看到降级建议（不被归零吞掉）。"""
        run_report(tmp_data_dir, today=TODAY)
        r = run_report(tmp_data_dir, today=TODAY + timedelta(days=14))
        assert r["gap_streak_observed"] == 14
        hint = r["mode_transition_hint"]
        assert hint and hint["suggest_mode"] == "conversational"
        # 记录后运行态已归零重计（下轮从头累计）
        c = read_contract(tmp_data_dir)
        assert c["gap_streak"] == 0 and c["report_streak"] == 1

    def test_reconcile_counts_as_report(self, tmp_data_dir, base_contract):
        r = reconcile(tmp_data_dir, income=8000, today=TODAY)
        assert r["ok"] and r["report_streak"] == 1
        c = read_contract(tmp_data_dir)
        assert c["report_streak"] == 1 and c["gap_streak"] == 0

    def test_judge_observes_gap_and_hints(self, tmp_data_dir, base_contract):
        """审批不算上报：gap 惰性刷新落盘，达 14 天时 judge 输出附降级建议。"""
        run_report(tmp_data_dir, today=TODAY)
        r = submit(tmp_data_dir, amount=100, category="合理享受",
                   planned=True, today=TODAY + timedelta(days=14))
        assert r["ok"]
        hint = r["mode_transition_hint"]
        assert hint and hint["suggest_mode"] == "conversational"
        assert hint["gap_streak"] == 14
        c = read_contract(tmp_data_dir)
        assert c["gap_streak"] == 14 and c["report_streak"] == 0

    def test_judge_no_hint_when_fresh(self, tmp_data_dir, base_contract):
        run_report(tmp_data_dir, today=TODAY)
        r = submit(tmp_data_dir, amount=100, category="合理享受",
                   planned=True, today=TODAY)
        assert r["ok"] and r["mode_transition_hint"] is None
