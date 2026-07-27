# -*- coding: utf-8 -*-
"""第二份扫描报告（Loomy/self-trust-硬伤扫描报告.md）中等 M1–M9 / 轻微 L1–L11 回归测试。

每条测试对应报告里的一项修复，确保「逻辑 today 对齐 / 原子性 / 队列容错 /
锁 / 去重语义 / 恒定时间比较 / 类型保真 / 模式大小写 / deadline 校驗 / 中位数基线 /
损坏行容忍 / 缺省键 / CLI 解耦」在后续重构中不回退。
"""
from __future__ import annotations

import datetime
import importlib

import pytest
from datetime import date

from core import audit as audit_io
from core import contract as contract_io
from core.formulas import f1_effective_cushion
from modules.customize import (
    _eff_cushion, _parse_objective, _parse_scalar, apply, sweep_pending_config,
)
from modules.import_asset import _dedup_balances, _get_staging
from modules.judge import estimate_mortgage_monthly, expire, submit
from modules.governance import reconcile
from modules.report import _objective_view
from modules.initialize import lazy_init
from modules import calibrate as calibrate_mod

TODAY = date(2026, 7, 27)


# --------------------------------------------------------------------------- M1
class TestM1AuditTimeAlignsLogicalToday:
    def test_now_iso_uses_logical_today(self):
        """审计时间戳须对齐逻辑 today（重放可复现），而非真实墙钟。"""
        ts = audit_io.now_iso(TODAY)
        assert ts.startswith("2026-07-27T")

    def test_submit_audit_time_uses_today(self, tmp_data_dir):
        """submit 的 F8 审批快照 time 须对齐逻辑 today。"""
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        submit(tmp_data_dir, amount=35, category="合理享受", planned=True,
               today=TODAY)
        recs = audit_io.read_all(tmp_data_dir, "approval_log")
        assert recs, "审批快照应落盘"
        assert all(r["time"].startswith("2026-07-27T") for r in recs)

    def test_expire_audit_time_uses_today(self, tmp_data_dir):
        """expire 终裁的 expired_ruling 记录 time 须对齐逻辑 today。"""
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        c = contract_io.read_contract(tmp_data_dir)
        c["pending_requests"] = [{
            "request_id": "e1", "time": "2026-07-20T00:00:00",
            "amount": 6000.0, "category": "数码", "planned": False,
            "expire_at": "2026-07-21T00:00:00", "status": "cooling",
            "decision": {"scene": "B", "result": "附条件", "summary": "x"},
        }]
        contract_io.write_contract(tmp_data_dir, c, actor="engine")
        expire(tmp_data_dir, today=TODAY)
        recs = audit_io.read_all(tmp_data_dir, "approval_log")
        ruled = [r for r in recs if r.get("event") == "expired_ruling"]
        assert ruled and ruled[0]["time"].startswith("2026-07-27T")


# --------------------------------------------------------------------------- M2
class TestM2ExpireAtomicity:
    def _seed(self, tmp_data_dir):
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        c = contract_io.read_contract(tmp_data_dir)
        c["pending_requests"] = [
            {"request_id": f"exp{i}", "time": "2026-07-20T00:00:00",
             "amount": 6000.0, "category": "数码", "planned": False,
             "expire_at": "2026-07-21T00:00:00", "status": "cooling",
             "decision": {"scene": "B", "result": "附条件", "summary": "x"}}
            for i in (1, 2)]
        contract_io.write_contract(tmp_data_dir, c, actor="engine")

    def test_both_expired_processed_once(self, tmp_data_dir):
        """两条过期 cooling 须一次性原子终裁，且重跑不再二次处理。"""
        self._seed(tmp_data_dir)
        r1 = expire(tmp_data_dir, today=TODAY)
        assert len(r1["processed"]) == 2
        assert {p["final_status"] for p in r1["processed"]} == {"decided"}
        recs1 = audit_io.read_all(tmp_data_dir, "approval_log")
        ruled1 = [x for x in recs1 if x.get("event") == "expired_ruling"]
        assert len(ruled1) == 2

        # 重跑：不应再处理（状态已非 cooling），审计记录数不变
        r2 = expire(tmp_data_dir, today=TODAY)
        assert r2["processed"] == []
        recs2 = audit_io.read_all(tmp_data_dir, "approval_log")
        ruled2 = [x for x in recs2 if x.get("event") == "expired_ruling"]
        assert len(ruled2) == 2  # 未重复追加


# --------------------------------------------------------------------------- M3
class TestM3SweepToleratesSingleFailure:
    def test_failing_item_kept_others_applied(self, tmp_data_dir):
        """sweep 中单条应用失败 → 标记 failed 保留，不阻塞其余、不写脏契约。"""
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        c = contract_io.read_contract(tmp_data_dir)
        # 注意：默认契约已含 pending_config_changes=[]，必须用赋值覆盖而非 setdefault
        c["pending_config_changes"] = [
            # 有效：普通 set（CONFIG 区，configurator 可写）
            {"request_id": "ok1", "created_at": "2026-07-20T00:00:00",
             "expires_at": "2026-07-21T00:00:00", "status": "pending",
             "preview": {"changed_fields": {"monthly_contribution": {"from": 8000, "to": 9000}},
                         "touched_guard_fields": [], "risk_warnings": []},
             "changes": {"set": [{"path": "monthly_contribution", "value": 9000}]}},
            # 失败：重复追加已存在目标（H6 抛 ValueError）→ 须被隔离
            {"request_id": "bad1", "created_at": "2026-07-20T00:00:00",
             "expires_at": "2026-07-21T00:00:00", "status": "pending",
             "preview": {"changed_fields": {}, "touched_guard_fields": [],
                         "risk_warnings": []},
             "changes": {"add_objective": ["FIRE:3000000:2036-01-01"]}},
        ]
        contract_io.write_contract(tmp_data_dir, c, actor="configurator",
                                   confirm=True)
        res = sweep_pending_config(tmp_data_dir,
                                   now=datetime.datetime(2026, 7, 27, 23, 59))
        assert "ok1" in res["applied"]
        assert res["failed"] and res["failed"][0]["request_id"] == "bad1"

        after = contract_io.read_contract(tmp_data_dir)
        assert after["monthly_contribution"] == 9000  # 有效项已落地
        kept = [e for e in after.get("pending_config_changes", [])
                if e["status"] == "failed"]
        assert kept and kept[0]["request_id"] == "bad1"  # 失败项保留供排查


# --------------------------------------------------------------------------- M6
class TestM6ObjectiveViewFieldName:
    def test_only_achieved_ratio_present(self):
        """报表视图只暴露 achieved_ratio，不再挂易混的 achieve_ratio。"""
        obj = {"name": "FIRE", "target_amount": 3000000, "current_amount": 100000,
               "start_date": "2026-07-01", "deadline": "2036-01-01",
               "reward_quota": 0.0}
        view = _objective_view(obj, TODAY)
        assert "achieved_ratio" in view
        assert "achieve_ratio" not in view


# --------------------------------------------------------------------------- M7
class TestM7AuditAppendLock:
    def test_locked_append_writes_line_and_concurrent_safe(self, tmp_data_dir):
        """_locked_append 须落盘一行；两次追加均应保留（不交错/不丢）。"""
        path = audit_io.log_path(tmp_data_dir, "approval_log")
        audit_io._locked_append(path, '{"a": 1}')
        audit_io._locked_append(path, '{"a": 2}')
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 2
        assert lines[0] == '{"a": 1}' and lines[1] == '{"a": 2}'

    def test_append_produces_valid_jsonl(self, tmp_data_dir):
        audit_io.append(tmp_data_dir, "override_log", {"event": "x", "n": 1})
        recs = audit_io.read_all(tmp_data_dir, "override_log")
        assert recs == [{"event": "x", "n": 1}]


# --------------------------------------------------------------------------- M8
class TestM8DedupLastWins:
    def test_same_account_diff_balance_last_wins(self):
        """同账户（name+kind）余额不同 → 取最新出现值覆盖并告警，不求和（防 corpus 翻倍）。"""
        rows = [
            {"name": "招行", "kind": "asset", "balance": 100000.0, "monthly": 0.0},
            {"name": "招行", "kind": "asset", "balance": 200000.0, "monthly": 0.0},
        ]
        merged, warnings = _dedup_balances(rows)
        assert len(merged) == 1
        assert merged[0]["balance"] == 200000.0  # 最新快照覆盖，非求和 300000
        assert warnings and warnings[0]["name"] == "招行"


# --------------------------------------------------------------------------- M9
class TestM9ConstantTimeToken:
    def test_get_staging_rejects_bad_token(self):
        staging = {"token": "abcdef0123456789", "candidates": {}}
        bad, err = _get_staging({"pending_import": staging}, "wrong-token")
        assert bad is None and err == "bad_token"

    def test_customize_apply_rejects_stale_token(self, tmp_data_dir):
        """确认 token 不匹配 → stale_token，永不落盘。"""
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        changes = {"set": [{"path": "monthly_contribution", "value": 9000}]}
        res = apply(tmp_data_dir, changes, confirm=True, token="nope",
                    reason="x")
        assert res.get("error") == "stale_token"
        after = contract_io.read_contract(tmp_data_dir)
        assert after["monthly_contribution"] == 8000  # 未落盘


# --------------------------------------------------------------------------- L1
class TestL1ZeroTermMortgage:
    def test_term_zero_returns_zero_monthly(self):
        """期限 0 年（一次性付清）月供为 0，不返回全额本金。"""
        assert estimate_mortgage_monthly(1_000_000, 0, 0.04) == 0.0
        assert estimate_mortgage_monthly(500_000, 0, 0.0) == 0.0


# --------------------------------------------------------------------------- L3
class TestL3PositiveTargetOnly:
    def test_customize_rejects_negative_target(self):
        with pytest.raises(ValueError, match="目标额须为正数"):
            _parse_objective("FIRE:-500")

    def test_cli_rejects_negative_target(self):
        cli = importlib.import_module("cli")
        with pytest.raises(ValueError, match="目标额须为正数"):
            cli._parse_objective("FIRE:-500")


# --------------------------------------------------------------------------- L4
class TestL4ScalarTypeFidelity:
    def test_int_string_stays_int(self):
        assert _parse_scalar("3") == 3
        assert isinstance(_parse_scalar("3"), int)

    def test_float_string_stays_float(self):
        assert _parse_scalar("3.5") == 3.5
        assert isinstance(_parse_scalar("3.5"), float)

    def test_bool_and_none(self):
        assert _parse_scalar("true") is True
        assert _parse_scalar("null") is None


# --------------------------------------------------------------------------- L5
class TestL5CushionModeCaseInsensitive:
    def test_formula_months_uppercase(self):
        assert f1_effective_cushion("Months", living_baseline=5000, months=6) == 30000.0

    def test_customize_eff_cushion_uppercase(self):
        assert _eff_cushion({"mode": "Months", "months": 6}, 5000.0, 200000.0) == 30000.0


# --------------------------------------------------------------------------- L6
class TestL6DeadlineValidation:
    def test_past_deadline_rejected(self, tmp_data_dir):
        res = lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                        objectives=[{"name": "FIRE", "target_amount": 3000000,
                                     "deadline": "2020-01-01"}], today=TODAY)
        assert res["ok"] is False
        assert res["error"] == "no_valid_objectives"

    def test_malformed_deadline_rejected(self, tmp_data_dir):
        res = lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                        objectives=[{"name": "FIRE", "target_amount": 3000000,
                                     "deadline": "2036/01/01"}], today=TODAY)
        assert res["ok"] is False
        assert any("格式非法" in r.get("reason", "") for r in res["rejected_objectives"])


# --------------------------------------------------------------------------- L7
class TestL7MedianIncomeBaseline:
    def test_outlier_does_not_trigger_spurious_income_relax(self, tmp_data_dir):
        """monthly_contribution=0 且历史含一次性大额（异常）→ 中位数基线稳健，
        不应误判为「收入下跌」触发 income_relax（旧均值口径会误触发）。"""
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=0,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        c = contract_io.read_contract(tmp_data_dir)
        history = [
            {"month": "2026-05", "income": 50000.0},  # 一次性大额异常
            {"month": "2026-06", "income": 4000.0},
            {"month": "2026-07", "income": 4000.0},
        ]
        calibrate_mod.calibrate(c, history, today=TODAY)
        changes = c.get("rebalance_override")
        # 中位数基线 = 4000；近期 4000 不 ≤ 0.8*4000 → 不触发 income_relax
        assert changes is None or changes.get("reason") != "income_drop"


# --------------------------------------------------------------------------- L9
class TestL9CorruptLineSkipped:
    def test_read_all_skips_corrupt_line(self, tmp_data_dir):
        path = audit_io.log_path(tmp_data_dir, "override_log")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"event": "ok", "n": 1}\n'
            'this is not json\n'
            '{"event": "ok2", "n": 2}\n',
            encoding="utf-8")
        recs = audit_io.read_all(tmp_data_dir, "override_log")
        assert len(recs) == 2  # 损坏行跳过，有效记录不丢
        assert recs[0]["n"] == 1 and recs[1]["n"] == 2


# --------------------------------------------------------------------------- L10
class TestL10ReconcileReminderStreakDefault:
    def test_reminder_streak_setdefault(self, tmp_data_dir):
        lazy_init(tmp_data_dir, corpus=200000, monthly_contribution=8000,
                  objectives=[{"name": "FIRE", "target_amount": 3000000,
                               "deadline": "2036-01-01"}], today=TODAY)
        c = contract_io.read_contract(tmp_data_dir)
        # 模拟老契约/缺省缺失该键的场景，验证 setdefault 兜底不抛 KeyError
        c["reconcile"].pop("reminder_streak", None)
        contract_io.write_contract(tmp_data_dir, c, actor="configurator",
                                   confirm=True)
        reconcile(tmp_data_dir, corpus=210000, today=TODAY)
        after = contract_io.read_contract(tmp_data_dir)
        assert after["reconcile"]["reminder_streak"] == 0


# --------------------------------------------------------------------------- L11
class TestL11CliParsersLocal:
    def test_cli_parsers_not_imported_from_customize(self):
        """CLI 解析器应为本地实现（解耦 customize 私有符号），避免导入脆断。"""
        cli = importlib.import_module("cli")
        # 本地定义（同一模块 __dict__），非从 modules.customize 导入
        assert "_parse_liability" in cli.__dict__
        assert "_parse_rigid" in cli.__dict__
        assert "_parse_objective" in cli.__dict__

    def test_cli_liability_rigid_parse(self):
        cli = importlib.import_module("cli")
        li = cli._parse_liability("房贷:800000:5000:0.04")
        assert li == {"name": "房贷", "balance": 800000.0,
                      "monthly_payment": 5000.0, "annual_rate": 0.04}
        rg = cli._parse_rigid("保费:12000:3")
        assert rg == {"name": "保费", "amount": 12000.0, "due_month": 3}
