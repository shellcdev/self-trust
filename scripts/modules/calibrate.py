# -*- coding: utf-8 -*-
"""月度校准模块（§6.2 rebalance / 收入放松 + §6.4 目标生命周期）—— STUB 占位。

[STUB] 全部业务逻辑留待后续 PR：
- lag_streak 缓冲（连续 2 月 lag>0 才触发，F4 口径）；
- 柔性方案优先（target_amount 下调 / deadline 顺延建议，写 rebalance_override 临时层）；
- 刚性方案（boost 上限 +15pct + 非计划审批通过率收紧）；
- 收入下跌自动放松（monthly_history[].income 连续 2 月降 ≥20% → 宽松态）；
- 次月自动回滚（rebalance_override 过期清空，原始权重不变）；
- §6.4 生命周期迁移提示（completed / overdue / archived，用户显式确认）。

约束提醒：校准只写运行态区（rebalance_override / lag_streak / last_calibrate），
绝不改配置区 objectives.weight（§10.3；由 test_contract_guard 强制）。
"""
from __future__ import annotations

from datetime import date
from typing import Any


def calibrate(contract: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """[STUB] 月度校准入口。返回结构完整但标记 stub 的结果。"""
    today = today or date.today()
    return {
        "ok": True,
        "stub": True,
        "message": "校准模块骨架占位：lag_streak 缓冲/柔性方案/收入放松/回滚 待后续 PR 实装",
        "last_calibrate": contract.get("last_calibrate"),
        "rebalance_override": contract.get("rebalance_override"),
        "actions": [],
        "ref": "§6.2 / §6.4",
    }
