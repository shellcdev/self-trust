# -*- coding: utf-8 -*-
"""pytest 公共 fixture：temp dir 覆盖 data-dir，不碰真实数据（工程规范 #8）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scripts/ 加入 sys.path，使 core / modules 可导入（与 cli.py 同机制）
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """独立临时数据目录（等价 --data-dir 覆盖），测试互不串数据。"""
    d = tmp_path / "selftrust-data"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def base_contract(tmp_data_dir: Path) -> dict:
    """已初始化的基础契约（懒人模板：corpus 20万 / 月净流入 8000 / FIRE 目标）。"""
    from datetime import date
    from modules.initialize import lazy_init
    from core.contract import read_contract

    result = lazy_init(
        tmp_data_dir,
        corpus=200000,
        monthly_contribution=8000,
        objectives=[{"name": "FIRE", "target_amount": 3000000,
                     "deadline": "2036-01-01"}],
        today=date(2026, 7, 27),
    )
    assert result["ok"], result
    return read_contract(tmp_data_dir)
