# -*- coding: utf-8 -*-
"""契约 schema dataclass + 三区权限枚举 + pending_requests 状态机（设计文档 §2 / §10.3 / §5.1）。

三区权限（§10.3，公正性地基）：
- CONFIG   配置区：引擎只读，仅配置者经 §5.4 闸门可改；
- RUNTIME  运行态区：计数器与临时层，引擎按既定规则可写；
- AUDIT    审计区：仅追加，落 <data-dir>/audit/*.jsonl，不入 contract.json。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

SCHEMA_VERSION = "0.1"


class Zone(str, Enum):
    CONFIG = "config"    # 配置区：引擎只读
    RUNTIME = "runtime"  # 运行态区：引擎可写
    AUDIT = "audit"      # 审计区：仅追加（物理分离，不在 contract.json）


# 契约顶层字段 → 权限区映射（§10.3；contract.write_contract 据此强制校验）
FIELD_ZONES: dict[str, Zone] = {
    # ---- 配置区（引擎只读）----
    "version": Zone.CONFIG,
    "corpus": Zone.CONFIG,             # 仅初始化/对账/经审批支取可动（走闸门）
    "corpus_status": Zone.CONFIG,
    "liabilities": Zone.CONFIG,
    "rigid_annual_expenses": Zone.CONFIG,
    "monthly_contribution": Zone.CONFIG,
    "safety_cushion": Zone.CONFIG,
    "objectives": Zone.CONFIG,
    "distribution_rules": Zone.CONFIG,
    "mode": Zone.CONFIG,
    "cooldown_days": Zone.CONFIG,
    "cooldown_threshold": Zone.CONFIG,
    "fast_track_whitelist": Zone.CONFIG,   # 结构改动走闸门；used_annual 子项属运行态
    "optimization_goal": Zone.CONFIG,
    # ---- 运行态区（引擎可写）----
    "reconcile": Zone.RUNTIME,
    "whitelist_cap_year": Zone.RUNTIME,
    "appeal_count": Zone.RUNTIME,
    "pending_requests": Zone.RUNTIME,
    "pending_config_changes": Zone.RUNTIME,   # §5.4 冷却窗：削弱自身修改的待生效队列
    "pending_import": Zone.RUNTIME,           # §7.3 第三方导入候选暂存（核对确认才落 live corpus）
    "rebalance_override": Zone.RUNTIME,
    "last_calibrate": Zone.RUNTIME,
    "last_report_date": Zone.RUNTIME,
    "report_streak": Zone.RUNTIME,
    "gap_streak": Zone.RUNTIME,
    # ---- 审计区（逻辑归属示意；物理落 audit/，不应写进 contract.json）----
    "approval_log": Zone.AUDIT,
    "appeal_log": Zone.AUDIT,
    "override_log": Zone.AUDIT,
    "reward_log": Zone.AUDIT,
    "monthly_history": Zone.AUDIT,
}

# §5.4 核心护栏字段（修改须二次确认 + 风险提示 + 冷静窗）
CORE_GUARD_FIELDS = frozenset({
    "safety_cushion",
    "objectives",
    "fast_track_whitelist",
    "optimization_goal",
    "distribution_rules",   # 含 invest_ratio / living_baseline / calc_params
})


class RequestStatus(str, Enum):
    """pending_requests 状态机（§5.1）：cooling → withdrawn | decided | expired"""
    COOLING = "cooling"
    WITHDRAWN = "withdrawn"
    DECIDED = "decided"
    EXPIRED = "expired"


# 合法状态迁移表；终态不可再迁移
_TRANSITIONS: dict[RequestStatus, frozenset[RequestStatus]] = {
    RequestStatus.COOLING: frozenset(
        {RequestStatus.WITHDRAWN, RequestStatus.DECIDED, RequestStatus.EXPIRED}
    ),
    RequestStatus.WITHDRAWN: frozenset(),
    RequestStatus.DECIDED: frozenset(),
    RequestStatus.EXPIRED: frozenset(),
}


def can_transition(src: RequestStatus, dst: RequestStatus) -> bool:
    """状态机守卫：仅 cooling 可迁出，终态封闭。"""
    return dst in _TRANSITIONS[RequestStatus(src)]


@dataclass
class PendingRequest:
    """冷静期待审申请（§5.1，跨会话持久不丢单）。"""
    request_id: str
    time: str                 # ISO 提交时间
    amount: float
    category: str
    planned: bool
    expire_at: str            # ISO 到期时间
    status: str = RequestStatus.COOLING.value

    def transition(self, dst: RequestStatus) -> None:
        if not can_transition(RequestStatus(self.status), dst):
            raise ValueError(f"非法状态迁移: {self.status} -> {dst.value}")
        self.status = dst.value


@dataclass
class Objective:
    """长期目标（§2 / §6.4 生命周期：active|completed|overdue|archived）。"""
    name: str
    weight: float = 1.0
    current_amount: float = 0.0
    start_date: Optional[str] = None
    deadline: Optional[str] = None
    target_amount: Optional[float] = None
    lag_streak: int = 0
    reward_unlocked: bool = False
    reward_quota: float = 0.0
    status: str = "active"    # 缺省视为 active（schema 向后兼容）


@dataclass
class SafetyCushion:
    mode: str = "months"      # months | fixed | ratio
    months: float = 6
    fixed: float = 100000
    ratio: float = 0.2


@dataclass
class Contract:
    """记账契约（§2 schema 草案；审计日志物理分离，不含 *_log 字段）。"""
    version: str = SCHEMA_VERSION
    corpus: float = 0.0
    corpus_status: str = "manual"   # manual | imported_pending | imported_confirmed
    liabilities: list[dict[str, Any]] = field(default_factory=list)
    rigid_annual_expenses: list[dict[str, Any]] = field(default_factory=list)
    monthly_contribution: float = 0.0
    safety_cushion: dict[str, Any] = field(
        default_factory=lambda: asdict(SafetyCushion()))
    objectives: list[dict[str, Any]] = field(default_factory=list)
    distribution_rules: dict[str, Any] = field(default_factory=lambda: {
        "living_baseline": {"mode": "auto", "manual": 0, "history3m_value": None},
        "invest_ratio": 0.5,
        "calc_params": {"inflation": 0.025, "drawdown_factor": 0.10, "r_gross": 0.05},
        # 标准类目词汇表（推荐清单，非硬约束；judge 当前不强制成员校验，见选项 B）。
        # 逻辑分组（仅作展示顺序，数据层为扁平列表）：
        #   生活必需：食品 居住 交通 通讯 医疗 教育
        #   日常开销：服饰 日用
        #   生活品质：合理享受（受保护「合理享受」额度）娱乐 旅行 社交 宠物
        #   大额与保障：数码家电 保险
        #   投资理财（资金去向标签，投资机制本身由 invest_ratio 管）：投资 理财 基金 股票 黄金
        #   兜底：其他
        "allowed_categories": [
            "食品", "居住", "交通", "通讯", "医疗", "教育",
            "服饰", "日用",
            "合理享受", "娱乐", "旅行", "社交", "宠物",
            "数码家电", "保险",
            "投资", "理财", "基金", "股票", "黄金",
            "其他",
        ],
    })
    mode: str = "hybrid"            # ledger | conversational | hybrid
    reconcile: dict[str, Any] = field(default_factory=lambda: {
        "enabled": True, "period_days": 30,
        "last_reconcile": None, "reminder_streak": 0,
    })
    cooldown_days: int = 3
    cooldown_threshold: Any = "auto"
    fast_track_whitelist: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "医疗", "per_tx_cap": 50000, "annual_cap": 200000, "used_annual": 0},
        {"name": "急诊", "per_tx_cap": 50000, "annual_cap": 200000, "used_annual": 0},
        {"name": "房屋应急", "per_tx_cap": 100000, "annual_cap": 300000, "used_annual": 0},
        {"name": "车险理赔", "per_tx_cap": 20000, "annual_cap": 80000, "used_annual": 0},
    ])
    whitelist_cap_year: Optional[int] = None
    appeal_count: int = 0
    pending_requests: list[dict[str, Any]] = field(default_factory=list)
    pending_config_changes: list[dict[str, Any]] = field(default_factory=list)
    pending_import: Optional[dict[str, Any]] = None   # §7.3 导入候选暂存（含 token）
    optimization_goal: str = "balanced"   # wealth | balanced | objective
    rebalance_override: Optional[dict[str, Any]] = None
    last_calibrate: Optional[str] = None
    last_report_date: Optional[str] = None
    report_streak: int = 0
    gap_streak: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contract":
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416
        return cls(**{k: v for k, v in data.items() if k in known})


def living_baseline_value(contract: dict[str, Any]) -> float:
    """月度生活费基线取值（§7.4 三模式；history3m 无历史回退 auto）。"""
    lb = contract.get("distribution_rules", {}).get("living_baseline", {})
    mode = lb.get("mode", "auto")
    if mode == "manual":
        return float(lb.get("manual", 0) or 0)
    if mode == "history3m" and lb.get("history3m_value"):
        return float(lb["history3m_value"])
    return float(contract.get("monthly_contribution", 0) or 0) * 0.5
