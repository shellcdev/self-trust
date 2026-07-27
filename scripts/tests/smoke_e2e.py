# -*- coding: utf-8 -*-
"""端到端冒烟（质量门禁 #2）：init → 冷静期 → withdraw → C 驳回 → calibrate
→ report → reward → reset。直接调 cli.main（同真实命令路径），temp data-dir。

运行：python scripts/tests/smoke_e2e.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cli  # noqa: E402


def run(*argv: str) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(list(argv))
    out = json.loads(buf.getvalue())
    out["_exit"] = code
    return out


def main() -> int:
    d = tempfile.mkdtemp(prefix="st-smoke-")
    base = ["--data-dir", d, "--today", "2026-07-27"]
    checks: list[tuple[str, bool]] = []

    # 1. init
    r = run(*base, "init", "--corpus", "200000", "--monthly", "8000",
            "--objective", "FIRE:3000000:2036-01-01")
    checks.append(("init ok", r["ok"] and r["_exit"] == 0))

    # 2. judge 大额非计划 → 冷静期入队
    r = run(*base, "judge", "--amount", "6000", "--category", "合理享受")
    rid = r.get("request_id")
    checks.append(("cooldown triggered + request_id",
                   r["ok"] and r["cooldown"]["triggered"] and bool(rid)))

    # 3. withdraw → 正向反馈要素（公式估算，非硬编码）
    r = run(*base, "judge", "--action", "withdraw", "--request-id", rid)
    fb = r.get("feedback", {})
    checks.append(("withdraw ok + formula-based feedback",
                   r["ok"] and r["status"] == "withdrawn"
                   and fb.get("ahead_months_simple") == 1.5
                   and fb.get("ahead_months_real") is not None))
    # 落盘状态转 withdrawn
    contract = json.loads((Path(d) / "contract.json").read_text(encoding="utf-8"))
    checks.append(("pending persisted withdrawn",
                   contract["pending_requests"][0]["status"] == "withdrawn"))

    # 4. 击穿安全垫 → 场景 C 驳回
    r = run(*base, "judge", "--amount", "199000", "--category", "合理享受")
    checks.append(("scene C reject", r["decision"]["scene"] == "C"))

    # 5. calibrate 触发状态翻转（造超期目标：用 2036-01-02 之后的 today）
    r = run("--data-dir", d, "--today", "2036-06-01", "calibrate")
    flips = [c for c in r.get("changes", []) if c.get("type") == "lifecycle"]
    checks.append(("calibrate lifecycle flip",
                   r["ok"] and flips and flips[0]["to"] == "overdue"))

    # 6. report → JSON + monthly_history 追加
    r = run(*base, "report")
    checks.append(("report ok + snapshot",
                   r["ok"] and r["snapshot_appended"] is not None
                   and "█" in r["ascii"] or "░" in r["ascii"]))
    hist = (Path(d) / "audit" / "monthly_history.jsonl")
    checks.append(("monthly_history file", hist.is_file()))

    # 7. reward：造 >120% 达成 → unlock → quota > 0
    cpath = Path(d) / "contract.json"
    contract = json.loads(cpath.read_text(encoding="utf-8"))
    contract["objectives"][0]["current_amount"] = 3700000
    contract["objectives"][0]["status"] = "active"
    cpath.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    r = run(*base, "reward", "--action", "unlock")
    checks.append(("reward unlocked quota>0",
                   r["ok"] and r["unlocked"]
                   and r["unlocked"][0]["reward_quota"] == 140000.0))
    r = run(*base, "reward", "--action", "claim", "--objective", "FIRE",
            "--amount", "40000", "--purpose", "旅行")
    checks.append(("reward claim decrements",
                   r["ok"] and r["quota_remaining"] == 100000.0))

    # 8. reset：无确认拒绝 → 确认后重建，audit 不丢
    approvals_before = sum(1 for _ in open(
        Path(d) / "audit" / "approval_log.jsonl", encoding="utf-8"))
    r = run(*base, "reset")
    checks.append(("reset needs confirm", not r["ok"] and r["error"] == "need_confirm"))
    r = run(*base, "reset", "--confirm", "--corpus", "50000", "--monthly", "5000",
            "--objective", "新目标:500000:2030-01-01")
    approvals_after = sum(1 for _ in open(
        Path(d) / "audit" / "approval_log.jsonl", encoding="utf-8"))
    contract = json.loads(cpath.read_text(encoding="utf-8"))
    checks.append(("reset rebuilt + audit kept",
                   r["ok"] and r.get("reset") and contract["corpus"] == 50000
                   and approvals_after == approvals_before))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    print(f"\n{len(checks) - len(failed)}/{len(checks)} passed; data-dir={d}")
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
