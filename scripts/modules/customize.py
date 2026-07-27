# -*- coding: utf-8 -*-
"""记账自定义（§5.4 / §7.1 / §9）：逐项增量覆盖修改契约配置区参数。

确定性规则（公正性靠代码不靠 AI）：
- 增量覆盖：只改用户指定的字段，不破坏未填值（deep-merge）；
- §5.4 核心护栏字段（safety_cushion / objectives / fast_track_whitelist /
  optimization_goal / distribution_rules）修改 → 二次确认 + 风险提示 + 落 override_log；
- 非核心字段（monthly_contribution / mode / corpus 等）走普通确认（同一「预览→确认」两步）；
- 单次预览不落盘（needs_confirm）；确认须带预览返回的 token（防漂移 / 手滑）；
- 落盘经 core.contract.write_contract(actor="configurator", confirm=True)，
  三区权限 + §5.4 闸门由底层强制，未知字段 / 审计字段显式 GuardError；
- 变更落 override_log（§5.4 步骤4），与 §10.1 审计一致、仅追加可复盘。

LLM 铁律：禁止心算，风险提示中的数字必须原样引用本模块从契约算出的结果。
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from core import audit as audit_io
from core import contract as contract_io
from core.contract import _validate_zones
from core.models import CORE_GUARD_FIELDS, living_baseline_value


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_scalar(s: str) -> Any:
    """--set 的值类型解析：null/bool/float/str（按此顺序）。"""
    low = s.strip().lower()
    if low in ("null", "none", ""):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return float(s)
    except ValueError:
        return s


def _set_dotpath(d: dict[str, Any], path: str, value: Any) -> None:
    """在嵌套 dict 上按 dotpath 设置值（就地修改 d）。"""
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _parse_objective(spec: str) -> dict[str, Any]:
    """解析 --add-objective "名称:目标额:期限"，补齐 Objective schema 默认。"""
    parts = spec.split(":")
    obj: dict[str, Any] = {
        "name": parts[0], "weight": 1.0, "current_amount": 0.0,
        "start_date": None, "deadline": None, "target_amount": None,
        "lag_streak": 0, "reward_unlocked": False, "reward_quota": 0.0,
        "status": "active",
    }
    if len(parts) > 1 and parts[1]:
        obj["target_amount"] = float(parts[1])
    if len(parts) > 2 and parts[2]:
        obj["deadline"] = parts[2]
    return obj


def _top_field(path: str) -> str:
    """dotpath 的顶层字段名（用于 §5.4 护栏归属判定）。"""
    return path.split(".", 1)[0]


def _risk_warnings(contract: dict[str, Any], changed: dict[str, Any]) -> list[str]:
    """§5.4 步骤1 + 485：核心护栏字段修改须用具体数字与后果提示（不空泛）。"""
    warns: list[str] = []
    lb = living_baseline_value(contract)
    m = float(contract.get("monthly_contribution", 0) or 0)

    if "safety_cushion" in changed:
        old, new = (changed["safety_cushion"]["from"],
                    changed["safety_cushion"]["to"])
        om, nm = old.get("months"), new.get("months")
        if om is not None and nm is not None and nm < om:
            warns.append(
                f"安全垫月数由 {om} 降至 {nm}；按当前生活费基线 {lb}，"
                f"现金缓冲由 {om * lb} 降至 {nm * lb}（抗风险能力↓）")
        if old.get("mode") != new.get("mode"):
            warns.append(
                f"安全垫模式由 {old.get('mode')} 改为 {new.get('mode')}（缓冲口径变化）")

    if "distribution_rules" in changed:
        od = changed["distribution_rules"]["from"].get("invest_ratio")
        nd = changed["distribution_rules"]["to"].get("invest_ratio")
        if od is not None and nd is not None:
            if nd == 0:
                warns.append("invest_ratio 归零，FIRE 将实质性停滞（每月增值投入归零）")
            elif nd < od:
                warns.append(
                    f"投资比例由 {od} 降至 {nd}；按月净流入 {m}，"
                    f"每月增值投入由 {od * m} 降至 {nd * m}（目标推进减速）")
            elif nd > od:
                warns.append(
                    f"投资比例由 {od} 升至 {nd}；按月净流入 {m}，"
                    f"每月增值投入由 {od * m} 升至 {nd * m}（短期可支配收入减少）")

    if "optimization_goal" in changed:
        new = changed["optimization_goal"]["to"]
        if new == "wealth":
            warns.append("切换至 wealth（激进增值）：生活费基线压缩、短期可支配收入减少、目标推进加速")
        elif new == "objective":
            warns.append("切换至 objective（目标优先）：非目标支出更受限")
        elif new == "balanced":
            warns.append("切回 balanced（均衡）：恢复默认调度")

    if "objectives" in changed:
        olds = {o.get("name") for o in changed["objectives"]["from"]}
        news = changed["objectives"]["to"]
        new_names = {n.get("name") for n in news}
        for o in news:
            if o.get("name") not in olds:
                warns.append(
                    f"新增目标 {o.get('name')}（目标额 {o.get('target_amount')}，"
                    f"期限 {o.get('deadline')}）")
        for o in changed["objectives"]["from"]:
            if o.get("name") not in new_names:
                warns.append(f"移除目标 {o.get('name')}（已删目标不再追踪）")

    if "fast_track_whitelist" in changed:
        olds = {w.get("name") for w in changed["fast_track_whitelist"]["from"]}
        news = changed["fast_track_whitelist"]["to"]
        new_names = {w.get("name") for w in news}
        for n in news:
            if n.get("name") not in olds:
                warns.append(
                    f"新增极速审批类目 {n.get('name')}（单笔上限 {n.get('per_tx_cap')}，"
                    f"年上限 {n.get('annual_cap')}）：免冷静期不豁免安全垫")
        for name in olds - new_names:
            warns.append(f"移除极速审批类目 {name}（该类目恢复走正常冷静期）")
    return warns


def _apply_changes(contract: dict[str, Any], changes: dict[str, Any]):
    """将 changes 规范应用到契约深拷贝，返回 (new_contract, touched_top_fields)。"""
    new = copy.deepcopy(contract)
    touched: set[str] = set()

    for op in changes.get("set", []):
        _set_dotpath(new, op["path"], op["value"])
        touched.add(_top_field(op["path"]))

    for spec in changes.get("add_objective", []):
        obj = _parse_objective(spec)
        new.setdefault("objectives", []).append(obj)
        touched.add("objectives")

    for w in changes.get("whitelist_add", []):
        new.setdefault("fast_track_whitelist", []).append({
            "name": w["name"], "per_tx_cap": w["per_tx_cap"],
            "annual_cap": w["annual_cap"], "used_annual": 0})
        touched.add("fast_track_whitelist")

    for name in changes.get("whitelist_remove", []):
        wl = new.get("fast_track_whitelist", [])
        if not any(w.get("name") == name for w in wl):
            raise ValueError(f"白名单中不存在类目: {name}")
        new["fast_track_whitelist"] = [w for w in wl if w.get("name") != name]
        touched.add("fast_track_whitelist")

    return new, touched


def _diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """顶层字段 before/after 差异（深层比较）。"""
    changed: dict[str, Any] = {}
    for k in set(old) | set(new):
        if old.get(k) != new.get(k):
            changed[k] = {"from": old.get(k), "to": new.get(k)}
    return changed


def _contract_sha(contract: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _token(changes: dict[str, Any], contract_sha: str) -> str:
    """确认 token：变更规范 + 当前契约摘要，防确认漂移 / 手滑（§5.4 单次确认不生效）。"""
    canon = json.dumps(changes, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256((canon + "|" + contract_sha).encode("utf-8")).hexdigest()[:16]


def build_changes(args) -> dict[str, Any]:
    """从 CLI args 解析出 changes 规范（结构化变更列表）。"""
    changes: dict[str, Any] = {
        "set": [], "add_objective": [],
        "whitelist_add": [], "whitelist_remove": [],
    }
    for item in (args.set or []):
        if "=" not in item:
            raise ValueError(f"--set 格式应为 DOTPATH=VALUE，得到: {item}")
        path, _, raw = item.partition("=")
        changes["set"].append({"path": path.strip(), "value": _parse_scalar(raw)})
    for spec in (args.add_objective or []):
        changes["add_objective"].append(spec)
    if getattr(args, "whitelist_add", None):
        ptc = args.per_tx_cap
        anc = args.annual_cap
        if ptc is None or anc is None:
            raise ValueError("--whitelist-add 须同时提供 --per-tx-cap 与 --annual-cap")
        changes["whitelist_add"].append(
            {"name": args.whitelist_add, "per_tx_cap": float(ptc),
             "annual_cap": float(anc)})
    if getattr(args, "whitelist_remove", None):
        changes["whitelist_remove"].append(args.whitelist_remove)
    if not any(changes.values()):
        raise ValueError(
            "未提供任何修改（--set / --add-objective / --whitelist-add / "
            "--whitelist-remove 至少一项）")
    return changes


def preview(data_dir: Path, changes: dict[str, Any]) -> dict[str, Any]:
    """预览修改（不落盘）：before/after + 护栏字段风险提示 + 二次确认 token。"""
    contract = contract_io.read_contract(data_dir)
    new, _ = _apply_changes(contract, changes)
    # 提前校验三区 / §5.4（preview 即暴露 GuardError，避免 confirm 才报错）
    _validate_zones(new, contract, "configurator", confirm=True)

    changed = _diff(contract, new)
    touched_guard = sorted(t for t in changed if t in CORE_GUARD_FIELDS)
    risks = _risk_warnings(contract, changed)
    tok = _token(changes, _contract_sha(contract))
    return {
        "ok": True, "needs_confirm": True, "preview": True,
        "changed_fields": changed,
        "touched_guard_fields": touched_guard,
        "risk_warnings": risks,
        "token": tok,
        "message": (
            "以下修改将在确认后落盘（§5.4 二次确认）。核心护栏字段已标注风险提示；"
            "回复确认修改（带本 token）即生效。")
        if touched_guard else
        ("以下非核心参数修改将在确认后落盘（普通确认）。"
         "回复确认修改（带本 token）即生效。"),
    }


def apply(data_dir: Path, changes: dict[str, Any], *, confirm: bool,
          token: str | None, reason: str) -> dict[str, Any]:
    """应用修改：confirm=False → 返回预览；confirm=True + 正确 token → 落盘 + 写 override_log。"""
    contract = contract_io.read_contract(data_dir)
    expected = _token(changes, _contract_sha(contract))
    if not confirm:
        return preview(data_dir, changes)
    if token != expected:
        return {
            "ok": False, "error": "stale_token",
            "message": "确认 token 不匹配或契约已变更，请重新预览（customize 不带 --confirm）再确认",
            "expected_token": expected,
        }

    new, _ = _apply_changes(contract, changes)
    changed = _diff(contract, new)
    touched_guard = sorted(t for t in changed if t in CORE_GUARD_FIELDS)
    risks = _risk_warnings(contract, changed)

    # 落盘：configurator + confirm=True 通过 §5.4 闸门；未知/审计字段由底层 GuardError
    contract_io.write_contract(data_dir, new, actor="configurator", confirm=True)
    audit_io.append(data_dir, "override_log", {
        "time": _now(), "event": "contract_customize",
        "changed_fields": changed,
        "touched_guard_fields": touched_guard,
        "risk_warnings": risks,
        "reason": reason or "用户显式自定义（§5.4）",
        "confirm": "已二次确认（token 校验通过）",
    })
    return {
        "ok": True, "applied": True,
        "changed_fields": changed,
        "touched_guard_fields": touched_guard,
        "risk_warnings": risks,
        "note": "配置区增量覆盖完成；审计区 override_log 已追加（§10.1 仅追加）",
    }
