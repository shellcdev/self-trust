# -*- coding: utf-8 -*-
"""CLI 解析与分发测试（§8.3 / §9）。

覆盖：
- build_parser 子命令齐备；
- judge 子命令默认 action=submit + 字段解析；
- _parse_objective 合法 / 非法（目标额须为正）；
- main 端到端分发 init → 落盘契约（用临时 data-dir，不碰真实数据）。
"""
from __future__ import annotations

import pytest

from cli import build_parser, main, _parse_objective


EXPECTED_SUBCOMMANDS = {
    "init", "judge", "demo", "report", "reconcile", "calibrate",
    "reward", "reset", "appeal", "objective", "log", "import-asset",
}


def _subcommand_names(parser):
    return set(parser._subparsers._group_actions[0].choices.keys())


def test_parser_has_all_subcommands():
    assert EXPECTED_SUBCOMMANDS <= _subcommand_names(build_parser())


def test_judge_default_action_submit():
    args = build_parser().parse_args(
        ["judge", "--amount", "6000", "--category", "合理享受"])
    assert args.command == "judge"
    assert args.action == "submit"
    assert args.amount == 6000.0
    assert args.category == "合理享受"


def test_parse_objective_ok_and_invalid():
    assert _parse_objective("FIRE:3000000:2036-01-01") == {
        "name": "FIRE", "target_amount": 3000000.0, "deadline": "2036-01-01"}
    assert _parse_objective("无期限目标") == {"name": "无期限目标"}
    with pytest.raises(ValueError):
        _parse_objective("坏目标:-100:2036-01-01")


def test_init_dispatch_creates_contract(tmp_data_dir):
    # 注意：--data-dir 是主解析器全局参数，须置于子命令之前（argparse 路由规则）
    code = main([
        "--data-dir", str(tmp_data_dir),
        "init", "--corpus", "200000", "--monthly", "8000",
        "--objective", "FIRE:3000000:2036-01-01",
    ])
    assert code == 0
    assert (tmp_data_dir / "contract.json").is_file()
