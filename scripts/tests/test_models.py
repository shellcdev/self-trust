# -*- coding: utf-8 -*-
"""默认契约数据（models.Contract）标准值锁定测试。

重点守护标准类目词汇表（distribution_rules.allowed_categories）：
它是新装用户开箱即用的推荐清单，回归会悄悄削弱开箱体验。
"""
from __future__ import annotations

from core import models


# 标准类目词汇表预期（与 models.py 默认值保持一致；逻辑分组见 models.py 注释）。
EXPECTED_STD_CATEGORIES = [
    "食品", "居住", "交通", "通讯", "医疗", "教育",
    "服饰", "日用",
    "合理享受", "娱乐", "旅行", "社交", "宠物",
    "数码家电", "保险",
    "投资", "理财", "基金", "股票", "黄金",
    "其他",
]


def test_default_allowed_categories_is_standard_set():
    """默认契约的标准类目词汇表等于预期清单，且保持顺序。"""
    default = models.Contract().to_dict()
    cats = default["distribution_rules"]["allowed_categories"]
    assert cats == EXPECTED_STD_CATEGORIES


def test_default_allowed_categories_no_duplicates():
    """标准类目词汇表无重复（去重是开关的隐含契约，默认值本身也不能有重）。"""
    cats = models.Contract().to_dict()["distribution_rules"]["allowed_categories"]
    assert len(cats) == len(set(cats))


def test_reasonable_enjoyment_always_present():
    """「合理享受」是框架受保护的 joy 额度类目，必须始终在标准清单内。"""
    cats = models.Contract().to_dict()["distribution_rules"]["allowed_categories"]
    assert "合理享受" in cats
