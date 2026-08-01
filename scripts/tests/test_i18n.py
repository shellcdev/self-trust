# -*- coding: utf-8 -*-
"""铁律 #7 机械保障：枚举值 → 中文映射无遗漏。

加新枚举值（RequestStatus / ObjectiveStatus / corpus_status）必须同步在
core/i18n.py 补中文映射，否则本测试失败——把"约定"升级成"机械保障"。
"""
from core.i18n import (
    REQUEST_STATUS_ZH, OBJECTIVE_STATUS_ZH, CORPUS_STATUS_ZH, zh,
)
from core.models import RequestStatus

# 目标状态（models.Objective.status 为散字符串，集中登记以便自检）
KNOWN_OBJECTIVE_STATUSES = {"active", "completed", "overdue", "archived"}


def test_request_status_all_mapped():
    vals = {s.value for s in RequestStatus}
    missing = vals - set(REQUEST_STATUS_ZH)
    assert not missing, f"RequestStatus 未覆盖中文映射: {missing}"


def test_objective_status_all_mapped():
    missing = KNOWN_OBJECTIVE_STATUSES - set(OBJECTIVE_STATUS_ZH)
    assert not missing, f"目标状态未覆盖中文映射: {missing}"


def test_corpus_status_mapped():
    # corpus_status 非正规 Enum，列出已知值确保映射完整
    for v in ("manual", "imported_pending", "imported_confirmed"):
        assert v in CORPUS_STATUS_ZH, f"corpus_status 缺映射: {v}"


def test_zh_fallback_no_crash():
    # 映射不到回退原值，绝不 KeyError 崩引擎
    assert zh(REQUEST_STATUS_ZH, "unknown_new_state") == "unknown_new_state"


def test_zh_returns_chinese():
    assert zh(REQUEST_STATUS_ZH, "cooling") == "冷静期"
    assert zh(OBJECTIVE_STATUS_ZH, "completed") == "已达成"
    assert zh(CORPUS_STATUS_ZH, "manual") == "手动录入"
