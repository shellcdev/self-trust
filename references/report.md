# report — 报表/校准/奖励/目标生命周期（§6.1~§6.4）

## 1. 记账报表（§6.1）[stub]

`python scripts/cli.py report` 当前返回骨架结构。实装后双段呈现：
- **文字统计**：资产池/分配进度/达成率/本月已批驳回/安全垫余量预警；
- **双可视化**：
  - 目标双轨进度条（达成 vs 时间进度；绿=超前/黄=小幅落后/红=严重落后触发校准；无 deadline 目标只展示攒钱占比）；
  - 近 6 月资金流向 ASCII 趋势图（攒钱/生活/冲动/安全垫红线四层，monthly_history 快照）。
- conversational 模式须标「估算数据，精度有限」；数据缺失标「数据不全，测算存在偏差」（§3 护栏）。

## 2. 月度校准（§6.2）[stub]

`python scripts/cli.py calibrate` 当前为 stub。实装规则：
- **缓冲**：连续 2 月 `lag > 0`（F4）才触发（`lag_streak >= 2`），单月突发不收紧；
- **柔性优先**：target_amount 下调 / deadline 顺延建议 → 写 `rebalance_override` 临时层，**不改原始 objectives**；
- **刚性**：boost 上限 +15pct + 非计划审批通过率收紧；
- **收入放松**：monthly_history[].income 连续 2 月降 ≥20% → 宽松态（invest_ratio 临时 −10pct，保 living_baseline）；恢复自动回滚；
- 报表强制提示：生效周期/次月自动回滚/原始权重不变。

## 3. 里程碑奖励（§6.3）[stub]

达成率 ≥120% 且未解锁 → `reward_max = 超额 × 0.2`（F6，引擎已实现公式）；
`记账奖励 <用途>` 支取：免冷静期但**仍走 §4.4 判定**；reward_quota 分次递减；落 reward_log。

## 4. 目标生命周期（§6.4）[待实施]

active → completed（用户确认收尾，权重释放提示重分配）/ overdue（超期三选一：延期/降额/放弃，均过 §5.4 闸门）/ archived（归档，current_amount 回归资金池自由层）。
状态迁移全部用户显式确认，引擎只提示不代决。

## 5. 审计日志查询（§10.1）——已实现

```bash
python scripts/cli.py log --name approval_log|appeal_log|override_log|reward_log|monthly_history
```
只读；审计仅追加不可删，每笔审批含 F8 完整中间变量，可逐式复盘验算。
