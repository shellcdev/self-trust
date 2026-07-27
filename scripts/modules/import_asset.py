# -*- coding: utf-8 -*-
"""第三方资产导入（§7.3）：CSV / 手动录入 → 拉取候选 → 人工核对 → 确认生效。

状态机（§7.3 硬约束）：
- ``imported_pending``：导入已拉取但尚未人工核对确认；**禁止任何支取审批**
  （judge 入口前置拦截，见 modules/judge.py）。
- ``imported_confirmed``：用户修正确认后生效，资产池正式纳入资金池。

数据中立机制（§3 / §11.5）：
- 候选数据先暂存于 RUNTIME 区 ``pending_import``，**不立即写入 live corpus**；
  核对确认（confirm）后才落到配置区的 corpus / monthly_contribution /
  liabilities / rigid_annual_expenses；取消（cancel）仅清 staging 并还原
  corpus_status，live corpus 原值不受污染（避免未核实数据污染后续所有审批）。
- 两步确认 + token 防漂移（复用 §5.4 范式）。

CSV 格式（balances）：``name,balance,kind[,monthly]``
  kind ∈ {asset, liability, rigid}；asset 余额为正；liability 余额为正（债务额）、
  monthly=月供；rigid 余额为正（年支出额）、monthly 缺省=余额/12。
CSV 格式（flows，可选）：``date,amount``（date YYYY-MM-DD；amount 正负=收支；
  月均净流入 = Σ/月数）。
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from core import audit as audit_io
from core import contract as contract_io


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _token(staging: dict[str, Any], contract_sha: str) -> str:
    """确认 token：候选暂存规范 + 当前契约摘要，防确认漂移 / 手滑。"""
    canon = json.dumps(staging, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256((canon + "|" + contract_sha).encode("utf-8")).hexdigest()[:16]


def _contract_sha(contract: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def parse_balances_csv(path: Any) -> list[dict[str, Any]]:
    """解析余额 CSV（name,balance,kind[,monthly]）→ 规范行列表。"""
    p = Path(path)
    rows: list[dict[str, Any]] = []
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            name = (row.get("name") or "").strip()
            kind = (row.get("kind") or "").strip().lower()
            if not name or not kind:
                raise ValueError(f"balances CSV 第 {i} 行缺少 name 或 kind")
            if kind not in ("asset", "liability", "rigid"):
                raise ValueError(
                    f"balances CSV 第 {i} 行 kind 须为 asset/liability/rigid，得到 {kind!r}")
            try:
                balance = float(row.get("balance") or 0)
            except ValueError:
                raise ValueError(f"balances CSV 第 {i} 行 balance 非数字: {row.get('balance')!r}")
            monthly = (row.get("monthly") or "").strip()
            monthly_val = float(monthly) if monthly else 0.0
            rows.append({"name": name, "balance": balance,
                         "kind": kind, "monthly": monthly_val})
    if not rows:
        raise ValueError("balances CSV 为空（至少需要一行资产）")
    return rows


def parse_flows_csv(path: Any) -> list[tuple[str, float]]:
    """解析流水 CSV（date,amount）→ [(date_str, amount), ...]。"""
    p = Path(path)
    out: list[tuple[str, float]] = []
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            ds = (row.get("date") or "").strip()
            am = (row.get("amount") or "").strip()
            if not ds or not am:
                raise ValueError(f"flows CSV 第 {i} 行缺少 date 或 amount")
            try:
                amount = float(am)
            except ValueError:
                raise ValueError(f"flows CSV 第 {i} 行 amount 非数字: {am!r}")
            out.append((ds, amount))
    return out


def _dedup_balances(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按 (name, kind) 去重合并，防止同一账户在 CSV/手动录入中重复列出导致资产/负债双倍计入。

    - 完全重复行（name/balance/kind/monthly 全同）= 同账户重复导出 → 丢弃多余副本。
    - 同 name+kind 但余额/月供不同 = 歧义（可能漏列/错列）→ 求和并告警，不静默丢弃。
    """
    warnings: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}  # (name, kind) -> index in merged
    merged: list[dict[str, Any]] = []
    for r in rows:
        key = (r["name"], r["kind"])
        idx = seen.get(key)
        if idx is None:
            merged.append(dict(r))
            seen[key] = len(merged) - 1
            continue
        prev = merged[idx]
        if prev["balance"] == r["balance"] and prev["monthly"] == r["monthly"]:
            continue  # 完全重复 → 丢弃副本（修复 H1：不再双倍计入）
        # 同账户余额不同 → 求和（保守不丢钱）+ 告警，交由人工核对
        prev["balance"] = prev["balance"] + r["balance"]
        prev["monthly"] = prev["monthly"] + r["monthly"]
        warnings.append({
            "name": r["name"], "kind": r["kind"],
            "reason": (f"「{r['name']}」({r['kind']}) 出现多次且余额/月供不一致，"
                       "已按同账户求和合并，请核对是否为错账或重复导出"),
        })
    return merged, warnings


def compute_candidates(balances: list[dict[str, Any]],
                       flows: Optional[list[tuple[str, float]]] = None) -> dict[str, Any]:
    """由余额 / 流水行推导导入候选。

    返回：{ corpus, monthly_contribution, liabilities, rigid_annual_expenses,
            suspicious, summary }
    - corpus = Σ 资产余额（kind=asset）
    - liabilities = [{name, balance, monthly_payment, annual_rate}]
    - rigid_annual_expenses = [{name, amount, due_month}]
    - monthly_contribution = 流水月均净流入（无流水则 0）
    - suspicious = 流水异常月份（月净流入绝对值 > 3×中位数，提示用户核对）
    """
    corpus = 0.0
    liabilities: list[dict[str, Any]] = []
    rigid: list[dict[str, Any]] = []
    asset_rows = liability_rows = rigid_rows = 0
    # 修复 H1：先按 (name, kind) 去重合并，避免重复行导致资产/负债双倍计入
    balances, dedup_warnings = _dedup_balances(balances)
    for r in balances:
        if r["kind"] == "asset":
            asset_rows += 1
            corpus += float(r["balance"])
        elif r["kind"] == "liability":
            liability_rows += 1
            liabilities.append({
                "name": r["name"],
                "balance": abs(float(r["balance"])),
                "monthly_payment": float(r["monthly"]),
                "annual_rate": 0.0,
            })
        elif r["kind"] == "rigid":
            rigid_rows += 1
            rigid.append({
                "name": r["name"],
                "amount": float(r["balance"]),
                "due_month": None,
            })
    monthly = 0.0
    suspicious: list[dict[str, Any]] = []
    if flows:
        by_month: dict[str, float] = {}
        for ds, amt in flows:
            month = ds[:7]  # YYYY-MM
            by_month[month] = by_month.get(month, 0.0) + float(amt)
        nets = list(by_month.values())
        if nets:
            median = sorted(nets)[len(nets) // 2]
            monthly = sum(nets) / len(nets)
            for m, net in sorted(by_month.items()):
                if median and abs(net) > 3 * abs(median):
                    suspicious.append({
                        "month": m, "net": net,
                        "reason": (f"月净流入 {net} 偏离中位数 {median} 超 3 倍，"
                                   "请核对是否有重复记账 / 错账 / 币种错配"),
                    })
    # provided：来源（CSV/手动）实际提供了哪些分类。confirm 据此只覆盖显式项，
    # 缺类（如 CSV 只有资产、没有负债/刚性行）视为「未提供」→ 保留 live 原值（#1 修复）。
    provided = {
        "corpus": asset_rows > 0,
        "monthly_contribution": bool(flows),
        "liabilities": liability_rows > 0,
        "rigid_annual_expenses": rigid_rows > 0,
    }
    return {
        "corpus": corpus,
        "monthly_contribution": monthly,
        "liabilities": liabilities,
        "rigid_annual_expenses": rigid,
        "suspicious": suspicious,
        "warnings": dedup_warnings,
        "provided": provided,
        "summary": {
            "total_assets": corpus,
            "liabilities_count": len(liabilities),
            "rigid_count": len(rigid),
            "months_flow": len(flows) if flows else 0,
        },
    }


def stage_import(contract: dict[str, Any], candidates: dict[str, Any],
                 source: str, today: Optional[date] = None) -> dict[str, Any]:
    """§7.3 第一步：拉取候选并暂存，置 corpus_status=imported_pending（锁定审批）。

    live corpus 暂不写入（staging 在 RUNTIME 区 pending_import），核对确认才落盘。
    返回摘要 + 确认 token（confirm 须带；cancel 亦须带）。
    """
    prior_status = contract.get("corpus_status", "manual")
    staging = {
        "source": source,
        "candidates": candidates,
        "prior_status": prior_status,
        "staged_at": _now(),
    }
    tok = _token(staging, _contract_sha(contract))
    staging["token"] = tok
    contract["corpus_status"] = "imported_pending"
    contract["pending_import"] = staging
    return {
        "ok": True,
        "staged": True,
        "needs_confirm": True,
        "token": tok,
        "source": source,
        "summary": candidates["summary"],
        "suspicious": candidates["suspicious"],
        "warnings": candidates.get("warnings", []),
        "candidates": {
            "corpus": candidates["corpus"],
            "monthly_contribution": candidates["monthly_contribution"],
            "liabilities": candidates["liabilities"],
            "rigid_annual_expenses": candidates["rigid_annual_expenses"],
        },
        "message": (
            "已拉取第三方资产候选并暂存（corpus_status=imported_pending，审批已锁定）。"
            "请逐项核对摘要与可疑流水；确认请带本 token 执行 confirm，"
            "或带 token 执行 cancel 放弃本次导入。"),
    }


def _get_staging(contract: dict[str, Any], token: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    staging = contract.get("pending_import")
    if not staging or staging.get("token") != token:
        return None, "bad_token"
    return staging, None


def confirm_import(contract: dict[str, Any], token: str,
                   corrections: Optional[dict[str, Any]] = None,
                   today: Optional[date] = None) -> dict[str, Any]:
    """§7.3 第二步：核对确认，将候选（可被 corrections 修正）落到 live 配置区。

    corpus / monthly_contribution / liabilities / rigid_annual_expenses 写入；
    corpus_status → imported_confirmed；清空 pending_import。
    """
    staging, err = _get_staging(contract, token)
    if err:
        return {"ok": False, "error": err,
                "message": "导入 token 不匹配（须用 stage 返回的 token）"}
    cands = dict(staging["candidates"])
    # 来源显式提供了哪些分类（stage 时标记）；旧数据无 provided 则回退为「全部覆盖」。
    staged_provided = cands.get("provided", {
        "corpus": True, "monthly_contribution": True,
        "liabilities": True, "rigid_annual_expenses": True,
    })
    if corrections:
        cands.update({k: v for k, v in corrections.items() if v is not None})
    # 仅覆盖「来源提供」或「人工修正」的分类；其余 live 原值保留，
    # 避免 CSV 缺某类（如负债/刚性）时静默清空已录入资产（#1 修复）。
    provided = dict(staged_provided)
    if corrections:
        for k in corrections:
            provided[k] = True
    if provided.get("corpus"):
        contract["corpus"] = float(cands["corpus"])
    if provided.get("monthly_contribution"):
        contract["monthly_contribution"] = float(cands["monthly_contribution"])
    if provided.get("liabilities"):
        contract["liabilities"] = cands["liabilities"]
    if provided.get("rigid_annual_expenses"):
        contract["rigid_annual_expenses"] = cands["rigid_annual_expenses"]
    contract["corpus_status"] = "imported_confirmed"
    contract["pending_import"] = None
    return {
        "ok": True,
        "confirmed": True,
        "corpus_status": "imported_confirmed",
        "applied": {
            "corpus": contract["corpus"],
            "monthly_contribution": contract["monthly_contribution"],
            "liabilities": contract["liabilities"],
            "rigid_annual_expenses": contract["rigid_annual_expenses"],
        },
        "message": ("第三方资产已核对确认并生效（imported_confirmed），"
                    "资产池正式纳入资金池，可正常审批。"),
    }


def cancel_import(contract: dict[str, Any], token: str) -> dict[str, Any]:
    """放弃导入：还原 corpus_status（prior_status）并清空 pending_import；live corpus 不变。"""
    staging, err = _get_staging(contract, token)
    if err:
        return {"ok": False, "error": err,
                "message": "导入 token 不匹配（须用 stage 返回的 token）"}
    prior = staging.get("prior_status", "manual")
    contract["corpus_status"] = prior
    contract["pending_import"] = None
    return {
        "ok": True,
        "cancelled": True,
        "corpus_status_restored": prior,
        "message": f"已放弃本次导入，corpus_status 还原为 {prior}（live 资产未改动）。",
    }
