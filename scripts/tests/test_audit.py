from __future__ import annotations

from core import audit as mod_audit
from core import audit as audit_io


def test_atomic_write_bytes_roundtrip(tmp_path):
    # CQ-1 回归：整文件原子写 + 写后回读校验
    blob = b"hello\x00world"
    p = tmp_path / "x.jsonl"
    mod_audit._atomic_write_bytes(p, blob)
    assert p.read_bytes() == blob  # 回读校验保证落盘一致
    # 重写（更大/更小/空）仍原子正确
    mod_audit._atomic_write_bytes(p, b"")
    assert p.read_bytes() == b""


def test_append_plaintext_roundtrip(tmp_path):
    # 明文追加路径端到端往返，间接锁定 _atomic_write_bytes 行为
    audit_io.append(tmp_path, "override_log", {"event": "t", "k": 1})
    rows = audit_io.read_all(tmp_path, "override_log")
    assert rows == [{"event": "t", "k": 1}]
    # 二次追加不丢首条
    audit_io.append(tmp_path, "override_log", {"event": "t2"})
    rows = audit_io.read_all(tmp_path, "override_log")
    assert [r["event"] for r in rows] == ["t", "t2"]
