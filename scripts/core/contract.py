# -*- coding: utf-8 -*-
"""契约读写 + 数据目录解析 + 三区权限强制（设计文档 §2 / §8.3 #6 / §10.3 / §5.4）。

数据目录解析优先级（写进 README，规范 #6）：
    命令行 --data-dir  >  环境变量 SELFTRUST_DATA_DIR  >  默认 <workspace>/memory/trust/
默认 <workspace> 取当前工作目录（skill 运行时由调用方保证 cwd 或显式传参），
代码零个人绝对路径硬编码（假设开源）。

三区权限强制（公正性地基，test_contract_guard 最高优先）：
- actor="engine"：只允许改运行态区字段；触碰配置区 → PermissionError（显式报错不吞）。
- actor="configurator"：可改配置区，但核心护栏字段（§5.4）必须 confirm=True
  （模拟二次确认闸门），否则 GuardError。
- 审计区字段禁止写入 contract.json（物理分离，走 core.audit）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .models import Contract, FIELD_ZONES, CORE_GUARD_FIELDS, Zone

ENV_DATA_DIR = "SELFTRUST_DATA_DIR"
DEFAULT_SUBPATH = Path("memory") / "trust"
CONTRACT_FILENAME = "contract.json"


class GuardError(PermissionError):
    """三区权限 / §5.4 闸门违规（显式抛出，不吞错）。"""


def resolve_data_dir(cli_data_dir: Optional[str] = None) -> Path:
    """解析数据目录：命令行 > env > 默认 <cwd>/memory/trust/。"""
    if cli_data_dir:
        return Path(cli_data_dir).expanduser()
    env = os.environ.get(ENV_DATA_DIR)
    if env:
        return Path(env).expanduser()
    return Path.cwd() / DEFAULT_SUBPATH


def contract_path(data_dir: Path) -> Path:
    return Path(data_dir) / CONTRACT_FILENAME


def contract_exists(data_dir: Path) -> bool:
    return contract_path(data_dir).is_file()


def read_contract(data_dir: Path) -> dict[str, Any]:
    """读契约；不存在则 FileNotFoundError（显式，不返回空契约假装存在）。"""
    path = contract_path(data_dir)
    if not path.is_file():
        raise FileNotFoundError(f"契约不存在: {path}（请先运行 init）")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _validate_zones(new: dict[str, Any], old: Optional[dict[str, Any]],
                    actor: str, confirm: bool) -> None:
    for key, value in new.items():
        zone = FIELD_ZONES.get(key)
        if zone is None:
            raise GuardError(f"未知契约字段（schema 外禁止写入）: {key}")
        if zone is Zone.AUDIT:
            raise GuardError(
                f"审计区字段 {key} 禁止写入 contract.json（物理分离，走 core.audit）")
        changed = old is None or old.get(key) != value
        if not changed:
            continue
        if zone is Zone.CONFIG:
            if actor != "configurator":
                raise GuardError(
                    f"引擎无权修改配置区字段: {key}（§10.3 最小权限）")
            if key in CORE_GUARD_FIELDS and not confirm:
                raise GuardError(
                    f"核心护栏字段 {key} 修改须经 §5.4 二次确认（confirm=True）")


def write_contract(
    data_dir: Path,
    contract: dict[str, Any],
    *,
    actor: str,
    confirm: bool = False,
    allow_create: bool = False,
) -> Path:
    """写契约（整文件原子替换），写前强制三区权限校验。

    actor: "engine"（运行态区可写）| "configurator"（配置区可写，护栏字段须 confirm）
    allow_create: 仅初始化/重置路径可 True；常规写要求契约已存在。
    """
    if actor not in ("engine", "configurator"):
        raise GuardError(f"未知 actor: {actor!r}")
    data_dir = Path(data_dir)
    path = contract_path(data_dir)
    old: Optional[dict[str, Any]] = None
    if path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            old = json.load(f)
    elif not allow_create:
        raise FileNotFoundError(f"契约不存在: {path}（请先运行 init）")

    if old is None and actor != "configurator":
        raise GuardError("契约创建（初始化/重置）仅配置者可执行")

    _validate_zones(contract, old, actor, confirm)

    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def new_default_contract() -> dict[str, Any]:
    """balanced 默认契约骨架（§7.1 固化默认值来源）。"""
    return Contract().to_dict()
