# -*- coding: utf-8 -*-
"""落盘健壮性护栏测试（2026-07-28 三层加固：读时守卫 / 写前校验 / 唯一临时名）。

覆盖：拼接/截断 JSON 触发 ContractCorruptedError 并指向 .bak.corrupt；
写前校验在 tmp 无效时保留原好文件、不残留 tmp；CLI 输出 contract_corrupted + exit 6。
"""
from __future__ import annotations

import copy

import pytest

import cli
import core.contract as contract_mod
from core.contract import (
    ContractCorruptedError, read_contract, write_contract, contract_path,
)


class TestReadGuard:
    """读时完整性守卫：拼接/截断 JSON 抛清晰错误，不裸抛 Extra data。"""

    def test_detects_concatenated_json(self, tmp_data_dir):
        p = contract_path(tmp_data_dir)
        # 两段拼接 JSON（复现根因：第一段完整、第二段残缺）
        p.write_bytes('{"a":1}{"b":2}'.encode("utf-8"))
        with pytest.raises(ContractCorruptedError) as ei:
            read_contract(tmp_data_dir)
        assert ei.value.path == p
        assert ".bak.corrupt" in str(ei.value)

    def test_detects_truncated_json(self, tmp_data_dir):
        p = contract_path(tmp_data_dir)
        p.write_bytes('{"a":1, "b":'.encode("utf-8"))  # 截断
        with pytest.raises(ContractCorruptedError) as ei:
            read_contract(tmp_data_dir)
        assert ".bak.corrupt" in str(ei.value)


class TestWriteGuard:
    """写前校验：tmp 回读通过才替换；失败保留原好文件、不残留 tmp。"""

    def test_preserves_good_file_when_tmp_invalid(self, monkeypatch, tmp_data_dir, base_contract):
        # 先落一份完好契约（base_contract fixture 已 lazy_init 写入）
        good = read_contract(tmp_data_dir)
        # 强制 tmp 回读校验失败，模拟瞬态写花
        monkeypatch.setattr(contract_mod, "_tmp_is_valid", lambda tmp: False)
        bad = copy.deepcopy(base_contract)
        bad["mode"] = "objective"
        with pytest.raises(ContractCorruptedError):
            write_contract(tmp_data_dir, bad, actor="configurator")
        # 原好文件未被替换、内容未变、仍可正常读
        assert read_contract(tmp_data_dir) == good
        # 不应残留任何 tmp 文件
        assert not list(contract_path(tmp_data_dir).parent.glob("*.tmp"))

    def test_no_tmp_leak_on_success(self, tmp_data_dir, base_contract):
        write_contract(tmp_data_dir, base_contract, actor="configurator", allow_create=True)
        # 回读一致
        assert read_contract(tmp_data_dir) == base_contract
        # 无 tmp 残留
        assert not list(contract_path(tmp_data_dir).parent.glob("*.tmp"))


class TestCliExitCode:
    """CLI 出口：契约损坏 → error=contract_corrupted，exit 6。"""

    def test_cli_reports_contract_corrupted_exit6(self, tmp_data_dir):
        p = contract_path(tmp_data_dir)
        p.write_bytes('{"a":1}{"b":2}'.encode("utf-8"))  # 拼接损坏
        code = cli.main([
            "--json", "--data-dir", str(tmp_data_dir),
            "judge", "--amount", "1", "--category", "食品",
        ])
        assert code == 6
