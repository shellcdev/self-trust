# data-modes — 三数据模式/对账/切换（§3 / §3.1 / §3.2）

## 1. 三模式对比（§3）

| 模式 | 资产台账 | 日常消费 | 负担 | 适用 |
|---|---|---|---|---|
| `ledger` | 完整持久 | 逐笔强制 | 高 | 精细化记账用户 |
| `conversational` | 不留存（会话即弃） | 单次临时 | 极低 | 试用/不愿记账 |
| `hybrid`（默认） | 资金池/目标/注入持久 | 口头临时审 | 中 | 绝大多数用户 |

边界护栏：
- ledger 缺流水 → 报表标「数据不全，测算存在偏差」；
- conversational 每次审批**必须用户手动确认当前总资产**，未确认审批中止；审批结论仍落 approval_log（审计不豁免）；
- hybrid：临时消费数据**绝不修改底层 corpus**，只有正式收入/注入/经审批支取才更新。

## 2. 平滑过渡提示（§3.1）[待实施]

仅 hybrid 触发、仅提示不自动改（用户终裁）：
- 连续 7 天上报（report_streak）→ 建议升 ledger；
- 连续 14 天缺报（gap_streak）→ 建议降 conversational。
监测字段（运行态区）：last_report_date / report_streak / gap_streak。

## 3. hybrid 定期对账（§3.2）[stub]

`python scripts/cli.py reconcile` 当前为 stub。实装规则：
- 距 last_reconcile 满 period_days（默认 30）→ 推送核对提醒（corpus / liabilities / current_amount）；
- 用户确认/修正后写入并更新 last_reconcile（引擎不自动改写 corpus，§10.3 最小权限）；
- reminder_streak 超阈值（默认 2）→ 建议降级 conversational（复用 §3.1，不强制）；
- ledger / conversational 不触发本机制。

## 4. 切换命令

`记账切模式 ledger|conversational|hybrid`[待实施] —— mode 为非核心配置字段，普通确认即可（不过 §5.4 闸门），但仍属配置区（仅配置者可改）。
