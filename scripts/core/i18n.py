# -*- coding: utf-8 -*-
"""枚举值 → 中文标签（铁律 #7：引擎用户可见串禁露英文枚举/字段名）。

from __future__ import annotations：3.9 兼容守卫（dict[str,str] / Mapping[str,str]
等注解在 3.9 下惰性求值，避免 X | Y 等新语法误触 SyntaxError）。


集中维护，杜绝各模块散落 ``_*_ZH`` 字典导致加新枚举值时漏映射。
取标签一律走 :func:`zh`，映射不到时**回退原值**（绝不 ``KeyError`` 崩引擎）。
"""
from __future__ import annotations

from typing import Mapping


# 申请状态（core.models.RequestStatus）
REQUEST_STATUS_ZH: dict[str, str] = {
    "cooling": "冷静期",
    "withdrawn": "已撤回",
    "decided": "已裁决",
    "expired": "已过期",
}

# 目标状态（core.models.ObjectiveStatus）
OBJECTIVE_STATUS_ZH: dict[str, str] = {
    "active": "进行中",
    "completed": "已达成",
    "overdue": "已超期",
    "archived": "已归档",
}

# 资产来源状态（contract.corpus_status）
CORPUS_STATUS_ZH: dict[str, str] = {
    "manual": "手动录入",
    "imported_pending": "待核对",
    "imported_confirmed": "已确认",
}

# 审批支出台账状态（core.models.SpendStatus）
SPEND_STATUS_ZH: dict[str, str] = {
    "cooling": "冷静期",
    "approved": "已批准",
    "withdrawn": "已撤回",
    "expired": "已过期",
}

# 配置变更待生效队列状态（core.models.ConfigChangeStatus）
CONFIG_CHANGE_STATUS_ZH: dict[str, str] = {
    "pending": "待生效",
    "applied": "已生效",
    "failed": "已失败",
}


def zh(mapping: Mapping[str, str], value) -> str:
    """取枚举值的中文标签；映射不到回退原值（不崩引擎）。"""
    return mapping.get(value, value)
