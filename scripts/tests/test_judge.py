# -*- coding: utf-8 -*-
"""judge 骨架测试：三场景路由 + 白名单双上限 + 阈值 clamp（§4.4 / §5.1.2）。

注：judge 为骨架版（lag 恶化校验/冷静期入队为 stub），本套件覆盖已实装的
确定性路由，后续 PR 实装时扩充。
"""
from __future__ import annotations

from modules.judge import judge, check_whitelist


class TestSceneRouting:
    """base_contract: corpus=200000, monthly=8000, baseline=4000, 垫=24000（months×6）。"""

    def test_scene_a_approve(self, base_contract):
        r = judge(base_contract, amount=6000, category="合理享受", planned=False)
        assert r["ok"] and r["decision"]["scene"] == "A"
        assert r["decision"]["result"] == "批准"

    def test_scene_b_conditional(self, base_contract):
        # 200000 - 180000 = 20000 < 24000，缺口 4000 ≤ 月净流入 8000 → B
        r = judge(base_contract, amount=180000, category="合理享受", planned=False)
        assert r["decision"]["scene"] == "B"
        assert r["decision"]["result"] == "附条件"

    def test_scene_c_reject(self, base_contract):
        # 缺口远超月净流入 → C
        r = judge(base_contract, amount=199000, category="合理享受", planned=False)
        assert r["decision"]["scene"] == "C"
        assert r["decision"]["result"] == "驳回"

    def test_invalid_amount(self, base_contract):
        r = judge(base_contract, amount=0, category="X", planned=False)
        assert r["ok"] is False and r["error"] == "invalid_amount"

    def test_outputs_full_intermediates(self, base_contract):
        """引擎 JSON 必须带全部中间变量（LLM 禁止心算铁律的前提）。"""
        r = judge(base_contract, amount=100, category="食品", planned=True)
        for key in ("corpus", "net_assets", "monthly_net", "living_baseline",
                    "effective_cushion", "monthly_invest_nominal",
                    "monthly_invest_real", "remaining_after"):
            assert key in r["inputs"], f"缺中间变量 {key}"
        assert r["formulas_used"]


class TestCooldown:
    def test_small_amount_no_cooldown(self, base_contract):
        r = judge(base_contract, amount=100, category="食品", planned=True)
        assert r["cooldown"]["triggered"] is False

    def test_large_amount_triggers_cooldown(self, base_contract):
        # 阈值 = (24000/30)*3 = 2400（在 [800, 12000] clamp 内）
        r = judge(base_contract, amount=6000, category="合理享受", planned=False)
        assert r["cooldown"]["threshold"] == 2400.0
        assert r["cooldown"]["triggered"] is True

    def test_whitelist_fast_track_skips_cooldown(self, base_contract):
        r = judge(base_contract, amount=6000, category="医疗", planned=False)
        assert r["whitelist"]["fast_track"] is True
        assert r["cooldown"]["triggered"] is False
        # 免等待不豁免判定：仍有场景结论
        assert r["decision"]["scene"] in ("A", "B", "C")


class TestWhitelistCaps:
    def test_within_both_caps(self, base_contract):
        wl = check_whitelist(base_contract, "医疗", 50000)
        assert wl["fast_track"] is True

    def test_per_tx_cap_exceeded(self, base_contract):
        wl = check_whitelist(base_contract, "医疗", 50001)
        assert wl["listed"] and not wl["fast_track"] and not wl["per_tx_ok"]

    def test_annual_cap_exceeded(self, base_contract):
        c = dict(base_contract)
        c["fast_track_whitelist"] = [{"name": "医疗", "per_tx_cap": 50000,
                                      "annual_cap": 200000, "used_annual": 160000}]
        wl = check_whitelist(c, "医疗", 50000)   # 160000+50000 > 200000
        assert wl["listed"] and not wl["fast_track"] and not wl["annual_ok"]

    def test_not_listed(self, base_contract):
        wl = check_whitelist(base_contract, "合理享受", 100)
        assert wl["listed"] is False and wl["fast_track"] is False
