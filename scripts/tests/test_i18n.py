# -*- coding: utf-8 -*-
"""铁律 #7 机械保障：枚举值 → 中文映射无遗漏。

from __future__ import annotations：3.9 兼容守卫（与业务模块一致）。


加新枚举值（RequestStatus / ObjectiveStatus / corpus_status）必须同步在
core/i18n.py 补中文映射，否则本测试失败——把"约定"升级成"机械保障"。

目标状态直接遍历 ObjectiveStatus 枚举（与 RequestStatus 同构），
**不再维护 KNOWN_OBJECTIVE_STATUSES 集合**——加新状态即自检覆盖。
"""
from __future__ import annotations

from core.i18n import (
    REQUEST_STATUS_ZH, OBJECTIVE_STATUS_ZH, CORPUS_STATUS_ZH,
    SPEND_STATUS_ZH, CONFIG_CHANGE_STATUS_ZH, REWARD_STATUS_ZH,
    STATUS_ZH, zh_status, zh,
)
from core.models import (
    RequestStatus, ObjectiveStatus, SpendStatus, ConfigChangeStatus, RewardStatus,
)


def test_request_status_all_mapped():
    vals = {s.value for s in RequestStatus}
    missing = vals - set(REQUEST_STATUS_ZH)
    assert not missing, f"RequestStatus 未覆盖中文映射: {missing}"


def test_objective_status_all_mapped():
    # 直接遍历枚举，加新状态自动纳入自检（无需维护已知集合）
    missing = {s.value for s in ObjectiveStatus} - set(OBJECTIVE_STATUS_ZH)
    assert not missing, f"ObjectiveStatus 未覆盖中文映射: {missing}"


def test_corpus_status_mapped():
    # corpus_status 非正规 Enum，列出已知值确保映射完整
    for v in ("manual", "imported_pending", "imported_confirmed"):
        assert v in CORPUS_STATUS_ZH, f"corpus_status 缺映射: {v}"


def test_spend_status_all_mapped():
    # 直接遍历枚举，加新状态自动纳入自检（无需维护已知集合）
    missing = {s.value for s in SpendStatus} - set(SPEND_STATUS_ZH)
    assert not missing, f"SpendStatus 未覆盖中文映射: {missing}"


def test_config_change_status_all_mapped():
    # 直接遍历枚举，加新状态自动纳入自检
    missing = {s.value for s in ConfigChangeStatus} - set(CONFIG_CHANGE_STATUS_ZH)
    assert not missing, f"ConfigChangeStatus 未覆盖中文映射: {missing}"


def test_reward_status_all_mapped():
    # 直接遍历枚举，加新状态自动纳入自检（无需维护已知集合）
    missing = {s.value for s in RewardStatus} - set(REWARD_STATUS_ZH)
    assert not missing, f"RewardStatus 未覆盖中文映射: {missing}"


def test_zh_fallback_no_crash():
    # 映射不到回退原值，绝不 KeyError 崩引擎
    assert zh(REQUEST_STATUS_ZH, "unknown_new_state") == "unknown_new_state"


def test_zh_returns_chinese():
    assert zh(REQUEST_STATUS_ZH, "cooling") == "冷静期"
    assert zh(OBJECTIVE_STATUS_ZH, "completed") == "已达成"
    assert zh(CORPUS_STATUS_ZH, "manual") == "手动录入"


def test_status_zh_covers_all_families():
    # 渲染层统一映射 zh_status 须覆盖全部状态族（含 SpendStatus/ConfigChangeStatus），
    # 否则渲染任意状态值仍可能泄漏英文枚举（铁律 #7 机械保障）。
    families = [
        (RequestStatus, {s.value for s in RequestStatus}),
        (ObjectiveStatus, {s.value for s in ObjectiveStatus}),
        (SpendStatus, {s.value for s in SpendStatus}),
        (ConfigChangeStatus, {s.value for s in ConfigChangeStatus}),
        (RewardStatus, {s.value for s in RewardStatus}),
    ]
    for _enum, vals in families:
        missing = vals - set(STATUS_ZH)
        assert not missing, f"{_enum.__name__} 未并入 STATUS_ZH 渲染层映射: {missing}"
        for v in vals:
            assert zh_status(v) != v, f"{_enum.__name__}.{v} 经 zh_status 仍回退原值（未中文化）"


def test_zh_status_fallback_no_crash():
    # 未知状态值回退原值，绝不 KeyError 崩引擎
    assert zh_status("brand_new_state") == "brand_new_state"
