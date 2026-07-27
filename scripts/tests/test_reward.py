# -*- coding: utf-8 -*-
"""里程碑奖励测试（§6.3：120% 解锁 20% 超额 / 分次支取 / 不豁免判定）。"""
from __future__ import annotations

import copy
from datetime import date

from core import audit
from core.contract import read_contract, write_contract
from modules.reward import reward_status, unlock_rewards, claim_reward

TODAY = date(2026, 7, 27)


def _make_over_achiever(tmp_data_dir, current=3700000):
    """把 base_contract 的 FIRE 拉到 ≥120% 达成（3.6M 为 120% 线）。"""
    c = read_contract(tmp_data_dir)
    c["objectives"][0]["current_amount"] = float(current)
    write_contract(tmp_data_dir, c, actor="configurator", confirm=True)
    return c


class TestUnlock:
    def test_unlock_at_120pct(self, tmp_data_dir, base_contract):
        _make_over_achiever(tmp_data_dir)   # 3.7M / 3M ≈ 123%
        r = unlock_rewards(tmp_data_dir)
        assert r["ok"] and len(r["unlocked"]) == 1
        u = r["unlocked"][0]
        assert u["reward_quota"] == (3700000 - 3000000) * 0.2   # 超额×20%
        saved = read_contract(tmp_data_dir)
        assert saved["objectives"][0]["reward_unlocked"] is True
        assert saved["objectives"][0]["reward_quota"] == 140000.0
        # reward_log 留痕
        logs = audit.read_all(tmp_data_dir, "reward_log")
        assert logs and logs[0]["event"] == "unlocked"

    def test_below_120_not_unlocked(self, tmp_data_dir, base_contract):
        _make_over_achiever(tmp_data_dir, current=3300000)   # 110%
        r = unlock_rewards(tmp_data_dir)
        assert r["unlocked"] == []

    def test_unlock_only_once(self, tmp_data_dir, base_contract):
        _make_over_achiever(tmp_data_dir)
        unlock_rewards(tmp_data_dir)
        r2 = unlock_rewards(tmp_data_dir)   # 已解锁不重复
        assert r2["unlocked"] == []

    def test_status_readonly(self, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["current_amount"] = 3700000
        r = reward_status(c)
        assert r["rewards"][0]["unlockable"] is True
        assert r["rewards"][0]["potential_reward_max"] == 140000.0


class TestClaim:
    def _unlocked(self, tmp_data_dir):
        _make_over_achiever(tmp_data_dir)
        unlock_rewards(tmp_data_dir)

    def test_claim_partial_decrements_quota(self, tmp_data_dir, base_contract):
        self._unlocked(tmp_data_dir)
        r = claim_reward(tmp_data_dir, objective="FIRE", amount=40000,
                         purpose="旅行", today=TODAY)
        assert r["ok"] and r["cooldown_exempt"] is True
        assert r["quota_remaining"] == 100000.0
        saved = read_contract(tmp_data_dir)
        assert saved["objectives"][0]["reward_quota"] == 100000.0
        logs = audit.read_all(tmp_data_dir, "reward_log")
        claimed = [x for x in logs if x["event"] == "claimed"]
        assert claimed[0]["purpose"] == "旅行"

    def test_claim_exceeding_quota_rejected(self, tmp_data_dir, base_contract):
        self._unlocked(tmp_data_dir)
        r = claim_reward(tmp_data_dir, objective="FIRE", amount=140001,
                         purpose="x", today=TODAY)
        assert r["ok"] is False and r["error"] == "quota_exceeded"

    def test_claim_without_unlock_rejected(self, tmp_data_dir, base_contract):
        r = claim_reward(tmp_data_dir, objective="FIRE", amount=100,
                         purpose="x", today=TODAY)
        assert r["ok"] is False and r["error"] == "no_reward_quota"

    def test_claim_still_passes_judge(self, tmp_data_dir, base_contract):
        """免冷静期不豁免 §4.4：支取会击穿安全垫 → 拒绝（护栏）。"""
        self._unlocked(tmp_data_dir)
        # 垫=24000（baseline 4000×6）；corpus 改 150000 后支取 140000 →
        # 剩余 10000 < 24000，缺口 14000 > 月净流入 8000 → 场景 C
        c = read_contract(tmp_data_dir)
        c["corpus"] = 150000
        write_contract(tmp_data_dir, c, actor="configurator", confirm=True)
        r = claim_reward(tmp_data_dir, objective="FIRE", amount=140000,
                         purpose="x", today=TODAY)
        assert r["ok"] is False and r["error"] == "cushion_violation"
