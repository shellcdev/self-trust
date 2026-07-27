# -*- coding: utf-8 -*-
"""治理模块：申诉/人工覆写（§5.2）+ 记账重置（§7.1.1）+ hybrid 对账（§3.2）。

确定性规则（公正性靠代码不靠 AI）：
- 申诉：按 §4.4 统一判定重审，仍 C → appeal_count += 1；计数按同一 request_id
  累计（换申请自动归零，锚点存于 appeal_log 最后一条）；满 3 次开放一次人工覆写；
- 覆写：仅作用于当次支取，必须 confirm=True 确认知悉目标延后时长（F5/F7 测算），
  写 override_log，消耗申诉计数归零——兜底是例外非常态；
- 重置：二次确认闸门；仅重写 contract.json，audit/ 全部保留（§10.1 仅追加不可删）；
  重建事件（含旧契约哈希）记 override_log，推倒重来本身可复盘；
- 对账：软确认——用户拍板差异，引擎不自动改写 corpus（§10.3）。

LLM 铁律：禁止心算，数字必须原样引用引擎输出。
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from core import audit as audit_io
from core import contract as contract_io
from core import formulas as F

APPEAL_OVERRIDE_THRESHOLD = 3   # §5.2 连续申诉驳回满 3 次开放人工覆写


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _last_appeal_request(data_dir: Path) -> Optional[str]:
    records = audit_io.read_all(data_dir, "appeal_log")
    for rec in reversed(records):
        if rec.get("request_id"):
            return rec["request_id"]
    return None


def _find_request(contract: dict[str, Any], request_id: str) -> dict[str, Any] | None:
    for r in contract.get("pending_requests", []):
        if r.get("request_id") == request_id:
            return r
    return None


# ================================================================ §5.2 申诉
def appeal(
    data_dir: Path,
    *,
    request_id: str,
    reason: str,
    today: date | None = None,
) -> dict[str, Any]:
    """驳回后申诉：按 §4.4 重审；仍不达标维持驳回并累计 appeal_count。"""
    from modules.judge import judge  # 延迟导入避免环

    today = today or date.today()
    contract = contract_io.read_contract(data_dir)
    entry = _find_request(contract, request_id)
    if entry is None:
        return {"ok": False, "error": "request_not_found",
                "message": f"未找到申请 {request_id}"}

    # 换申请自动归零（计数按 request_id 维度，§5.2）
    if _last_appeal_request(data_dir) != request_id:
        contract["appeal_count"] = 0

    verdict = judge(contract, amount=float(entry["amount"]),
                    category=entry.get("category", ""),
                    planned=bool(entry.get("planned")), today=today)
    if not verdict.get("ok"):
        return verdict

    upheld = verdict["decision"]["scene"] == "C"
    if upheld:
        contract["appeal_count"] = int(contract.get("appeal_count", 0)) + 1
    else:
        contract["appeal_count"] = 0   # 重审改判 → 计数归零
    contract_io.write_contract(data_dir, contract, actor="engine")

    override_open = upheld and contract["appeal_count"] >= APPEAL_OVERRIDE_THRESHOLD
    audit_io.append(data_dir, "appeal_log", {
        "time": _now(), "request_id": request_id, "reason": reason,
        "result": "维持驳回" if upheld else f"改判：{verdict['decision']['result']}",
        "appeal_count": contract["appeal_count"],
        "override_open": override_open,
    })
    return {
        "ok": True, "request_id": request_id,
        "upheld": upheld,
        "decision": verdict["decision"],
        "appeal_count": contract["appeal_count"],
        "override_open": override_open,
        "message": ("你已连续 3 次申诉被驳，现开放一次人工复核——"
                    "请作为配置者亲自裁决（override，须确认目标延后时长）"
                    if override_open else
                    ("维持驳回（§4.4 重审不达标）" if upheld
                     else "重审改判，按新判定执行")),
    }


def override(
    data_dir: Path,
    *,
    request_id: str,
    confirm: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    """人工覆写兜底（§5.2）：满 3 次申诉后一次性放行当次支取。

    必须 confirm=True（确认知悉目标延后时长）；消耗申诉计数归零；
    仅作用于当次支取，不改任何契约配置结构。
    """
    from modules.judge import _objective_impacts  # 复用延后测算

    today = today or date.today()
    contract = contract_io.read_contract(data_dir)
    entry = _find_request(contract, request_id)
    if entry is None:
        return {"ok": False, "error": "request_not_found",
                "message": f"未找到申请 {request_id}"}
    count = int(contract.get("appeal_count", 0))
    if count < APPEAL_OVERRIDE_THRESHOLD or _last_appeal_request(data_dir) != request_id:
        return {"ok": False, "error": "override_not_open",
                "message": f"人工覆写未开放：需同一申请连续 {APPEAL_OVERRIDE_THRESHOLD} "
                           f"次申诉被驳（当前 {count} 次，锚定申请须一致）"}

    # 目标延后时长测算（F5/F7 口径，覆写前必须知悉）
    amount = float(entry["amount"])
    dr = contract.get("distribution_rules", {})
    cp = dr.get("calc_params", {})
    f0 = F.f0_net_position(contract.get("corpus", 0), contract.get("liabilities"),
                           contract.get("rigid_annual_expenses"),
                           contract.get("monthly_contribution", 0))
    invest_nominal = F.f3_monthly_invest_nominal(
        f0["monthly_net"], dr.get("invest_ratio", 0.5))
    invest_real = F.f3_5_monthly_invest_real(
        invest_nominal, inflation=cp.get("inflation", 0.025),
        drawdown_factor=cp.get("drawdown_factor", 0.10),
        r_gross=cp.get("r_gross", 0.05))
    impacted, _, _ = _objective_impacts(
        contract, amount, False, invest_nominal, invest_real,
        cp.get("inflation", 0.025), today)
    delay_simple = F.f5_impact_simple(amount, invest_nominal)
    target_impact = {
        "delay_months_simple": delay_simple,
        "impacted_objectives": impacted,
        "note": "简化口径误差 ±20%~50%，真实口径见 impacted_objectives（F7）",
    }

    if not confirm:
        return {"ok": False, "error": "need_confirm",
                "message": "人工覆写须确认知悉本次消费的目标延后时长"
                           "（confirm=True）",
                "target_impact": target_impact}

    contract["appeal_count"] = 0   # 消耗申诉计数（防兜底常态化）
    contract_io.write_contract(data_dir, contract, actor="engine")
    audit_io.append(data_dir, "override_log", {
        "time": _now(), "event": "manual_override",
        "request_id": request_id, "amount": amount,
        "category": entry.get("category"),
        "target_impact": target_impact,
        "confirm": "已确认知悉目标延后影响",
    })
    return {"ok": True, "request_id": request_id, "amount": amount,
            "target_impact": target_impact, "appeal_count": 0,
            "message": "人工覆写放行（仅当次支取）；申诉计数已消耗归零，"
                       "需重新积累 3 次方可再次开启兜底通道"}


# ================================================================ §7.1.1 重置
def reset_contract(
    data_dir: Path,
    *,
    confirm: bool = False,
    corpus: float | None = None,
    monthly_contribution: float | None = None,
    objectives: list[dict[str, Any]] | None = None,
    reason: str = "",
    today: date | None = None,
) -> dict[str, Any]:
    """记账重置（§7.1.1）：唯一整文件重建入口。

    - confirm=False → 返回 need_confirm（二次确认闸门，同 §5.4 同源）；
    - 仅重写 contract.json；audit/ 全部日志原样保留（§10.1）；
    - override_log 记 event=contract_reset（含旧契约 sha256 摘要）。
    """
    from modules.initialize import lazy_init  # 复用 §7.1 懒人模板

    today = today or date.today()
    path = contract_io.contract_path(data_dir)
    if not path.is_file():
        return {"ok": False, "error": "not_found",
                "message": "契约不存在，无需重置；请直接 init"}
    if not confirm:
        return {"ok": False, "error": "need_confirm",
                "message": "将丢弃当前契约并重建，audit 历史保留。"
                           "确认请再说一次『确认重置』（confirm=True）"}
    if corpus is None or monthly_contribution is None or not objectives:
        return {"ok": False, "error": "missing_params",
                "message": "重置须提供新契约 3 项：corpus / monthly / objectives"}

    old_bytes = path.read_bytes()
    old_hash = hashlib.sha256(old_bytes).hexdigest()

    # 重建留痕先落审计（先记后删，链条不断）
    audit_io.append(data_dir, "override_log", {
        "time": _now(), "event": "contract_reset",
        "old_contract_sha256": old_hash,
        "reason": reason or "用户显式重置（§7.1.1）",
        "note": "audit 目录全部保留；旧 objective 引用在报表标注（已重置前）",
    })
    path.unlink()   # 仅删契约文件；audit/ 不动（§10.1 仅追加不可删）
    result = lazy_init(data_dir, corpus=corpus,
                       monthly_contribution=monthly_contribution,
                       objectives=objectives, today=today)
    if not result.get("ok"):
        return {"ok": False, "error": "reinit_failed",
                "message": "重置后重建失败（旧契约已删，audit 保留）",
                "detail": result}
    result["reset"] = True
    result["old_contract_sha256"] = old_hash
    return result


# ================================================================ §3.2 对账
def reconcile(
    data_dir: Path,
    *,
    corpus: float | None = None,
    income: float | None = None,
    invest: float | None = None,
    living: float | None = None,
    impulse: float | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """hybrid 对账（§3.2）：用户拍板修正 corpus / 补录当月实绩，更新 last_reconcile。

    - corpus 修正为配置区写（configurator，非核心护栏字段，普通确认即可）；
    - 当月实绩（income/invest/living/impulse）追加 monthly_history 快照
      （同月多条按最后一条为准，§6.2 收入监测口径）；
    - 对账差额不进入审批判定历史，仅同步真实基数（F0 回到真实现金流）。
    """
    today = today or date.today()
    contract = contract_io.read_contract(data_dir)
    changes: dict[str, Any] = {}

    if corpus is not None:
        changes["corpus"] = {"from": contract.get("corpus"), "to": float(corpus)}
        contract["corpus"] = float(corpus)

    contract.setdefault("reconcile", {})
    contract["reconcile"]["last_reconcile"] = today.isoformat()
    contract["reconcile"]["reminder_streak"] = 0
    # corpus 属配置区 → 用户拍板对账即配置者动作（引擎不自动改写，§3.2 护栏）
    contract_io.write_contract(data_dir, contract, actor="configurator")

    snapshot = None
    if any(v is not None for v in (income, invest, living, impulse)):
        f0 = F.f0_net_position(contract.get("corpus", 0), contract.get("liabilities"),
                               contract.get("rigid_annual_expenses"),
                               contract.get("monthly_contribution", 0))
        snapshot = {
            "time": _now(), "month": today.strftime("%Y-%m"),
            "income": income, "invest": invest,
            "living": living, "impulse": impulse,
            "corpus": contract.get("corpus"),
            "cushion_left": None,
            "source": "reconcile",
        }
        audit_io.append(data_dir, "monthly_history", snapshot)

    return {"ok": True, "changes": changes,
            "last_reconcile": today.isoformat(),
            "snapshot_appended": snapshot,
            "note": "对账为用户拍板确认；差额不进入审批判定历史（§3.2）"}
