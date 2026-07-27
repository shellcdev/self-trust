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


# §10.3 运行态区显式包含「lag_streak / used_annual」等计数器——它们物理上嵌在
# CONFIG 区父字段（objectives / fast_track_whitelist）内。引擎仅允许改动这些
# 运行态子字段；父字段的其余结构（weight / target_amount / caps …）仍然只读。
_ENGINE_SUBFIELD_ALLOW: dict[str, frozenset[str]] = {
    "objectives": frozenset({"lag_streak", "reward_unlocked", "reward_quota", "status"}),
    "fast_track_whitelist": frozenset({"used_annual"}),
}
# 引擎可自动执行的目标状态翻转：仅 active→overdue（超期是确定性事实，§6.4）；
# completed / archived 须用户显式确认（configurator）。
_ENGINE_STATUS_FLIPS = frozenset({("active", "overdue")})


def _engine_list_change_ok(key: str, old_list: Any, new_list: Any) -> bool:
    """引擎对 CONFIG 区列表字段的改动是否仅限运行态子字段（§10.3）。"""
    if not isinstance(old_list, list) or not isinstance(new_list, list):
        return False
    if len(old_list) != len(new_list):
        return False  # 引擎不得增删条目（结构改动属配置区）
    allowed = _ENGINE_SUBFIELD_ALLOW[key]
    for o, n in zip(old_list, new_list):
        if not isinstance(o, dict) or not isinstance(n, dict):
            return False
        for k in set(o) | set(n):
            if o.get(k) == n.get(k):
                continue
            if k not in allowed:
                return False
            if key == "objectives" and k == "status":
                src = o.get(k) or "active"
                if (src, n.get(k)) not in _ENGINE_STATUS_FLIPS:
                    return False
    return True


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
                # 例外：objectives / fast_track_whitelist 内嵌的运行态计数器
                # （lag_streak / reward_* / used_annual / active→overdue）引擎可写
                if (key in _ENGINE_SUBFIELD_ALLOW and old is not None
                        and _engine_list_change_ok(key, old.get(key), value)):
                    continue
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
