# -*- coding: utf-8 -*-
"""§7.2 三场景模拟演示测试：真实引擎干跑（数字真算）+ 隔离（不落盘不改真实数据）。"""
from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from datetime import date

import cli
from core import formulas as F
from modules.initialize import demo_scenarios

TODAY = date(2026, 7, 27)


def _run_cli(*argv: str) -> tuple[dict, int]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(list(argv))
    return json.loads(buf.getvalue()), code


class TestDemoScenarios:
    def test_three_scene_types(self, base_contract):
        """三场景判定类型：A 直批（无冷静期）/ 冷静期触发 / C 驳回。"""
        r = demo_scenarios(base_contract, today=TODAY)
        assert r["ok"] and r["stub"] is False
        s1, s2, s3 = r["scenarios"]
        # 场景 1：小额计划内 → 场景 A 直批且不触发冷静期
        assert s1["scene"] == "A" and s1["result"] == "批准"
        assert s1["cooldown_triggered"] is False
        # 场景 2：大额非计划 → 冷静期触发（§5.1）
        assert s2["cooldown_triggered"] is True
        assert s2["amount"] > r["engine_params"]["cooldown_threshold"]
        # 场景 3：破垫 → 场景 C 驳回 + 分期替代方案
        assert s3["scene"] == "C" and s3["result"] == "驳回"
        assert r["alt_plan_scenario3"] is not None
        assert r["alt_plan_scenario3"]["months"] >= 2

    def test_numbers_from_real_engine_not_hardcoded(self, base_contract):
        """数字必须来自引擎真实输出：阈值/安全垫与 F1/F2 独立复算一致。"""
        r = demo_scenarios(base_contract, today=TODAY)
        baseline = base_contract["monthly_contribution"] * 0.5
        cushion = F.f1_effective_cushion("months", baseline, months=6)
        threshold = F.f2_cooldown_threshold(
            cushion, base_contract["cooldown_days"], baseline)
        assert r["engine_params"]["judge_cushion"] == cushion
        assert r["engine_params"]["cooldown_threshold"] == threshold
        assert r["engine_params"]["corpus"] == base_contract["corpus"]
        # F5 简化延后月数（引擎真算，非文案硬编码）
        s2 = r["scenarios"][1]
        invest = F.f3_monthly_invest_nominal(
            base_contract["monthly_contribution"], 0.5)
        assert s2["delay_months_simple"] == F.f5_impact_simple(
            s2["amount"], invest)
        # 分期替代方案每笔 ≤ 冷静期阈值（引擎阈值推导，非硬编码 N）
        alt = r["alt_plan_scenario3"]
        assert alt["per_month"] <= threshold + 0.01

    def test_no_write_to_data_dir_and_no_mutation(self, tmp_data_dir, base_contract):
        """演示绝不落盘：不写 data-dir（无新文件）、不改传入契约对象。"""
        before = sorted(p.name for p in tmp_data_dir.rglob("*"))
        snapshot = copy.deepcopy(base_contract)
        demo_scenarios(base_contract, today=TODAY)
        after = sorted(p.name for p in tmp_data_dir.rglob("*"))
        assert before == after            # 无任何新文件（含 audit/）
        assert base_contract == snapshot  # 传入契约零改动（deepcopy 隔离）

    def test_demo_defaults_when_no_contract(self, tmp_path):
        """无契约 → 演示专用默认参数（纯内存），显式标注非真实契约，且不落盘。"""
        empty = tmp_path / "no-contract"
        empty.mkdir()
        r = demo_scenarios(None, today=TODAY)
        assert r["ok"] and r["demo_defaults_used"] is True
        assert any("演示数据，非您的真实契约" in n for n in r["notes"])
        scenes = [s["scene"] for s in r["scenarios"]]
        assert scenes[0] == "A" and scenes[2] == "C"
        assert not any(empty.iterdir())

    def test_init_attaches_demo(self, tmp_path):
        """初始化成功回执自动附演示区块（§7.2 交互口径）。"""
        d = tmp_path / "st-init-demo"
        r, code = _run_cli("--data-dir", str(d), "--today", "2026-07-27",
                           "init", "--corpus", "200000", "--monthly", "8000",
                           "--objective", "FIRE:3000000:2036-01-01")
        assert code == 0 and r["ok"]
        demo = r["demo"]
        assert demo["ok"] and demo["demo_defaults_used"] is False
        assert [s["scene"] for s in demo["scenarios"]][0] == "A"
        assert demo["scenarios"][2]["scene"] == "C"

    def test_cli_demo_command(self, tmp_path):
        """`demo` 子命令：无契约走演示默认值且不创建任何文件。"""
        d = tmp_path / "st-demo-cli"
        r, code = _run_cli("--data-dir", str(d), "--today", "2026-07-27", "demo")
        assert code == 0 and r["ok"]
        assert r["demo_defaults_used"] is True
        assert not d.exists()   # 干跑不创建 data-dir

    def test_cli_demo_uses_real_contract_after_init(self, tmp_path):
        d = tmp_path / "st-demo-real"
        _run_cli("--data-dir", str(d), "--today", "2026-07-27",
                 "init", "--corpus", "500000", "--monthly", "10000",
                 "--objective", "FIRE:3000000:2036-01-01")
        r, code = _run_cli("--data-dir", str(d), "--today", "2026-07-27", "demo")
        assert code == 0 and r["demo_defaults_used"] is False
        assert r["engine_params"]["corpus"] == 500000
        # 演示后契约无 pending_requests 入队（干跑不入冷静期队列）
        contract = json.loads((d / "contract.json").read_text(encoding="utf-8"))
        assert contract["pending_requests"] == []
