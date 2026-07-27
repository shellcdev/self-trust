# -*- coding: utf-8 -*-
"""报表模块（§6.1 双可视化：双轨进度条 + 近6月 ASCII 趋势图）—— STUB 占位。

[STUB] 全部业务逻辑留待后续 PR：
- objectives 双轨进度条（达成 vs 时间进度，绿/黄/红，F4 口径）；
- 近 6 月资金流向 ASCII 趋势图（monthly_history 快照 + 安全垫红线）；
- 月末快照追加 monthly_history（走 core.audit 仅追加）；
- conversational 模式「估算数据，精度有限」标注；
- 安全垫逼近红色预警（§10.2）。
"""
from __future__ import annotations

from typing import Any


def render_report(contract: dict[str, Any]) -> dict[str, Any]:
    """[STUB] 报表入口。返回结构完整但标记 stub 的结果。"""
    return {
        "ok": True,
        "stub": True,
        "message": "报表模块骨架占位：进度条/趋势图/快照 待后续 PR 实装",
        "corpus": contract.get("corpus"),
        "mode": contract.get("mode"),
        "objectives": [
            {"name": o.get("name"), "current_amount": o.get("current_amount"),
             "target_amount": o.get("target_amount"), "status": o.get("status", "active")}
            for o in contract.get("objectives", [])
        ],
        "ascii": "（报表渲染待实装，见 references/report.md · §6.1）",
        "ref": "§6.1",
    }
