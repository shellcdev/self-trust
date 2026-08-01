# -*- coding: utf-8 -*-
"""月净流入口径（毛/净）文本渲染测试（renderer.py，phase 1 纯展示层）。

守护：
- init 毛口径徽标 〔毛口径·待校准〕；
- report 毛口径徽标 + 净口径分解行；
- judge B/C/冷静期 毛口径提示行（§1.5），小额直批 A 不刷屏。
"""
from __future__ import annotations

from datetime import date

from render.renderer import render

TODAY = date(2026, 7, 27)


class TestInitBadge:
    def test_gross_badge_shown(self):
        out = render({"ok": True, "corpus": 200000, "monthly_contribution": 8000,
                      "monthly_basis": "gross_estimate", "currency": "CNY",
                      "objectives": [], "warnings": []}, "init")
        assert "〔毛口径·待校准〕" in out

    def test_net_no_badge(self):
        out = render({"ok": True, "corpus": 200000, "monthly_contribution": 8000,
                      "monthly_basis": "net", "currency": "CNY",
                      "objectives": [], "warnings": []}, "init")
        assert "〔毛口径·待校准〕" not in out


class TestReportBadgeAndDecomp:
    def test_gross_badge_in_report(self):
        out = render({"ok": True, "corpus": 200000, "net_assets": 200000,
                      "cushion_margin": 176000, "cushion_alert": False,
                      "monthly_net": 8000, "monthly_basis": "gross_estimate",
                      "objectives": [], "pending_cooling": [], "notes": []}, "report")
        assert "〔毛口径·待校准〕" in out

    def test_net_decomposition_line(self):
        out = render({"ok": True, "corpus": 200000, "net_assets": 200000,
                      "cushion_margin": 176000, "cushion_alert": False,
                      "monthly_net": 8000, "monthly_basis": "net",
                      "monthly_net_effective": {"entered": 8000, "debt_monthly": 5000,
                                                "rigid_monthly": 1000, "net": 2000},
                      "objectives": [], "pending_cooling": [], "notes": []}, "report")
        assert "月净流入（净）" in out
        assert "〔毛口径·待校准〕" not in out


class TestJudgeGrossPrompt:
    def _base(self, scene, cooldown):
        return {
            "ok": True,
            "decision": {"scene": scene, "result": "附条件", "summary": "对照"},
            "inputs": {"amount": 1000, "category": "X", "corpus": 200000,
                       "remaining_after": 199000, "effective_cushion": 24000,
                       "monthly_basis": "gross_estimate", "monthly_net": 8000},
            "impacted_objectives": [],
            "cooldown": {"triggered": cooldown, "days": 3},
            "request_id": "rid", "expire_at": "2026-08-01",
            "impact": {"delay_months_simple": 0},
        }

    def test_b_scene_shows_prompt(self):
        out = render(self._base("B", False), "judge", "submit")
        assert "毛口径估算" in out

    def test_c_scene_shows_prompt(self):
        out = render(self._base("C", False), "judge", "submit")
        assert "毛口径估算" in out

    def test_cooldown_shows_prompt(self):
        out = render(self._base("A", True), "judge", "submit")
        assert "毛口径估算" in out

    def test_small_a_no_prompt(self):
        # 小额直批 A 无冷静期 → 不刷屏
        out = render(self._base("A", False), "judge", "submit")
        assert "毛口径估算" not in out

    def test_net_basis_no_prompt(self):
        r = self._base("B", False)
        r["inputs"]["monthly_basis"] = "net"
        out = render(r, "judge", "submit")
        assert "毛口径估算" not in out
