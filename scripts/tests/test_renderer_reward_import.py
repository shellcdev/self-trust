# -*- coding: utf-8 -*-
"""奖励 / 资产导入 渲染层统一 zh_status 路由测试（铁律 #7 守护）。

守护：reward / import 渲染点显示的状态值一律经 core.i18n.zh_status 中文化，
不得直吐英文枚举值（如 locked / imported_pending / manual）。
"""
from __future__ import annotations

from render.renderer import render


class TestRewardStatusRender:
    def test_reward_status_routed(self):
        out = render({"ok": True, "ref": "§6.3", "rewards": [
            {"name": "FIRE", "achieve_ratio": 130.0, "reward_quota": 140000.0,
             "reward_status": "unlocked"},
            {"name": "房", "achieve_ratio": 80.0, "reward_quota": 0.0,
             "reward_status": "locked"},
        ]}, "reward", "status")
        assert "已解锁" in out          # unlocked → 已解锁（zh_status 路由）
        assert "未解锁" in out          # locked → 未解锁（zh_status 路由）
        assert "locked" not in out      # 英文枚举值不得泄漏
        assert "unlocked" not in out

    def test_reward_status_four_states(self):
        out = render({"ok": True, "ref": "§6.3", "rewards": [
            {"name": "a", "achieve_ratio": 130.0, "reward_quota": 0.0,
             "reward_status": "exhausted"},
            {"name": "b", "achieve_ratio": 130.0, "reward_quota": 0.0,
             "reward_status": "unlockable"},
        ]}, "reward", "status")
        assert "已用尽" in out
        assert "待解锁" in out


class TestImportStatusRender:
    def test_pending_routed(self):
        out = render({"ok": True, "import_status": "imported_pending",
                      "summary": {"total_assets": 100.0},
                      "suspicious": []}, "import-asset", "pending")
        assert "待核对" in out          # imported_pending → 待核对（zh_status）
        assert "imported_pending" not in out

    def test_confirm_routed(self):
        out = render({"ok": True, "import_status": "imported_confirmed",
                      "applied": {"corpus": 100.0}}, "import-asset", "confirm")
        assert "已确认" in out          # imported_confirmed → 已确认（zh_status）
        assert "imported_confirmed" not in out

    def test_cancel_routed(self):
        out = render({"ok": True, "import_status": "manual"}, "import-asset", "cancel")
        assert "手动录入" in out        # manual → 手动录入（zh_status）
        assert "manual" not in out
