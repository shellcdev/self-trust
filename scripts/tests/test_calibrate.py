# -*- coding: utf-8 -*-
"""校准模块测试（§6.2 缓冲/柔性/收入放松/回滚）—— 骨架版冒烟。

[STUB] 校准业务逻辑未实装（见 modules/calibrate.py）；本套件当前仅验证
stub 契约结构，后续 PR 实装时替换为完整用例（缓冲 2 月/柔性优先/放松/回滚）。
"""
from __future__ import annotations

from modules.calibrate import calibrate


def test_stub_returns_structured_result(base_contract):
    r = calibrate(base_contract)
    assert r["ok"] is True
    assert r["stub"] is True          # 实装后本断言应删除并补完整用例
    assert "rebalance_override" in r
    assert r["actions"] == []


def test_stub_does_not_mutate_contract(base_contract):
    import copy
    snapshot = copy.deepcopy(base_contract)
    calibrate(base_contract)
    assert base_contract == snapshot   # 校准 stub 不得有副作用
