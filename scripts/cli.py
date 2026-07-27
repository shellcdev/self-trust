# -*- coding: utf-8 -*-
"""self-trust 统一 CLI 入口（设计文档 §8.3 #1 / §9）。

子命令：judge | init | report | reconcile | calibrate | reward | log
- 全部输出结构化 JSON（stdout，UTF-8）；LLM 铁律：禁止心算，数字原样引用本输出。
- 数据目录解析优先级：--data-dir > SELFTRUST_DATA_DIR > <cwd>/memory/trust/（README）。
- 引擎错误显式返回 {"ok": false, "error": ...}，退出码非 0，不吞错。

示例：
    python scripts/cli.py init --json --data-dir /tmp/st \\
        --corpus 200000 --monthly 8000 \\
        --objective "FIRE:3000000:2036-01-01"
    python scripts/cli.py judge --json --amount 6000 --category 合理享受
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 允许 `python scripts/cli.py` 直接运行（scripts/ 加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import audit as audit_io          # noqa: E402
from core import contract as contract_io    # noqa: E402
from core.contract import GuardError        # noqa: E402
from modules import calibrate as mod_cal    # noqa: E402
from modules import initialize as mod_init  # noqa: E402
from modules import judge as mod_judge      # noqa: E402
from modules import report as mod_report    # noqa: E402


def _emit(payload: dict, code: int = 0) -> int:
    # Windows 控制台可能默认 GBK，强制 UTF-8 防中文/符号编码失败（跨平台一致）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return code


def _parse_objective(spec: str) -> dict:
    """解析 --objective "名称:目标额:期限"；目标额/期限可省略（无期限目标）。"""
    parts = spec.split(":")
    obj: dict = {"name": parts[0]}
    if len(parts) > 1 and parts[1]:
        obj["target_amount"] = float(parts[1])
    if len(parts) > 2 and parts[2]:
        obj["deadline"] = parts[2]
    return obj


def cmd_init(args) -> int:
    data_dir = contract_io.resolve_data_dir(args.data_dir)
    objectives = [_parse_objective(s) for s in (args.objective or [])]
    result = mod_init.lazy_init(
        data_dir,
        corpus=args.corpus,
        monthly_contribution=args.monthly,
        objectives=objectives,
    )
    return _emit(result, 0 if result.get("ok") else 1)


def cmd_judge(args) -> int:
    data_dir = contract_io.resolve_data_dir(args.data_dir)
    contract = contract_io.read_contract(data_dir)
    result = mod_judge.judge(
        contract, amount=args.amount, category=args.category,
        planned=args.planned)
    if result.get("ok"):
        # F8 快照落审计（骨架版：结构完整，字段随 judge 实装扩充）
        audit_io.append_approval_snapshot(data_dir, {
            "time": datetime.now().isoformat(timespec="seconds"),
            "amount": args.amount,
            "category": args.category,
            "scene": result["decision"]["scene"],
            "inputs": result["inputs"],
            "formulas_used": result["formulas_used"],
            "decision": result["decision"],
            "alt_plan": "",
        })
    return _emit(result, 0 if result.get("ok") else 1)


def cmd_report(args) -> int:
    data_dir = contract_io.resolve_data_dir(args.data_dir)
    contract = contract_io.read_contract(data_dir)
    return _emit(mod_report.render_report(contract))


def cmd_reconcile(args) -> int:
    # [STUB] §3.2 hybrid 对账：核对/修正 corpus 等，更新 last_reconcile；后续 PR 实装
    return _emit({"ok": True, "stub": True,
                  "message": "reconcile 骨架占位（§3.2），待后续 PR 实装"})


def cmd_calibrate(args) -> int:
    data_dir = contract_io.resolve_data_dir(args.data_dir)
    contract = contract_io.read_contract(data_dir)
    return _emit(mod_cal.calibrate(contract))


def cmd_reward(args) -> int:
    # [STUB] §6.3 里程碑奖励支取：F6 校验 + reward_quota 递减 + reward_log；后续 PR 实装
    return _emit({"ok": True, "stub": True,
                  "message": "reward 骨架占位（§6.3），待后续 PR 实装"})


def cmd_log(args) -> int:
    data_dir = contract_io.resolve_data_dir(args.data_dir)
    records = audit_io.read_all(data_dir, args.name)
    return _emit({"ok": True, "log": args.name,
                  "count": len(records), "records": records})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="self-trust",
        description="self-trust 自律记账引擎（确定性判定，LLM 只渲染不心算）")
    p.add_argument("--data-dir", default=None,
                   help="数据目录（优先级：本参数 > SELFTRUST_DATA_DIR > <cwd>/memory/trust/）")
    p.add_argument("--json", action="store_true", default=True,
                   help="结构化 JSON 输出（默认且唯一格式）")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="懒人一键初始化（§7.1）")
    sp.add_argument("--corpus", type=float, required=True, help="资金池初始余额")
    sp.add_argument("--monthly", type=float, required=True,
                    help="月度净流入（净口径：税后收入-负债月供-刚性月摊）")
    sp.add_argument("--objective", action="append", required=True,
                    help='目标 "名称:目标额:期限"（1~3 个，可重复传）')
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("judge", help="支取审批统一判定（§4.4）")
    sp.add_argument("--amount", type=float, required=True)
    sp.add_argument("--category", required=True)
    sp.add_argument("--planned", action="store_true", help="是否计划内")
    sp.set_defaults(func=cmd_judge)

    sp = sub.add_parser("report", help="记账报表（§6.1）[stub]")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("reconcile", help="hybrid 对账（§3.2）[stub]")
    sp.set_defaults(func=cmd_reconcile)

    sp = sub.add_parser("calibrate", help="月度校准（§6.2）[stub]")
    sp.set_defaults(func=cmd_calibrate)

    sp = sub.add_parser("reward", help="里程碑奖励支取（§6.3）[stub]")
    sp.set_defaults(func=cmd_reward)

    sp = sub.add_parser("log", help="审计留痕只读查询（§10.1）")
    sp.add_argument("--name", default="approval_log",
                    choices=sorted(audit_io.VALID_LOGS))
    sp.set_defaults(func=cmd_log)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        return _emit({"ok": False, "error": "not_found", "message": str(e)}, 2)
    except GuardError as e:
        return _emit({"ok": False, "error": "guard", "message": str(e)}, 3)
    except (ValueError, TypeError) as e:
        return _emit({"ok": False, "error": "invalid", "message": str(e)}, 4)


if __name__ == "__main__":
    raise SystemExit(main())
