# -*- coding: utf-8 -*-
"""三区权限护栏测试（§10.3 / §5.4）—— 测试价值序最高优先：权限护栏 = 公正性地基。

核心断言：引擎（actor=engine）写配置区必须被拒；审计区字段禁入 contract.json；
核心护栏字段修改必须过 §5.4 二次确认闸门。
"""
from __future__ import annotations

import copy

import pytest

from core.contract import (
    GuardError, read_contract, write_contract, contract_path,
)


def _load(tmp_data_dir):
    return read_contract(tmp_data_dir)


class TestEngineCannotWriteConfigZone:
    """引擎无权修改配置区（最高优先）。"""

    @pytest.mark.parametrize("field,value", [
        ("corpus", 999999.0),
        ("monthly_contribution", 1.0),
        ("safety_cushion", {"mode": "months", "months": 0, "fixed": 0, "ratio": 0}),
        ("optimization_goal", "wealth"),
        ("cooldown_days", 0),
        ("mode", "conversational"),
    ])
    def test_engine_config_write_rejected(self, tmp_data_dir, base_contract,
                                          field, value):
        c = copy.deepcopy(base_contract)
        c[field] = value
        with pytest.raises(GuardError):
            write_contract(tmp_data_dir, c, actor="engine")
        # 落盘未被污染
        assert read_contract(tmp_data_dir)[field] == base_contract[field]

    def test_engine_cannot_tamper_objectives(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["weight"] = 0.01
        with pytest.raises(GuardError):
            write_contract(tmp_data_dir, c, actor="engine")

    def test_engine_cannot_add_or_remove_objectives(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"].append({"name": "偷渡目标"})
        with pytest.raises(GuardError):
            write_contract(tmp_data_dir, c, actor="engine")

    def test_engine_cannot_flip_status_to_completed(self, tmp_data_dir, base_contract):
        """§6.4：completed/archived 须用户显式确认，引擎仅可 active→overdue。"""
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["status"] = "completed"
        with pytest.raises(GuardError):
            write_contract(tmp_data_dir, c, actor="engine")

    def test_engine_cannot_raise_whitelist_caps(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["fast_track_whitelist"][0]["per_tx_cap"] = 999999
        with pytest.raises(GuardError):
            write_contract(tmp_data_dir, c, actor="engine")


class TestEngineRuntimeSubfields:
    """§10.3：嵌在配置区父字段内的运行态计数器，引擎可写。"""

    def test_engine_updates_lag_streak(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["lag_streak"] = 2
        write_contract(tmp_data_dir, c, actor="engine")
        assert read_contract(tmp_data_dir)["objectives"][0]["lag_streak"] == 2

    def test_engine_updates_reward_fields(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["reward_unlocked"] = True
        c["objectives"][0]["reward_quota"] = 12000.0
        write_contract(tmp_data_dir, c, actor="engine")
        saved = read_contract(tmp_data_dir)
        assert saved["objectives"][0]["reward_quota"] == 12000.0

    def test_engine_flips_active_to_overdue(self, tmp_data_dir, base_contract):
        """超期是确定性事实，引擎可自动翻转 active→overdue（§6.4）。"""
        c = copy.deepcopy(base_contract)
        c["objectives"][0]["status"] = "overdue"
        write_contract(tmp_data_dir, c, actor="engine")
        assert read_contract(tmp_data_dir)["objectives"][0]["status"] == "overdue"

    def test_engine_updates_used_annual(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["fast_track_whitelist"][0]["used_annual"] = 6000
        write_contract(tmp_data_dir, c, actor="engine")
        saved = read_contract(tmp_data_dir)
        assert saved["fast_track_whitelist"][0]["used_annual"] == 6000


class TestEngineCanWriteRuntimeZone:
    """运行态区（计数器/临时层）引擎可写。"""

    def test_engine_updates_counters(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["appeal_count"] = 2
        c["report_streak"] = 7
        c["last_calibrate"] = "2026-07-01"
        c["rebalance_override"] = {"month": "2026-07", "reason": "lag_streak"}
        write_contract(tmp_data_dir, c, actor="engine")
        saved = read_contract(tmp_data_dir)
        assert saved["appeal_count"] == 2
        assert saved["rebalance_override"]["reason"] == "lag_streak"

    def test_engine_updates_pending_requests(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["pending_requests"] = [{
            "request_id": "r1", "time": "2026-07-27T00:00:00", "amount": 6000,
            "category": "合理享受", "planned": False,
            "expire_at": "2026-07-30T00:00:00", "status": "cooling"}]
        write_contract(tmp_data_dir, c, actor="engine")
        assert read_contract(tmp_data_dir)["pending_requests"][0]["status"] == "cooling"


class TestConfiguratorGuardGate:
    """配置者改核心护栏字段必须过 §5.4 二次确认（confirm=True）。"""

    def test_guard_field_without_confirm_rejected(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["safety_cushion"] = dict(c["safety_cushion"], months=1)
        with pytest.raises(GuardError, match="二次确认"):
            write_contract(tmp_data_dir, c, actor="configurator", confirm=False)

    def test_guard_field_with_confirm_accepted(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["safety_cushion"] = dict(c["safety_cushion"], months=12)
        write_contract(tmp_data_dir, c, actor="configurator", confirm=True)
        assert read_contract(tmp_data_dir)["safety_cushion"]["months"] == 12

    def test_non_guard_config_field_plain_confirm(self, tmp_data_dir, base_contract):
        """非核心字段（如 mode）走普通确认，不强制二次确认。"""
        c = copy.deepcopy(base_contract)
        c["mode"] = "ledger"
        write_contract(tmp_data_dir, c, actor="configurator", confirm=False)
        assert read_contract(tmp_data_dir)["mode"] == "ledger"


class TestAuditZoneSeparation:
    """审计区字段禁止写入 contract.json（物理分离）。"""

    @pytest.mark.parametrize("field", [
        "approval_log", "appeal_log", "override_log", "reward_log",
        "monthly_history",
    ])
    def test_audit_field_rejected(self, tmp_data_dir, base_contract, field):
        c = copy.deepcopy(base_contract)
        c[field] = [{"time": "t"}]
        with pytest.raises(GuardError, match="审计区"):
            write_contract(tmp_data_dir, c, actor="configurator", confirm=True)


class TestMiscGuards:
    def test_unknown_field_rejected(self, tmp_data_dir, base_contract):
        c = copy.deepcopy(base_contract)
        c["hacked_field"] = 1
        with pytest.raises(GuardError, match="未知契约字段"):
            write_contract(tmp_data_dir, c, actor="configurator", confirm=True)

    def test_unknown_actor_rejected(self, tmp_data_dir, base_contract):
        with pytest.raises(GuardError, match="actor"):
            write_contract(tmp_data_dir, base_contract, actor="hacker")

    def test_engine_cannot_create_contract(self, tmp_path):
        from core.contract import new_default_contract
        with pytest.raises(GuardError, match="配置者"):
            write_contract(tmp_path / "fresh", new_default_contract(),
                           actor="engine", allow_create=True)

    def test_write_without_contract_requires_allow_create(self, tmp_path):
        from core.contract import new_default_contract
        with pytest.raises(FileNotFoundError):
            write_contract(tmp_path / "fresh2", new_default_contract(),
                           actor="configurator")


class TestDataDirResolution:
    """数据目录三级解析：命令行 > env > 默认 <home>/.claw/self-trust/（零 cwd 依赖）。"""

    def test_cli_arg_wins(self, tmp_path, monkeypatch):
        from pathlib import Path
        from core.contract import resolve_data_dir
        monkeypatch.setenv("SELFTRUST_DATA_DIR", str(tmp_path / "env"))
        assert resolve_data_dir(str(tmp_path / "cli")) == Path(tmp_path / "cli")

    def test_env_overrides_default(self, tmp_path, monkeypatch):
        from pathlib import Path
        from core.contract import resolve_data_dir
        monkeypatch.setenv("SELFTRUST_DATA_DIR", str(tmp_path / "env"))
        assert resolve_data_dir(None) == Path(tmp_path / "env")

    def test_default_anchored_to_home_not_cwd(self, tmp_path, monkeypatch):
        """默认落点锚定 Path.home()/.claw/self-trust（规范 §3 平台基址），不随 cwd 飘。"""
        from pathlib import Path
        from core.contract import resolve_data_dir
        monkeypatch.delenv("SELFTRUST_DATA_DIR", raising=False)
        monkeypatch.chdir(tmp_path)   # 换 cwd 不影响默认解析
        resolved = resolve_data_dir(None)
        assert resolved == Path.home() / ".claw" / "self-trust"
        assert not str(resolved).startswith(str(tmp_path))


class TestInitGuards:
    """§7.1 护栏 1：重复初始化拒绝覆盖。"""

    def test_reinit_rejected(self, tmp_data_dir, base_contract):
        from modules.initialize import lazy_init
        result = lazy_init(tmp_data_dir, corpus=1, monthly_contribution=1,
                           objectives=[{"name": "X"}])
        assert result["ok"] is False
        assert result["error"] == "exists"
        # 原契约未被覆盖
        assert read_contract(tmp_data_dir)["corpus"] == 200000

    def test_deadline_not_after_today_rejected(self, tmp_path):
        from datetime import date
        from modules.initialize import lazy_init
        d = tmp_path / "init2"
        result = lazy_init(
            d, corpus=1000, monthly_contribution=100,
            objectives=[{"name": "过期目标", "target_amount": 100,
                         "deadline": "2026-07-27"}],
            today=date(2026, 7, 27))
        assert result["ok"] is False
        assert result["error"] == "no_valid_objectives"
        assert not contract_path(d).exists()
