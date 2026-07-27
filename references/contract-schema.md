# contract-schema — schema 字段 + 三区权限表（§2 / §10.3，排障用）

> 运行时基本不读；排障/开发时对照。完整 schema 以设计文档 §2 为真相源，代码映射在 `scripts/core/models.py`。

## 1. 数据布局

```
<data-dir>/
├── contract.json          # 契约（配置区 + 运行态区）
└── audit/                 # 审计区（物理分离，仅追加 .jsonl）
    ├── approval_log.jsonl     # F8 快照：每笔审批完整中间变量
    ├── appeal_log.jsonl
    ├── override_log.jsonl     # 覆写/护栏修改/契约重置事件
    ├── reward_log.jsonl
    └── monthly_history.jsonl  # 月度快照（§6.1 趋势图数据源）
```

data-dir 解析：`--data-dir` > `SELFTRUST_DATA_DIR` > `<workspace>/memory/trust/`。

## 2. 三区权限表（§10.3，`models.FIELD_ZONES` 强制）

| 区 | 字段 | 写权限 |
|---|---|---|
| 配置区（引擎只读） | version, corpus, corpus_status, liabilities, rigid_annual_expenses, monthly_contribution, safety_cushion, objectives, distribution_rules, mode, cooldown_days, cooldown_threshold, fast_track_whitelist, optimization_goal | 仅配置者；核心护栏字段（CORE_GUARD_FIELDS）须 §5.4 二次确认 |
| 运行态区（引擎可写） | reconcile, whitelist_cap_year, appeal_count, pending_requests, rebalance_override, last_calibrate, last_report_date, report_streak, gap_streak | 引擎按既定规则更新 |
| 审计区（仅追加） | approval_log, appeal_log, override_log, reward_log, monthly_history | 禁入 contract.json；只经 core/audit.py append |

违规写入 → `GuardError`（显式报错不吞），由 `test_contract_guard.py` 全量守护（测试价值序最高）。

## 3. 关键字段速查

- `corpus_status`：manual | imported_pending（**禁审批**）| imported_confirmed（§7.3 状态机）；
- `pending_requests[].status`：cooling → withdrawn | decided | expired（终态封闭，`models.can_transition`）；
- `objectives[].status`：active（缺省）| completed | overdue | archived（§6.4）；
- `fast_track_whitelist[]`：{name, per_tx_cap, annual_cap, used_annual}，used_annual 属运行态语义、跨年归零（whitelist_cap_year 判定）；
- `rebalance_override`：校准临时层，次月回滚，**不改原始 objectives**；
- `distribution_rules.calc_params`：inflation=0.025 / drawdown_factor=0.10 / r_gross=0.05（F3.5/F7 口径）。
