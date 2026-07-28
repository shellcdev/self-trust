# -*- coding: utf-8 -*-
"""加密开关（方案 C：passphrase + key-file 双路线）测试。

覆盖：底层 seal/unseal 往返、错误密码、key-file 模式、is_encrypted 检测、
契约读写加密、审计日志加密、明文向后兼容、缺密钥报错。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core import crypto as crypto_io
from core import contract as contract_io
from core import audit as audit_io
from core.models import Contract


@pytest.fixture(autouse=True)
def _reset_crypto():
    """每个用例前后清空 session + 审计加密标志（隔离）。"""
    crypto_io.reset_session()
    yield
    crypto_io.reset_session()


# ── 底层原语 ──────────────────────────────────────────────────────────
def test_seal_unseal_passphrase_roundtrip():
    blob = crypto_io.seal(b"hello world", passphrase="x")
    assert crypto_io.is_encrypted(blob)
    assert crypto_io.unseal(blob, passphrase="x") == b"hello world"


def test_seal_unseal_json_roundtrip():
    obj = {"a": 1, "b": ["x", "y"], "c": {"nested": True}}
    blob = crypto_io.seal_json(obj, passphrase="x")
    assert crypto_io.unseal_json(blob, passphrase="x") == obj


def test_wrong_passphrase_raises():
    blob = crypto_io.seal(b"secret", passphrase="correct")
    with pytest.raises(crypto_io.InvalidPassphrase):
        crypto_io.unseal(blob, passphrase="wrong")


def test_is_encrypted_false_for_plaintext():
    assert not crypto_io.is_encrypted(b'{"a": 1}')
    with pytest.raises(crypto_io.CryptoError):
        crypto_io.unseal(b'{"a": 1}', passphrase="x")


def test_keyfile_mode_roundtrip(tmp_path):
    kf = crypto_io.generate_key_file(tmp_path / ".key")
    key = kf.read_bytes()
    assert len(key) == 32
    blob = crypto_io.seal(b"keyfile-secret", key=key)
    assert crypto_io.unseal(blob, key=key) == b"keyfile-secret"


def test_keyfile_mode_bad_key_raises(tmp_path):
    kf = crypto_io.generate_key_file(tmp_path / ".key")
    good = kf.read_bytes()
    blob = crypto_io.seal(b"data", key=good)
    with pytest.raises(crypto_io.InvalidPassphrase):
        crypto_io.unseal(blob, key=b"\x00" * 32)


def test_session_fallback_passphrase():
    crypto_io.set_session(passphrase="sess")
    blob = crypto_io.seal_json({"k": "v"})   # 无显式密钥 → 回退 session
    assert crypto_io.unseal_json(blob) == {"k": "v"}


# ── 契约读写加密 ──────────────────────────────────────────────────────
def _write_encrypted_contract(data_dir, *, mode, passphrase=None, key_file=None):
    if mode == "passphrase":
        crypto_io.set_session(passphrase=passphrase)
    else:
        crypto_io.set_session(key_file=key_file)
    c = Contract().to_dict()
    c["crypto"] = {"enabled": True, "mode": mode, "kdf": "pbkdf2",
                   "iterations": 200_000, "key_file": str(key_file) if key_file else None}
    contract_io.write_contract(
        data_dir, c, actor="configurator", confirm=True, allow_create=True)
    return c


def test_contract_encrypt_decrypt_passphrase(tmp_path):
    expect = _write_encrypted_contract(tmp_path, mode="passphrase", passphrase="p")
    raw = (tmp_path / "contract.json").read_bytes()
    assert crypto_io.is_encrypted(raw)          # 落盘为加密字节
    got = contract_io.read_contract(tmp_path)   # session 仍在 → 解密
    assert got["corpus"] == expect["corpus"]
    assert got["crypto"]["enabled"] is True
    # 缺密钥 → 报错
    crypto_io.reset_session()
    with pytest.raises(crypto_io.CryptoError):
        contract_io.read_contract(tmp_path)


def test_contract_encrypt_decrypt_keyfile(tmp_path):
    kf = crypto_io.generate_key_file(tmp_path / ".self-trust.key")
    expect = _write_encrypted_contract(tmp_path, mode="keyfile", key_file=kf)
    got = contract_io.read_contract(tmp_path)   # session 指向 key-file
    assert got["crypto"]["mode"] == "keyfile"
    assert got["corpus"] == expect["corpus"]


def test_contract_write_encrypted_requires_session(tmp_path):
    c = Contract().to_dict()
    c["crypto"] = {"enabled": True, "mode": "passphrase", "kdf": "pbkdf2",
                   "iterations": 200_000, "key_file": None}
    crypto_io.reset_session()                   # 无密钥
    with pytest.raises(crypto_io.CryptoError):
        contract_io.write_contract(
            tmp_path, c, actor="configurator", confirm=True, allow_create=True)


# ── 审计日志加密 ──────────────────────────────────────────────────────
def test_audit_append_read_encrypted(tmp_path):
    crypto_io.set_session(passphrase="p")
    crypto_io.set_audit_encrypted(True)
    audit_io.append(tmp_path, "approval_log", {"amount": 35, "category": "食品"})
    audit_io.append(tmp_path, "approval_log", {"amount": 6000, "category": "数码"})
    path = tmp_path / "audit" / "approval_log.jsonl"
    assert crypto_io.is_encrypted(path.read_bytes())
    records = audit_io.read_all(tmp_path, "approval_log")
    assert len(records) == 2
    assert records[0]["amount"] == 35
    assert records[1]["category"] == "数码"


def test_audit_unencrypted_backward_compat(tmp_path):
    crypto_io.set_audit_encrypted(False)
    audit_io.append(tmp_path, "approval_log", {"amount": 1})
    path = tmp_path / "audit" / "approval_log.jsonl"
    assert not crypto_io.is_encrypted(path.read_bytes())  # 明文
    assert len(audit_io.read_all(tmp_path, "approval_log")) == 1


def test_audit_append_encrypted_requires_session(tmp_path):
    crypto_io.reset_session()
    crypto_io.set_audit_encrypted(True)
    with pytest.raises(crypto_io.CryptoError):
        audit_io.append(tmp_path, "approval_log", {"amount": 1})


# ── init --encrypt 端到端（CLI 子进程，验证 _configure_crypto 链路）─────
def _cli(data_dir, *args):
    cmd = [sys.executable, str(Path(__file__).resolve().parent.parent / "cli.py"),
           "--data-dir", str(data_dir), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cli_init_encrypt_keyfile_cycle(tmp_path):
    # init --encrypt keyfile（自动生成密钥，无需 --pass）
    r = _cli(tmp_path, "init", "--corpus", "200000", "--monthly", "8000",
             "--objective", "FIRE:3000000:2036-01-01",
             "--encrypt", "--crypto-mode", "keyfile")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".self-trust.key").is_file()
    # 文件为加密字节
    assert crypto_io.is_encrypted((tmp_path / "contract.json").read_bytes())
    # judge 通过加密契约（key-file 模式自动读取 .self-trust.key）
    r2 = _cli(tmp_path, "judge", "--amount", "35", "--category", "合理享受")
    assert r2.returncode == 0, r2.stderr
    assert '"scene": "A"' in r2.stdout or '"result": "批准"' in r2.stdout
    # 审计日志也加密
    assert crypto_io.is_encrypted(
        (tmp_path / "audit" / "approval_log.jsonl").read_bytes())


def test_cli_init_encrypt_passphrase_requires_pass(tmp_path):
    # init passphrase 模式须带 --pass（写入时即加密；全局参数须置于子命令前）
    r = _cli(tmp_path, "--pass", "x", "init", "--corpus", "200000", "--monthly", "8000",
             "--objective", "FIRE:3000000:2036-01-01",
             "--encrypt", "--crypto-mode", "passphrase")
    assert r.returncode == 0, r.stderr
    # 无 --pass → 读契约报 crypto 错（退出码 5）
    r2 = _cli(tmp_path, "judge", "--amount", "35", "--category", "合理享受")
    assert r2.returncode == 5, r2.stdout
    # 带 --pass → 成功（全局参数须置于子命令前）
    r3 = _cli(tmp_path, "--pass", "x", "judge", "--amount", "35", "--category", "合理享受")
    assert r3.returncode == 0, r3.stderr
