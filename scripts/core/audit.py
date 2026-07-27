# -*- coding: utf-8 -*-
"""审计区仅追加写入（设计文档 §10.1 / 公式 F8）。

- 落点：<data-dir>/audit/<log_name>.jsonl，每行一条 JSON（仅追加，不提供删除/改写接口）。
- 撤回/覆写以「追加反向记录」表达，绝不抹除原记录。
- 关键失败显式抛错不吞（规范 #8）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AUDIT_SUBDIR = "audit"

# 合法审计日志名（§10.1 五类 + 契约重建事件复用 override_log）
VALID_LOGS = frozenset({
    "approval_log", "appeal_log", "override_log", "reward_log", "monthly_history",
})


def audit_dir(data_dir: Path) -> Path:
    return Path(data_dir) / AUDIT_SUBDIR


def log_path(data_dir: Path, log_name: str) -> Path:
    if log_name not in VALID_LOGS:
        raise ValueError(f"未知审计日志: {log_name}（合法值: {sorted(VALID_LOGS)}）")
    return audit_dir(data_dir) / f"{log_name}.jsonl"


def append(data_dir: Path, log_name: str, record: dict[str, Any]) -> Path:
    """仅追加一条审计记录。record 必须是可 JSON 序列化 dict。"""
    if not isinstance(record, dict):
        raise TypeError(f"审计记录必须为 dict，得到 {type(record).__name__}")
    path = log_path(data_dir, log_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return path


def read_all(data_dir: Path, log_name: str) -> list[dict[str, Any]]:
    """只读全量读取（记账日志 查询用）；文件不存在返回空列表。"""
    path = log_path(data_dir, log_name)
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                # 显式报错不吞：审计文件损坏是关键失败
                raise ValueError(f"{path} 第 {i} 行损坏: {e}") from e
    return records


def append_approval_snapshot(data_dir: Path, snapshot: dict[str, Any]) -> Path:
    """F8 审批快照落盘（结构由 formulas.f8_audit_snapshot 组装校验）。"""
    for key in ("time", "amount", "category", "scene", "inputs",
                "formulas_used", "decision"):
        if key not in snapshot:
            raise ValueError(f"F8 快照缺少必备键: {key}")
    return append(data_dir, "approval_log", snapshot)
