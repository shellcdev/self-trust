"""renderer — 确定性文本渲染器（替代 LLM 手工排版）

把 CLI 输出的结构化 JSON 渲染成带 §0.5 骨架的人可见格式化回执。
所有命令统一骨架：
    {prefix}{命令标签}·{结果词} 🕐[YYYY-MM-DD HH:MM GMT+8]
    ============================================
    {命令专属正文，逐行}
    ============================================
    {上下文行：按需}

本文件不依赖任何外部库，纯标准库。"""
# ================================================================
# pylint: disable=too-many-branches,too-many-return-statements

import datetime
from typing import Any

SEP: str = "=" * 44
"""分隔线：44 个等号"""


# ── 工具函数 ────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    """§0.1 金额格式：¥ + 千分位 + 2 位小数"""
    return f"¥{v:,.2f}"


def _now_ts(today: datetime.date | None = None) -> str:
    """生成时间戳 🕐[YYYY-MM-DD HH:MM GMT+8]"""
    base = today or datetime.date.today()
    now = datetime.datetime.now().time()
    dt = datetime.datetime.combine(base, now)
    return dt.strftime("🕐[%Y-%m-%d %H:%M GMT+8]")


def _ts_from(r: dict) -> str:
    """从结果 dict 中提取日期生成时间戳"""
    d = r.get("date")
    if d:
        try:
            return _now_ts(datetime.date.fromisoformat(str(d)[:10]))
        except (ValueError, TypeError):
            pass
    return _now_ts()


# ── 头部生成 ────────────────────────────────────────────────────

_HDR = "{prefix}{label}{ts}"


def _header(prefix: str, label: str, ts: str) -> str:
    return f"{prefix}{label}{ts}"


# ── §1 / §11 审批（judge submit）─────────────────────────────────

def _render_judge_submit(r: dict, ts: str) -> str:
    dec = r.get("decision", {})
    inp = r.get("inputs", {})
    imp = r.get("impacted_objectives", [])
    cd = r.get("cooldown", {})
    scene = dec.get("scene", "?")
    result_word = dec.get("result", "?")

    amount = inp.get("amount", 0)
    category = inp.get("category", "")
    cushion = inp.get("effective_cushion", 0)
    corpus = inp.get("corpus", 0)
    remaining = inp.get("remaining_after", 0)
    cooldown_t = cd.get("triggered", False)
    days = cd.get("days", 3)
    request_id = r.get("request_id", "")
    expire_at = r.get("expire_at", "")
    obj_name = imp[0].get("name") if imp else None
    delay_simple = r.get("impact", {}).get("delay_months_simple", 0)
    summary = dec.get("summary", "")

    # 前缀映射
    prefix_map = {"A": "✅", "B": "📋", "C": "📋"}
    prefix = prefix_map.get(scene, "📋")

    if not cooldown_t and scene == "A":
        # A-1 / A-3 紧凑卡片（§11.1）
        lines = [
            _header(prefix, "审批·批准", ts),
            SEP,
        ]
        # 消费行
        lines.append(f"{_fmt(amount)} {category}")
        # 判定行
        if obj_name:
            lines.append(f"安全垫 {_fmt(cushion)} 之上 · {obj_name} 不受损")
        else:
            lines.append(f"安全垫 {_fmt(cushion)} 之上 · 目标不受损")
        # 账本行
        lines.append(f"账本 {_fmt(corpus)} → {_fmt(remaining)}")
        lines.append(SEP)
        return "\n".join(lines)

    # A-2（有冷却）/ B / C → 长模板（§1.4）
    lines = [_header(prefix, f"审批·{result_word}", ts), SEP]

    if scene == "B":
        lines.append(f"契约对照：{summary}")
    elif scene == "C":
        lines.append(f"契约对照：{summary}")
        lines.append(f"目标影响：{obj_name or '目标'} 延后约 {_fmt_months(delay_simple)}（简化口径，误差 ±20%~50%）")
        lines.append(f"替代方案：{summary}")
    else:
        # A-2
        lines.append(f"契约对照：{summary}")

    if obj_name and scene != "C":
        lines.append(f"目标影响：{obj_name} 延后约 {_fmt_months(delay_simple)}（简化口径，误差 ±20%~50%）")

    if cooldown_t:
        lines.append(f"冷静期 {days} 天，到期 {expire_at}（编号 {request_id}）")

    lines.append(SEP)
    return "\n".join(lines)


# ── §2 冷静期生命周期 ───────────────────────────────────────────

def _render_judge_withdraw(r: dict, ts: str) -> str:
    fb = r.get("feedback", {})
    amount = fb.get("withdrawn_amount", 0)
    category = r.get("", "")
    rid = r.get("request_id", "")
    obj = fb.get("objective") or "你的长期目标"
    ahead_simple = fb.get("ahead_months_simple", 0)
    ahead_real = fb.get("ahead_months_real")
    note = fb.get("estimation_note", "")

    # 试着从上下文中找 category
    lines = [
        _header("✅", "撤回·已撤回", ts),
        SEP,
        f"申请 {rid}（¥{amount:,.2f}）已撤回",
        f"即时回馈：相当于 {obj} 目标提前约 {_fmt_months(ahead_simple)}",
        "· 估算非承诺：基于简化口径，误差 ±20%~50%",
        f"· {note}",
        "· 钱留在账上，冷静期自动解除",
        SEP,
    ]
    if ahead_real is not None:
        lines.insert(-1, f"· 真实口径约 {_fmt_months(ahead_real)}（含通胀/回撤）")
    return "\n".join(lines)


def _render_judge_finalize(r: dict, ts: str) -> str:
    rid = r.get("request_id", "")
    dec = r.get("decision", {})
    result_word = dec.get("result", "执行")
    summary = dec.get("summary", "")
    lines = [
        _header("✅", "终裁确认·已执行", ts),
        SEP,
        f"申请 {rid} 按「{result_word}」终裁执行",
        summary,
        SEP,
    ]
    return "\n".join(lines)


def _render_judge_expire(r: dict, ts: str) -> str:
    processed = r.get("processed", [])
    lines = [_header("⏰", "到期终裁·已处理", ts), SEP]
    if not processed:
        lines.append("✅ 无到期申请待终裁")
    else:
        for p in processed:
            amt = p.get("amount", 0)
            cat = p.get("category", "")
            final = p.get("final_status", "")
            d = p.get("decision", {})
            dr = d.get("result", "")
            lines.append(f"· {cat} {_fmt(amt)} → {final}（{dr}）")
    lines.append(SEP)
    return "\n".join(lines)


def _render_judge_reminders(r: dict, ts: str) -> str:
    reminders = r.get("reminders", [])
    lines = [_header("⏰", "冷静期提醒·查询", ts), SEP]
    if not reminders:
        lines.append("✅ 无冷静期挂起申请")
    else:
        for rm in reminders:
            kind = rm.get("kind", "cooling")
            cat = rm.get("category", "")
            amt = rm.get("amount", 0)
            days_left = rm.get("days_left", 0)
            expire_at = rm.get("expire_at", "")
            rid = rm.get("request_id", "")
            icon = "⚠️" if kind == "expiring" else "⏳"
            tag = "即将到期" if kind == "expiring" else "冷静中"
            lines.append(f"· {icon} {tag}：{cat} {_fmt(amt)}")
            lines.append(f"  剩余 {days_left} 天（到期 {expire_at}）编号 {rid}")
    lines.append(SEP)
    return "\n".join(lines)


# ── §3 初始化 ────────────────────────────────────────────────────

def _render_init(r: dict, ts: str) -> str:
    corpus = r.get("corpus", 0)
    monthly = r.get("monthly_contribution", 0)
    objs = r.get("objectives", [])
    warnings = r.get("warnings", [])
    currency = r.get("currency", "CNY")
    sym = CURRENCY_SYMBOLS.get(currency, currency)

    lines = [_header("✅", "记账初始化·已生成", ts), SEP]
    obj_strs = []
    for o in objs:
        name = o.get("name", "")
        ta = o.get("target_amount", 0)
        dl = o.get("deadline", "")
        if ta and dl:
            obj_strs.append(f"{name}（{sym}{ta:,.2f}，{dl}）")
        elif ta:
            obj_strs.append(f"{name}（{sym}{ta:,.2f}）")
        else:
            obj_strs.append(name)
    lines.append(f"资金池 {sym}{corpus:,.2f}{'' if currency == 'CNY' else ' ' + currency}"
                 f"·月度净流入 {sym}{monthly:,.2f}{'' if currency == 'CNY' else ' ' + currency}")
    lines.append(f"目标：{'；'.join(obj_strs)}")
    for w in warnings:
        lines.append(f"⚠️ {w}")
    lines.append(SEP)
    lines.append("· 已生成默认契约，可随时说『自定义』逐项调")
    return "\n".join(lines)


# ── §4 演示 ──────────────────────────────────────────────────────

def _render_demo(r: dict, ts: str) -> str:
    lines = [
        _header("✅", "演示·已生成", ts),
        SEP,
        "⚠️ 演示数据，非您的真实契约",
    ]
    scenes = r.get("scenarios", [])
    for s in scenes:
        label = s.get("label", "")
        scene = s.get("scene", "")
        days = s.get("cooling_days", 0)
        if scene == "A":
            lines.append(f"· {label} → 批准（无冷静期）")
        elif scene == "B":
            lines.append(f"· {label} → 附条件（{days}天冷静期）")
        else:
            lines.append(f"· {label} → 驳回（冷却）")
    lines.append("这是演示，不影响真实账户；现在可以说『审查：买X花Y』开始真实审批")
    lines.append(SEP)
    return "\n".join(lines)


# ── §5 报表 ──────────────────────────────────────────────────────

def _render_report(r: dict, ts: str) -> str:
    corpus = r.get("corpus", 0)
    net = r.get("net_assets", 0)
    margin = r.get("cushion_margin", 0)
    alert = r.get("cushion_alert", False)
    monthly_net = r.get("monthly_net", 0)
    objs = r.get("objectives", [])
    pc = r.get("pending_cooling", [])
    notes = r.get("notes", [])

    lines = [_header("📊", "报表·已生成", ts), SEP]
    lines.append(f"· 资金池 {_fmt(corpus)}·净资产 {_fmt(net)}")
    lines.append(f"· 安全垫余量 {_fmt(margin)}")
    for o in objs:
        name = o.get("name", "")
        ar = o.get("achieved_ratio", 0)
        color = "✅" if ar >= 100 else ("🟡" if ar >= 50 else "🔴")
        tp = o.get("time_progress", 0)
        lines.append(f"· {name} 达成 {_fmt_pct(ar)}·{color}（时间轴应达 {_fmt_pct(tp)}）")
    lines.append(f"· 本月净流入 {_fmt(monthly_net)}，进度平稳")
    if alert:
        lines.append("· 安全垫预警：⚠️ 告警")
    else:
        lines.append("· 安全垫预警：余量充足，无预警")
    for p in pc:
        cat = p.get("category", "")
        amt = p.get("amount", 0)
        exp = p.get("expire_at", "")
        rid = p.get("request_id", "")
        lines.append(f"· 冷静期挂起（{len(pc)} 笔）：")
        lines.append(f"  · {cat} {_fmt(amt)} 待决")
        lines.append(f"    到期 {exp}（编号 {rid}）")
    for n in notes:
        lines.append(f"· {n}")
    lines.append(SEP)
    return "\n".join(lines)


# ── §6 校准 ──────────────────────────────────────────────────────

def _render_calibrate(r: dict, ts: str) -> str:
    skipped = r.get("skipped", False)
    changes = r.get("changes", [])
    ro = r.get("rebalance_override")
    lines = [_header("📊", "月度校准·已生效" if not skipped else "月度校准·已跳过", ts), SEP]
    if skipped:
        lines.append("✅ 本月已校准过（同月幂等），--force 可强制重跑")
    else:
        if not changes:
            lines.append("✅ 无需调整，目标进度正常")
        else:
            lines.append("以下调整已生效：")
            for c in changes:
                lines.append(f"· {c.get('description', '')}")
        if ro:
            lines.append("· 仅本月有效，原始权重不变")
    lines.append(SEP)
    return "\n".join(lines)


# ── §7 奖励 ──────────────────────────────────────────────────────

def _render_reward_status(r: dict, ts: str) -> str:
    objs = r.get("objectives", [])
    lines = [_header("🏆", "奖励状态·查询", ts), SEP]
    for o in objs:
        name = o.get("name", "")
        ar = o.get("achieved_ratio", 0)
        unlocked = o.get("reward_unlocked", False)
        quota = o.get("reward_quota", 0)
        un = "已解锁" if unlocked else "未解锁"
        lines.append(f"· {name}：达成率 {_fmt_pct(ar)} {un}")
        if quota > 0:
            lines.append(f"  可支取 {_fmt(quota)}")
        else:
            lines.append(f"  暂无可支取额度")
    lines.append(SEP)
    return "\n".join(lines)


def _render_reward_unlock(r: dict, ts: str) -> str:
    objs = r.get("objectives", [])
    lines = [_header("🏆", "奖励解锁·已解锁", ts), SEP]
    new_unlocked = False
    for o in objs:
        name = o.get("name", "")
        ar = o.get("achieved_ratio", 0)
        quota = o.get("reward_quota", 0)
        if ar >= 120:
            new_unlocked = True
            lines.append(f"· {name} 达成 {_fmt_pct(ar)}（≥120%）→ 解锁奖励额度 {_fmt(quota)}")
    if not new_unlocked:
        lines.append("✅ 暂无新解锁的奖励（达成率 ≥120% 时自动解锁）")
    lines.append(SEP)
    return "\n".join(lines)


def _render_reward_claim(r: dict, ts: str) -> str:
    obj = r.get("objective", "")
    amount = r.get("amount", 0)
    purpose = r.get("purpose", "")
    remaining = r.get("remaining_quota", 0)
    lines = [
        _header("✅", "奖励支取·已执行", ts),
        SEP,
        f"{obj} {_fmt(amount)}（{purpose}）",
        f"· 剩余额度 {_fmt(remaining)}",
        SEP,
    ]
    return "\n".join(lines)


# ── §8 日志 ──────────────────────────────────────────────────────

def _render_log(r: dict, ts: str) -> str:
    log_name = r.get("log", "?")
    count = r.get("count", 0)
    records = r.get("records", [])
    lines = [_header("📋", f"审计日志·{log_name}", ts), SEP]
    lines.append(f"共 {count} 条，展示最近 {min(10, count)} 条：")
    for rec in records[:10]:
        rt = rec.get("time", "")
        scene = rec.get("scene", rec.get("event", "?"))
        amount = rec.get("amount", 0)
        cat = rec.get("category", "")
        lines.append(f"· [{rt}] {scene} {_fmt(amount)} {cat}")
    lines.append(SEP)
    return "\n".join(lines)


# ── §9 申诉 / 覆写 ──────────────────────────────────────────────

def _render_appeal(r: dict, ts: str) -> str:
    upheld = r.get("upheld", True)
    dec = r.get("decision", {})
    summary = dec.get("summary", "")
    ac = r.get("appeal_count", 0)
    ov = r.get("override_open", False)
    result_word = "维持" if upheld else "改判"
    lines = [
        _header("📋", f"申诉·{result_word}", ts),
        SEP,
        summary,
        f"· 申诉计数 {ac}/3{' → 已开放人工覆写入口' if ov else ''}",
        SEP,
    ]
    return "\n".join(lines)


def _render_override_preview(r: dict, ts: str) -> str:
    ti = r.get("target_impact", {})
    ds = ti.get("delay_months_simple", 0)
    dr_ = ti.get("delay_months_real", 0)
    lines = [
        _header("⚠️", "人工覆写·预览", ts),
        SEP,
        f"· 目标影响：延后约 {_fmt_months(ds)}（简化口径，误差 ±20%~50%）",
        f"· 真实口径约 {_fmt_months(dr_)} 个月",
        "· 确认知悉后回复「确认覆写」执行",
        SEP,
    ]
    return "\n".join(lines)


def _render_override_confirm(r: dict, ts: str) -> str:
    rid = r.get("request_id", "")
    ti = r.get("target_impact", {})
    ds = ti.get("delay_months_simple", 0)
    lines = [
        _header("✅", "人工覆写·已执行", ts),
        SEP,
        f"申请 {rid} 放行",
        f"· 目标延后影响已记录（约 {_fmt_months(ds)} 个月）",
        "· 已落 override_log",
        SEP,
    ]
    return "\n".join(lines)


# ── §10 自定义 / 对账 / 重置 / 导入 ─────────────────────────────

def _render_customize_preview(r: dict, ts: str) -> str:
    changes = r.get("changes", [])
    token = r.get("token", "")
    cw = r.get("cooldown_window", False)
    cd = r.get("cooldown_days", 1)
    lines = [_header("📋", "修改预览·待确认", ts), SEP]
    for c in changes:
        field = c.get("field", "")
        fr = c.get("from", "")
        to = c.get("to", "")
        cons = c.get("consequence", "")
        lines.append(f"· {field}: {fr} → {to}")
        lines.append(f"  后果：{cons}")
    lines.append(f"· 确认令牌 {token}（回复「确认修改」+ 令牌生效）")
    if cw:
        lines.append(f"· ⚠️ 削弱型修改，确认后进入 {cd} 天冷静窗，窗内可无理由撤回")
    lines.append(SEP)
    return "\n".join(lines)


def _render_customize_confirm(r: dict, ts: str) -> str:
    cs = r.get("changes_summary", "")
    cw = r.get("cooldown_window", False)
    cd = r.get("cooldown_days", 1)
    rid = r.get("request_id", "")
    lines = [
        _header("✅", "修改生效·已生效", ts),
        SEP,
        cs,
    ]
    if cw:
        lines.append(f"· 进入 {cd} 天冷静窗（编号 {rid}），窗内可「记账自定义·撤回」")
    lines.append(SEP)
    return "\n".join(lines)


def _render_reconcile(r: dict, ts: str) -> str:
    changes = r.get("changes", {})
    psc = r.get("pending_spends_cleared", {})
    nrd = r.get("next_reconcile_date", "")
    lines = [_header("📊", "对账·已完成", ts), SEP]
    cc = changes.get("corpus")
    if cc:
        lines.append(f"· 资金池 {_fmt(cc['from'])} → {_fmt(cc['to'])}（差额 {_fmt(cc['diff'])}）")
    if psc:
        lines.append(f"· 清销已批支出 {psc.get('count', 0)} 笔（合计 {_fmt(psc.get('total', 0))}）")
    lines.append(f"· 下次对账提醒：{nrd}")
    lines.append(SEP)
    return "\n".join(lines)


def _render_reset_preview(r: dict, ts: str) -> str:
    sha = r.get("old_contract_sha256", "")
    lines = [
        _header("⚠️", "重置警告·待确认", ts),
        SEP,
        "· 将重建整个契约（审计日志保留）",
        f"· 旧契约 sha256: {sha}",
        "· 确认后须提供新契约参数（资金池/月度流入/目标）",
        SEP,
    ]
    return "\n".join(lines)


def _render_reset_confirm(r: dict, ts: str) -> str:
    sha = r.get("old_contract_sha256", "")
    # 嵌套的 init 结果
    init_rendered = r.get("_init_rendered", "")
    lines = [
        _header("✅", "重置·已生效", ts),
        SEP,
        f"· 旧契约 sha256: {sha}（已归档）",
        "· 新契约回执：",
        SEP,
    ]
    if init_rendered:
        lines.append(init_rendered)
    return "\n".join(lines)


def _render_import_pending(r: dict, ts: str) -> str:
    summary = r.get("summary", {})
    susp = r.get("suspicious", [])
    token = r.get("token", "")
    total = summary.get("total_assets", 0)
    lc = summary.get("liabilities_count", 0)
    rc = summary.get("rigid_count", 0)
    lines = [
        _header("📋", "资产导入·待核对", ts),
        SEP,
        f"· 总资产 {_fmt(total)}",
        f"· 负债 {lc} 项 / 刚性支出 {rc} 项",
    ]
    if susp:
        lines.append(f"· ⚠️ 可疑流水 {len(susp)} 条，请核对")
    else:
        lines.append("· 无可疑流水")
    lines.append(f"· 确认令牌 {token}")
    lines.append("· 核对后回复「确认导入」+ 令牌生效；或「取消导入」放弃")
    lines.append("· ⚠️ 导入待核对状态将锁定全部审批")
    lines.append(SEP)
    return "\n".join(lines)


def _render_import_confirm(r: dict, ts: str) -> str:
    applied = r.get("applied", {})
    lines = [
        _header("✅", "资产导入·已生效", ts),
        SEP,
        applied.get("summary", ""),
        "· 审批已解锁",
        SEP,
    ]
    return "\n".join(lines)


def _render_import_cancel(r: dict, ts: str) -> str:
    return (
        f"✅资产导入·已取消{_now_ts()}\n"
        f"{SEP}\n"
        "资产状态已还原\n"
        f"{SEP}\n"
    )


def _render_objective(r: dict, ts: str) -> str:
    name = r.get("name", "")
    ar = r.get("achieved_ratio", 0)
    to = r.get("to", "archived")
    lines = [
        _header("✅", f"目标·已{'归档' if to == 'archived' else '完结'}", ts),
        SEP,
        f"· {name} 已达成 {_fmt_pct(ar)}，归档至历史目标",
        "· 后续资金可重新分配",
        SEP,
    ]
    return "\n".join(lines)


# ── 错误渲染 ────────────────────────────────────────────────────

def _render_error(r: dict, ts: str) -> str:
    err = r.get("error", "unknown")
    msg = r.get("message", "")

    guide_map: dict[str, str] = {
        "not_found": "未找到契约数据，请先初始化（记账初始化）",
        "guard": msg,
        "invalid": f"参数有误：{msg}",
        "import_pending": "资产待核对，禁止审批；请先完成人工核对确认",
        "exists": "契约已存在，不可重复初始化；如需重建请走『记账重置』",
        "invalid_transition": msg,
        "request_not_found": "未找到该申请，可能已终裁或撤回",
        "not_due": f"该申请尚未到期，请到期后再终裁（{msg}）",
        "already_expired": "该申请已过期，请走到期终裁",
        "missing_rate": msg,
        "override_not_open": "尚未达到人工覆写条件（须连续 3 次申诉被驳）",
        "cushion_violation": "奖励支取击穿安全垫，规则引擎拒付",
        "invalid_amount": "申请金额必须为正数",
    }
    hint = guide_map.get(err, msg)
    lines = [
        _header("⚠️", "错误", ts),
        SEP,
        hint,
        SEP,
    ]
    return "\n".join(lines)


# ── 主入口 ──────────────────────────────────────────────────────

CURRENCY_SYMBOLS: dict[str, str] = {
    "CNY": "¥", "USD": "$", "EUR": "€", "GBP": "£",
    "HKD": "HK$", "JPY": "¥", "SGD": "S$", "AUD": "A$", "CAD": "C$",
}


def _fmt_pct(v: float) -> str:
    """百分比，保留 1 位小数"""
    return f"{v:.1f}%"


def _fmt_months(v: float) -> str:
    """月数，保留 1 位小数，0.1 兜底"""
    v = float(v)
    if abs(v) < 0.1:
        return "0.1 个月"
    return f"{v:.1f} 个月"


def render(result: dict, command: str, subcommand: str | None = None) -> str:
    """渲染引擎主入口。

    Args:
        result: CLI 模块输出的结构化 JSON（含 ok/error 等元字段）。
        command: 命令名（judge / init / report / demo / calibrate / reward /
                  log / appeal / customize / reconcile / reset / import-asset /
                  objective）。
        subcommand: 子命令识别（如 reward 的 status/unlock/claim，
                    customize 的 preview/confirm，appeal 的 override 等）。

    Returns:
        格式化文本，含 §0.5 全局骨架（分隔线 + 时间戳）。
        失败时返回 JSON 的 message。
    """
    ts = _ts_from(result)

    if not result.get("ok", True):
        return _render_error(result, ts)

    # judge 按 action 分派
    if command == "judge":
        action = subcommand or "submit"
        if action == "submit":
            return _render_judge_submit(result, ts)
        if action == "withdraw":
            return _render_judge_withdraw(result, ts)
        if action == "finalize":
            return _render_judge_finalize(result, ts)
        if action == "expire":
            return _render_judge_expire(result, ts)
        if action == "reminders":
            return _render_judge_reminders(result, ts)
        return _render_error({"ok": False, "error": "invalid",
                              "message": f"未知 judge action: {action}"}, ts)

    if command == "init":
        return _render_init(result, ts)
    if command == "demo":
        return _render_demo(result, ts)
    if command == "report":
        return _render_report(result, ts)
    if command == "calibrate":
        return _render_calibrate(result, ts)
    if command == "reconcile":
        return _render_reconcile(result, ts)

    if command == "reward":
        act = subcommand or "status"
        if act == "status":
            return _render_reward_status(result, ts)
        if act == "unlock":
            return _render_reward_unlock(result, ts)
        if act == "claim":
            return _render_reward_claim(result, ts)
        return _render_error(result, ts)

    if command == "log":
        return _render_log(result, ts)

    if command == "appeal":
        ov = subcommand == "override"
        confirm = subcommand == "override_confirm"
        if confirm:
            return _render_override_confirm(result, ts)
        if ov:
            return _render_override_preview(result, ts)
        return _render_appeal(result, ts)

    if command == "customize":
        if subcommand == "confirm":
            return _render_customize_confirm(result, ts)
        return _render_customize_preview(result, ts)

    if command == "reset":
        if subcommand == "confirm":
            return _render_reset_confirm(result, ts)
        return _render_reset_preview(result, ts)

    if command == "import-asset":
        status = subcommand or "pending"
        if status == "pending":
            return _render_import_pending(result, ts)
        if status == "confirm":
            return _render_import_confirm(result, ts)
        if status == "cancel":
            return _render_import_cancel(result, ts)
        return _render_error(result, ts)

    if command == "objective":
        return _render_objective(result, ts)

    return _render_error({"ok": False, "error": "invalid",
                          "message": f"未知命令: {command}"}, ts)


if __name__ == "__main__":  # pragma: no cover — 快速预览用
    import sys
    import json
    raw = sys.stdin.read()
    data = json.loads(raw)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "?"
    sub = sys.argv[2] if len(sys.argv) > 2 else None
    print(render(data, cmd, sub))
