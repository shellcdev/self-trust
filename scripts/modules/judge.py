# -*- coding: utf-8 -*-
"""审批判定模块（§4.4 统一判定 + §5.1 冷静期 + §5.1.2 白名单）—— 骨架版。

已实现（确定性路由骨架）：
- F0/F1/F2/F3 计算 → 场景 A/B/C 三段式路由；
- 白名单双上限判定（单笔 per_tx_cap 且 年度 annual_cap）；
- 冷静期触发判断（金额 > F2 阈值 且 非白名单极速）。

[STUB] 留待后续 PR：
- lag 恶化校验（场景 A 的目标进度不恶化条件，需接 F4 + objectives 遍历）；
- pending_requests 入队/提醒调度/状态迁移落盘；
- optimization_goal 三档对 B/C 边界的收紧调度（§7）；
- corpus_status=imported_pending 前置拦截（§7.3）。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from core import formulas as F
from core.models import living_baseline_value


def check_whitelist(contract: dict[str, Any], category: str,
                    amount: float) -> dict[str, Any]:
    """白名单双上限判定（§5.1.2）：单笔≤per_tx_cap 且 累计+本笔≤annual_cap。"""
    for item in contract.get("fast_track_whitelist", []):
        if item.get("name") != category:
            continue
        per_ok = amount <= float(item.get("per_tx_cap", 0))
        annual_ok = (float(item.get("used_annual", 0)) + amount
                     <= float(item.get("annual_cap", 0)))
        return {
            "listed": True,
            "fast_track": per_ok and annual_ok,
            "per_tx_ok": per_ok,
            "annual_ok": annual_ok,
            "remaining_annual": float(item.get("annual_cap", 0))
            - float(item.get("used_annual", 0)),
        }
    return {"listed": False, "fast_track": False}


def judge(
    contract: dict[str, Any],
    *,
    amount: float,
    category: str,
    planned: bool,
    today: date | None = None,
) -> dict[str, Any]:
    """§4.4 统一判定入口。返回结构化 JSON（判定 + 全部中间变量 + 文案要素）。

    LLM 铁律：禁止心算，数字必须原样引用本函数输出。
    """
    today = today or date.today()
    if amount <= 0:
        return {"ok": False, "error": "invalid_amount",
                "message": "申请金额必须为正数"}

    # ---- 中间变量（F0 ~ F3.5）----
    f0 = F.f0_net_position(
        contract.get("corpus", 0),
        contract.get("liabilities"),
        contract.get("rigid_annual_expenses"),
        contract.get("monthly_contribution", 0),
    )
    baseline = living_baseline_value(contract)
    sc = contract.get("safety_cushion", {})
    cushion = F.f1_effective_cushion(
        sc.get("mode", "months"), baseline,
        months=sc.get("months", 6), fixed=sc.get("fixed", 0),
        ratio=sc.get("ratio", 0.2), net_assets=f0["net_assets"])
    threshold_cfg = contract.get("cooldown_threshold", "auto")
    if threshold_cfg == "auto":
        threshold = F.f2_cooldown_threshold(
            cushion, contract.get("cooldown_days", 3), baseline)
    else:
        threshold = float(threshold_cfg)
    dr = contract.get("distribution_rules", {})
    invest_nominal = F.f3_monthly_invest_nominal(
        f0["monthly_net"], dr.get("invest_ratio", 0.5))
    cp = dr.get("calc_params", {})
    invest_real = F.f3_5_monthly_invest_real(
        invest_nominal,
        inflation=cp.get("inflation", 0.025),
        drawdown_factor=cp.get("drawdown_factor", 0.10),
        r_gross=cp.get("r_gross", 0.05))
    delay_simple = F.f5_impact_simple(amount, invest_nominal)

    # ---- 白名单 / 冷静期 ----
    wl = check_whitelist(contract, category, amount)
    cooldown_triggered = amount > threshold and not wl["fast_track"]

    # ---- §4.4 三场景路由（lag 恶化校验为 STUB，暂只按资金/垫口径）----
    remaining = f0["corpus"] - amount
    if remaining >= cushion:
        scene, result = "A", "批准"
        summary = "扣除后仍在安全垫之上，合理享受额度正常使用"
    elif f0["monthly_net"] > 0 and (cushion - remaining) <= f0["monthly_net"]:
        scene, result = "B", "附条件"
        summary = "扣除后跌破安全垫，但月度净流入可覆盖缺口（建议分期/延迟/缩减）"
    else:
        scene, result = "C", "驳回"
        summary = "击穿安全垫且无月度净流入兜底"

    return {
        "ok": True,
        "stub": True,   # 骨架版标记：lag 恶化 / 冷静期入队 / 调度收紧未实装
        "decision": {"scene": scene, "result": result, "summary": summary},
        "cooldown": {
            "triggered": cooldown_triggered,
            "threshold": threshold,
            "days": contract.get("cooldown_days", 3),
        },
        "whitelist": wl,
        "inputs": {
            **f0,
            "living_baseline": baseline,
            "effective_cushion": cushion,
            "invest_ratio": dr.get("invest_ratio", 0.5),
            "monthly_invest_nominal": invest_nominal,
            "monthly_invest_real": invest_real,
            "amount": float(amount),
            "category": category,
            "planned": planned,
            "remaining_after": remaining,
        },
        "impact": {
            "delay_months_simple": delay_simple,
            "note": "简化口径误差 ±20%~50%，长期目标以真实口径（F7）为准",
        },
        "formulas_used": ["F0", "F1", "F2", "F3", "F3.5", "F5"],
    }
