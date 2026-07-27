# -*- coding: utf-8 -*-
"""审计仅追加 + F8 快照完整性测试（§10.1 / 公式 8）。"""
from __future__ import annotations

import json

import pytest

from core import audit


class TestAppendOnly:
    def test_append_and_read_roundtrip(self, tmp_data_dir):
        audit.append(tmp_data_dir, "approval_log", {"time": "t1", "amount": 100})
        audit.append(tmp_data_dir, "approval_log", {"time": "t2", "amount": 200})
        records = audit.read_all(tmp_data_dir, "approval_log")
        assert [r["time"] for r in records] == ["t1", "t2"]

    def test_append_never_truncates(self, tmp_data_dir):
        """多次追加只增不减（仅追加语义）。"""
        path = None
        for i in range(5):
            path = audit.append(tmp_data_dir, "override_log", {"i": i})
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 5
        assert json.loads(lines[0])["i"] == 0  # 首条仍在，未被改写

    def test_no_delete_interface(self):
        """模块不提供任何删除/改写接口（§10.1 硬约束）。"""
        exposed = [n for n in dir(audit) if not n.startswith("_")]
        for banned in ("delete", "remove", "truncate", "rewrite", "clear"):
            assert not any(banned in n.lower() for n in exposed), \
                f"审计模块不得暴露删除类接口: {banned}"

    def test_invalid_log_name_rejected(self, tmp_data_dir):
        with pytest.raises(ValueError, match="未知审计日志"):
            audit.append(tmp_data_dir, "secret_log", {"x": 1})

    def test_non_dict_record_rejected(self, tmp_data_dir):
        with pytest.raises(TypeError):
            audit.append(tmp_data_dir, "approval_log", ["not-a-dict"])

    def test_missing_file_reads_empty(self, tmp_data_dir):
        assert audit.read_all(tmp_data_dir, "reward_log") == []

    def test_corrupt_line_skipped_tolerantly(self, tmp_data_dir):
        """L9：损坏行（如崩溃时的半截写入）跳过而非抛错，避免前序已读记录全部丢失。"""
        path = audit.log_path(tmp_data_dir, "appeal_log")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"ok": 1}\n{broken json\n', encoding="utf-8")
        recs = audit.read_all(tmp_data_dir, "appeal_log")  # 不抛错
        assert len(recs) == 1
        assert recs[0]["ok"] == 1


class TestF8Snapshot:
    def _valid_snapshot(self):
        return {
            "time": "2026-07-27T12:00:00", "amount": 10000,
            "category": "合理享受", "scene": "C",
            "inputs": {"corpus": 200000, "effective_cushion": 24000},
            "formulas_used": ["F0", "F1", "F3", "F5"],
            "decision": {"scene": "C", "result": "驳回", "summary": "击穿安全垫"},
            "alt_plan": "分 3 个月从合理享受额度支取",
        }

    def test_snapshot_persisted_under_audit_dir(self, tmp_data_dir):
        path = audit.append_approval_snapshot(tmp_data_dir, self._valid_snapshot())
        assert path.parent == audit.audit_dir(tmp_data_dir)
        records = audit.read_all(tmp_data_dir, "approval_log")
        assert records[0]["decision"]["result"] == "驳回"
        assert records[0]["inputs"]["corpus"] == 200000

    @pytest.mark.parametrize("missing", [
        "time", "amount", "category", "scene", "inputs",
        "formulas_used", "decision",
    ])
    def test_snapshot_missing_key_rejected(self, tmp_data_dir, missing):
        snap = self._valid_snapshot()
        del snap[missing]
        with pytest.raises(ValueError, match="必备键"):
            audit.append_approval_snapshot(tmp_data_dir, snap)

    def test_audit_dir_separated_from_contract(self, tmp_data_dir, base_contract):
        """契约与日志物理分离：audit/ 独立于 contract.json。"""
        from core.contract import contract_path
        audit.append_approval_snapshot(tmp_data_dir, self._valid_snapshot())
        assert contract_path(tmp_data_dir).is_file()
        assert audit.log_path(tmp_data_dir, "approval_log").is_file()
        # contract.json 内不含审计字段
        import json as _json
        contract = _json.loads(
            contract_path(tmp_data_dir).read_text(encoding="utf-8"))
        assert "approval_log" not in contract
