# -*- coding: utf-8 -*-
"""初始化模块（§7.1 懒人模板 / §7.2 演示数据 —— 演示部分留 stub）。

懒人模板：必填 3 项（corpus / monthly_contribution / objectives），
其余参数统一固化 balanced 默认值（§7.1 表）。

初始化护栏（§7.1）：
1. 重复初始化防护：contract.json 已存在 → 拒绝覆盖，提示走 记账自定义 / 记账重置；
2. 净口径警告：未补 liabilities / rigid_annual_expenses → 回执附毛口径警告；
3. deadline 校验：必须晚于 start_date（当日），否则驳回该目标；
4. 对账锚点：reconcile.last_reconcile = 初始化当日。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core import contract as contract_io
from core.contract import GuardError  # noqa: F401  (re-export for callers)


def lazy_init(
    data_dir: Path,
    *,
    corpus: float,
    monthly_contribution: float,
    objectives: list[dict[str, Any]],
    today: date | None = None,
) -> dict[str, Any]:
    """懒人一键初始化。返回结构化结果 {ok, contract_path, warnings, rejected_objectives}。

    已存在契约 → 返回 {ok: False, error: "exists", ...}（护栏 1，不覆盖）。
    """
    today = today or date.today()
    if contract_io.contract_exists(data_dir):
        return {
            "ok": False,
            "error": "exists",
            "message": (
                "已存在契约，增量修改请用 `记账自定义`；"
                "如需彻底重建请用 `记账重置`（带二次确认，且保留 audit 目录历史）"
            ),
        }

    if not objectives or len(objectives) > 3:
        return {"ok": False, "error": "objectives_count",
                "message": "核心目标须为 1~3 个"}

    warnings: list[str] = []
    rejected: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    today_iso = today.isoformat()

    for obj in objectives:
        deadline = obj.get("deadline")
        # 护栏 3：deadline 必须晚于 start_date（当日）；None 允许（无期限目标）
        if deadline is not None and str(deadline) <= today_iso:
            rejected.append({"name": obj.get("name"), "reason":
                             f"deadline {deadline} 不晚于当日 {today_iso}，不生成负周期"})
            continue
        accepted.append(obj)

    if not accepted:
        return {"ok": False, "error": "no_valid_objectives",
                "message": "所有目标均未通过 deadline 校验",
                "rejected_objectives": rejected}

    c = contract_io.new_default_contract()
    c["corpus"] = float(corpus)
    c["monthly_contribution"] = float(monthly_contribution)
    n = len(accepted)
    c["objectives"] = [
        {
            "name": o["name"],
            "weight": round(1.0 / n, 6),          # §7.1 多目标等权起步
            "current_amount": float(o.get("current_amount", 0) or 0),
            "start_date": today_iso,              # §7.1 start_date = 初始化当日
            "deadline": o.get("deadline"),
            "target_amount": o.get("target_amount"),
            "lag_streak": 0,
            "reward_unlocked": False,
            "reward_quota": 0.0,
            "status": "active",
        }
        for o in accepted
    ]
    # 护栏 4：对账锚点从首日起算
    c["reconcile"]["last_reconcile"] = today_iso

    # 护栏 2：净口径警告
    if not c["liabilities"] and not c["rigid_annual_expenses"]:
        warnings.append(
            "⚠️ 当前 monthly_contribution 可能为毛口径（未录入负债/刚性年支出），"
            "living_baseline / safety_cushion 据此偏高，"
            "建议尽快 `记账自定义` 补 liabilities / rigid_annual_expenses"
        )

    path = contract_io.write_contract(
        data_dir, c, actor="configurator", confirm=True, allow_create=True)
    return {
        "ok": True,
        "contract_path": str(path),
        "warnings": warnings,
        "rejected_objectives": rejected,
        "message": "已生成默认契约（balanced），可随时说『自定义』逐项调",
    }


def demo_scenarios(contract: dict[str, Any]) -> dict[str, Any]:
    """§7.2 三场景模拟演示（不落地真实账目）。

    [STUB] 骨架占位：后续 PR 用真实契约参数跑 F1/F2 + judge 干跑三场景。
    """
    return {
        "ok": True,
        "stub": True,
        "scenarios": [
            {"id": 1, "name": "小额合理消费", "expect": "场景A 直接批准", "ref": "§7.2"},
            {"id": 2, "name": "大额非计划消费", "expect": "触发 3 天冷静期", "ref": "§7.2"},
            {"id": 3, "name": "击穿安全垫大额消费", "expect": "驳回 + 分期替代方案", "ref": "§7.2"},
        ],
        "note": "演示不影响真实账户；具体测算待 judge 模块实装后接入",
    }
