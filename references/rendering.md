# rendering — 统一输出渲染指南

> 本文件是 LLM 把引擎 JSON 润色成用户可见文本的**唯一权威指南**。
> 模板（templates/）管「长什么样」，本文件管「什么场景用什么模板 + 通用规则」。
> 全局参数（--data-dir / --today / JSON 输出）见 SKILL.md。

---

## 0. 通用规则（所有命令适用）

### 0.1 数字格式

| 场景 | 格式 | 示例 |
|---|---|---|
| 金额 | `¥` + 千分位逗号 + 2 位小数 | `¥200,000.00` |
| 月数 | 保留 1 位小数 + 「个月」 | `1.5 个月` |
| 百分比 | 保留 1 位小数 + `%` | `66.7%` |
| 比率 | 保留 2 位小数 | `0.50` |

> **禁止**向用户展示引擎输出的浮点原始值（如 `200000.0` / `1.663201663201663`）。
> 月数 < 0.1 时四舍五入到 `0.1`（不展示 0，避免「延后 0 个月」的噪声）。

### 0.2 误差披露（§2.0）

简化口径数字（`impact.delay_months_simple` / `feedback.ahead_months_simple`）**必须**用「约/大约/估算」措辞，并附误差说明：
- 首次出现：`延后约 {n} 个月（简化口径，误差 ±20%~50%）`
- 后续提及：`约 {n} 个月` 即可
- 真实口径（`delay_months_real` / `ahead_months_real`）：`真实口径约 {n} 个月（含通胀/回撤）`

### 0.3 性质声明

涉及「信托/资产保护/法律」话题时，明确声明：**本工具为个人自律记账工具，无法律效力**（§0）。
日常审批/报表不需要每次重复声明。

### 0.4 引擎错误渲染

| 退出码 | error 值 | 用户提示 | 处理建议 |
|---|---|---|---|
| 2 | `not_found` | 「未找到契约数据，请先初始化（记账初始化）」 | 引导 init |
| 3 | `guard` | 「操作被安全护栏拦截：{message}」 | 转述 message，引导合规路径 |
| 4 | `invalid` | 「参数有误：{message}」 | 转述 message，引导修正 |
| 1 | `import_pending` | 「资产待核对，禁止审批；请先完成人工核对确认」 | 引导 import-asset --confirm |
| 1 | `exists` | 「契约已存在，不可重复初始化；如需重建请走『记账重置』」 | 引导 reset |
| 1 | `invalid_transition` | 「{message}」 | 转述 message，引导正确操作 |
| 1 | `request_not_found` | 「未找到该申请，可能已终裁或撤回」 | 引导查 reminders 或 log |
| 1 | `not_due` | 「该申请尚未到期，请到期后再终裁」 | 展示 expire_at |
| 1 | `already_expired` | 「该申请已过期，请走到期终裁」 | 引导 expire |
| 1 | `override_not_open` | 「尚未达到人工覆写条件（须连续 3 次申诉被驳）」 | 引导继续申诉或接受判定 |
| 1 | `cushion_violation` | 「奖励支取击穿安全垫，规则引擎拒付」 | 引导缩减金额或等里程碑 |

> **统一原则**：错误时只转述 `message` 字段 + 给出下一步建议，**不暴露** JSON 原文、不暴露退出码数字。

---

## 1. 审批提交（judge --action submit）

### 1.1 模板选择

```
decision.scene
├─ "A" + cooldown.triggered=false + whitelist.fast_track=false → templates/opinion.md 场景 A-1
├─ "A" + cooldown.triggered=false + whitelist.fast_track=true  → templates/opinion.md 场景 A-3
├─ "A" + cooldown.triggered=true                               → templates/opinion.md 场景 A-2
├─ "B"                                                         → templates/opinion.md 场景 B
└─ "C" + inputs.financed=true                                  → templates/opinion.md 场景 C-融资购房
   "C" + inputs.financed=false                                 → templates/opinion.md 场景 C
```

### 1.2 字段选择（show vs omit）

**展示**：`decision` / `cooldown` / `inputs.amount` / `inputs.category` / `inputs.planned` / `inputs.corpus` / `inputs.remaining_after` / `inputs.effective_cushion` / `impact.delay_months_simple` / `impacted_objectives[0].name`（有冷静期时 `request_id` / `expire_at`）

**省略**（内部变量，不向用户展示）：
- `inputs.liabilities_sum` / `inputs.monthly_payment_sum` / `inputs.rigid_monthly`（已在 corpus 中体现）
- `inputs.monthly_invest_real` / `inputs.inflation`（内部测算参数）
- `inputs.invest_ratio`（配置参数，非审批结果）
- `optimization_applied.*`（调度内部变量，除非用户问「为什么判定收紧了」）
- `formulas_used`（公式编号）
- `stub` / `mode_transition_hint`（后者非 null 时追加为提示行）

### 1.3 特殊场景

- **融资购房**（`inputs.financed=true`）：展示首付/贷款/月供三件套，判定看首付是否击穿垫 + 月供是否可覆盖
- **impacted_objectives 为空数组**：省略目标影响行（小额支出不拖累目标时常见）
- **rebalance_override 非 null**：在意见末尾追加「⚠️ 本月校准临时调整已生效，审批门槛/投资比例有临时偏移」

---

## 2. 冷静期生命周期（judge --action withdraw/finalize/expire/reminders）

### 2.1 撤回（withdraw）

模板：templates/opinion.md「撤回激励文案」

字段来源：返回的 `feedback.*` 对象（**不是** submit 的 `inputs.*`）。

- `feedback.objective` 为 null 时省略目标名，改为「你的长期目标」
- `feedback.ahead_months_real` 为 null 时省略真实口径行
- 必须转述 `feedback.estimation_note`（估算非承诺）

### 2.2 确认执行（finalize）

```
✅ 终裁确认：申请 {request_id} 按「{decision.result}」终裁执行
· {decision.summary}
```

> 简短即可——用户主动确认，不需要重复全部数字。

### 2.3 到期终裁（expire）

```
⏰ 到期终裁（{processed.length} 笔）：
· {processed[0].category?} ¥{processed[0].amount?} → {processed[0].final_status}
  （{processed[0].decision.result}）
· ...
```

> `processed` 为空数组时：`✅ 无到期申请待终裁`
> `final_status=decided` → 批准/附条件生效；`final_status=expired` → 驳回维持、申请失效

### 2.4 提醒（reminders）

```
⏰ 冷静期提醒（{reminders.length} 笔）：
· {reminders[0].kind=expiring?⚠️ 即将到期:⏳ 冷静中}：{reminders[0].category} ¥{reminders[0].amount}
  剩余 {reminders[0].days_left} 天（到期 {reminders[0].expire_at}）
  编号 {reminders[0].request_id}
· ...
```

> `reminders` 为空数组时：`✅ 无冷静期挂起申请`
> `kind=expiring`（≤1天）用 ⚠️ 并建议「确认执行或撤回」；`kind=cooling` 用 ⏳ 常规提醒

---

## 3. 初始化（init）

```
✅ 契约已生成（{模式} 模式）
· 资金池 ¥{corpus} · 月度净流入 ¥{monthly_contribution}
· 目标：{objectives[0].name}（¥{target_amount}，{deadline}）...
```

- `warnings` 非空时逐条转述（⚠️ 前缀）
- `rejected_objectives` 非空时转述被拒原因
- `demo` 区块非空时按 templates/demo.md 渲染
- 末尾固定语：「已生成默认契约，可随时说『自定义』逐项调」

---

## 4. 演示（demo）

模板：templates/demo.md（已完善，按现有规则渲染）

关键点：
- `demo_defaults_used=true` 时必须声明「⚠️ 演示数据，非您的真实契约」
- 末尾固定语：「这是演示，不影响真实账户；现在可以说『审查：买X花Y』开始真实审批」

---

## 5. 报表（report）

模板：templates/report.md（五段式）

关键点：
- `notes[]` 必须**逐条转述**，不可省略
- `objectives[].ascii` 和 `ascii` **直接引用**，不自绘
- `cushion_alert=true` 时红色预警
- `pending_cooling` 为空时整段省略

---

## 6. 校准（calibrate）

```
📊 月度校准（{month}）：
{changes.length > 0?以下调整已生效:✅ 无需调整，目标进度正常}
· {changes[0].description}
· ...
```

- `skipped=true` 时：`✅ 本月已校准过（同月幂等），--force 可强制重跑`
- `rebalance_override` 非空时转述临时调整内容 + 「仅本月有效，原始权重不变」
- changes 中的具体数字**原样引用**，禁止心算

---

## 7. 奖励（reward）

### status

```
🏆 里程碑奖励状态：
· {objectives[0].name}：达成率 {achieved_ratio}% {reward_unlocked?已解锁:未解锁}
  {reward_quota > 0?可支取 ¥{reward_quota}:暂无可支取额度}
```

### unlock

```
🏆 奖励解锁：
· {objectives[0].name} 达成 {achieved_ratio}%（≥120%）→ 解锁奖励额度 ¥{reward_quota}
```

- 无新解锁时：`✅ 暂无新解锁的奖励（达成率 ≥120% 时自动解锁）`

### claim

```
✅ 奖励支取：{objective} ¥{amount}（{purpose}）
· 剩余额度 ¥{remaining_quota}
```

- `error=cushion_violation` 时按错误渲染表处理

---

## 8. 审计日志（log）

```
📋 审计日志（{log}，{count} 条）：
{count > 0?
  · [{records[0].time}] {records[0].event??:records[0].scene} ¥{records[0].amount} {records[0].category}
  · ...（最近 10 条，超过提示「共 {count} 条，仅展示最近 10 条」）
:✅ 无记录}
```

> 日志可能很长，**默认只展示最近 10 条**，告知总数。用户要求看全部时再全量展示。

---

## 9. 申诉/覆写（appeal）

### 申诉

```
📋 申诉结果：{upheld?驳回维持:改判}
· {decision.summary}
· 申诉计数 {appeal_count}/3 {override_open?→ 已开放人工覆写入口:}
```

- `override_open=true` 时追加：「你已连续 3 次申诉被驳，可走人工覆写（须确知目标延后影响）」

### 覆写（第一步无 --confirm）

```
⚠️ 人工覆写预览：
· 目标影响：{target_impact.delay_months_simple} 个月（简化口径）
  / 真实口径 {target_impact.delay_months_real} 个月
· 确认知悉后回复「确认覆写」执行
```

### 覆写（第二步 --confirm）

```
✅ 人工覆写已执行：申请 {request_id} 放行
· 目标延后影响已记录（{target_impact.delay_months_simple} 个月）
· 已落 override_log
```

---

## 10. 自定义/对账/重置/导入

### 自定义预览（无 --confirm）

```
📋 修改预览：
· {changes[0].field}: {changes[0].from} → {changes[0].to}
  后果：{changes[0].consequence}
· 确认令牌 {token}（回回复「确认修改」+ 令牌生效）
{cooldown_window?· ⚠️ 此为削弱型修改，确认后进入 {cooldown_days} 天冷静窗，窗内可无理由撤回:}
```

### 自定义确认（--confirm + --token）

```
✅ 修改已生效：{changes_summary}
{cooldown_window?· 进入 {cooldown_days} 天冷静窗（编号 {request_id}），窗内可「记账自定义·撤回」:}
```

### 对账（reconcile）

```
📊 对账完成：
{changes.corpus?· 资金池 ¥{changes.corpus.from} → ¥{changes.corpus.to}（差额 ¥{changes.corpus.diff}）:}
{pending_spends_cleared?· 清销已批支出 {pending_spends_cleared.count} 笔（合计 ¥{pending_spends_cleared.total}）:}
· 下次对账提醒：{next_reconcile_date}
```

### 重置预览（无 --confirm）

```
⚠️ 重置警告：
· 将重建整个契约（审计日志保留）
· 旧契约 sha256: {old_contract_sha256}
· 确认后须提供新契约参数（资金池/月度流入/目标）
```

### 重置确认（--confirm）

```
✅ 契约已重置
· 旧契约 sha256: {old_contract_sha256}（已归档）
· 新契约回执：...（按 init 渲染）
```

### 导入暂存

```
📋 资产导入暂存（来源：{source}）：
· 总资产 ¥{summary.total_assets}
· 负债 {summary.liabilities_count} 项 / 刚性支出 {summary.rigid_count} 项
{suspicious.length > 0?· ⚠️ 可疑流水 {suspicious.length} 条，请核对:· 无可疑流水}
· 确认令牌 {token}
· 核对后回复「确认导入」+ 令牌生效；或「取消导入」放弃
· ⚠️ 导入待核对状态将锁定全部审批
```

### 导入确认

```
✅ 资产导入已确认生效
· {applied.summary}
· 审批已解锁
```

### 导入取消

```
✅ 导入已取消，资产状态已还原
```

---

## 附：全命令输出渲染速查

| 命令 | 模板 | 核心展示字段 | 省略字段 |
|---|---|---|---|
| judge submit A-1 | opinion.md A-1 | decision/amount/remaining_after | formulas/optimization/内部变量 |
| judge submit A-2 | opinion.md A-2 | +cooldown/request_id/impact | 同上 |
| judge submit A-3 | opinion.md A-3 | +whitelist.remaining_annual | 同上 |
| judge submit B | opinion.md B | +alt_months/alt_per_month | 同上 |
| judge submit C | opinion.md C | +替代方案/差额 | 同上 |
| judge withdraw | opinion.md 撤回 | feedback.* | — |
| judge finalize | 本文件 §2.2 | request_id/decision | — |
| judge expire | 本文件 §2.3 | processed[] | — |
| judge reminders | 本文件 §2.4 | reminders[] | — |
| report | report.md | 全五段 | formulas/ref/stub/snapshot内部 |
| init | 本文件 §3 | corpus/monthly/objectives | — |
| demo | demo.md | 三场景 | — |
| calibrate | 本文件 §6 | changes[] | formulas |
| reward status | 本文件 §7 | achieved_ratio/reward_quota | — |
| reward unlock | 本文件 §7 | reward_quota | — |
| reward claim | 本文件 §7 | amount/remaining | — |
| log | 本文件 §8 | records[]（最近10条） | — |
| appeal | 本文件 §9 | upheld/decision/appeal_count | — |
| customize 预览 | 本文件 §10 | changes[]/token | — |
| customize 确认 | 本文件 §10 | changes_summary | — |
| reconcile | 本文件 §10 | changes/pending_spends_cleared | — |
| reset 预览 | 本文件 §10 | old_contract_sha256 | — |
| reset 确认 | 本文件 §10 | +init回执 | — |
| import-asset 暂存 | 本文件 §10 | summary/suspicious/token | — |
| import-asset 确认 | 本文件 §10 | applied | — |
| import-asset 取消 | 本文件 §10 | — | — |
