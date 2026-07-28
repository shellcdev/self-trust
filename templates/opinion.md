# 审批意见书模板（§5.3，全场景）

> 渲染铁律：`{...}` 占位一律填引擎 JSON 原始输出，**禁止心算改数**；测算数字用「约/大约/估算」措辞。
> 字段映射见文末速查表；`?` 为三元条件（`cond?A:B`）。

---

## 场景 A — 批准（最高频，简短放行不说教）

### A-1 无冷静期（金额 ≤ 阈值，直接放行）

```
✅ 批准：{decision.summary}
· {inputs.category} ¥{inputs.amount}（{inputs.planned?计划内:非计划内}）
· 扣除后资金池余 ¥{inputs.remaining_after}，安全垫 ¥{inputs.effective_cushion} 未受影响
```

### A-2 触发冷静期（金额 > 阈值但未破垫 — 最常见非平凡场景）

```
✅ 批准（冷静期）：{decision.summary}
· {inputs.category} ¥{inputs.amount}（{inputs.planned?计划内:非计划内}）→ 触发 {cooldown.days} 天冷静期
· 扣除后资金池余 ¥{inputs.remaining_after}，安全垫 ¥{inputs.effective_cushion} 未击穿
· 目标影响：{impacted_objectives[0].name} 延后约 {impact.delay_months_simple} 个月（简化口径，{impact.note}）
· 申请编号 {request_id}，{cooldown.days} 天后到期（{expire_at}）
· 期间可「记账撤回」（撤回 = 多攒 ¥{inputs.amount}）/「记账确认执行」/「记账申诉」
```

> **渲染要点**：A-2 是用户最常遇到的「批准但要等」场景，须同时传达「可以花」+「先等 N 天」+「等不住可以撤」三层信息。`impacted_objectives` 为空数组时省略目标影响行。

### A-3 白名单极速放行（免冷静期）

```
✅ 批准（极速）：{decision.summary}
· {inputs.category} ¥{inputs.amount} → 白名单极速通道，免冷静期
· 本年度该类目剩余额度 ¥{whitelist.remaining_annual}
```

> **渲染要点**：白名单不豁免安全垫校验（仍走 §4.4 判定），仅免冷静等待。告知剩余年度额度即可。

---

## 场景 B — 附条件（给具体数字选项，不空泛建议）

```
⚠️ 附条件：{decision.summary}
· {inputs.category} ¥{inputs.amount}（{inputs.planned?计划内:非计划内}）
· 契约对照：资金池 ¥{inputs.corpus} 扣 ¥{inputs.amount} 后余 ¥{inputs.remaining_after}，
  安全垫 ¥{inputs.effective_cushion} → {inputs.remaining_after < inputs.effective_cushion?已击穿安全垫:在安全垫之上但拖累目标}
· 目标影响：{impacted_objectives[0].name} 延后约 {impact.delay_months_simple} 个月（简化口径，{impact.note}）
· 建议选项（选一个）：
  A. 分期支取：拆 {alt_months} 个月，每月约 ¥{alt_per_month}（不击穿安全垫）
  B. 延迟到目标超额里程碑（≥120%）解锁奖励额度后支取
  C. 缩减金额到 ¥{cooldown.threshold} 以内（免冷静期直接批准）
· {cooldown.triggered?申请编号 {request_id}，{cooldown.days} 天冷静期内可撤回/确认/申诉:「」}
```

> **字段来源**：`alt_months` / `alt_per_month` 无直接 JSON 字段时，用 `cooldown.threshold` 推导：`alt_months = ceil(inputs.amount / cooldown.threshold)`，`alt_per_month = cooldown.threshold`。**此为唯一允许 LLM 推算的值**（分期方案不改变判定结论，仅做呈现建议），金额本身仍引用引擎输出。

---

## 场景 C — 驳回（三段式强制，附替代方案）

```
❌ 驳回：{decision.summary}
· {inputs.category} ¥{inputs.amount}（{inputs.planned?计划内:非计划内}）
· 契约对照：资金池 ¥{inputs.corpus} 扣 ¥{inputs.amount} 后余 ¥{inputs.remaining_after}，
  安全垫 ¥{inputs.effective_cushion} → 已击穿（差额 ¥{inputs.effective_cushion - inputs.remaining_after}）
· 目标影响：{impacted_objectives[0].name} 延后约 {impact.delay_months_simple} 个月（简化口径，{impact.note}）
· 替代方案（优先级从高到低）：
  1. 从月度「合理享受」额度拆分支取（不破垫、不损目标）
  2. 拆分 {alt_months} 个月分期支取（每月约 ¥{alt_per_month}，不击穿安全垫）
  3. 等待目标超额里程碑（≥120%）解锁奖励额度后支取
· {cooldown.triggered?申请编号 {request_id}，{cooldown.days} 天冷静期内可撤回或申诉:「驳回维持，规则引擎按纪律义务终裁」}
```

> **基调**：「不是不让你花，是帮你算清代价后选更好的花法」。不说教，用数字说话。

### C-融资购房（financed=true 时的特殊驳回）

```
❌ 驳回（融资购房）：{decision.summary}
· 房产总价 ¥{inputs.amount}，首付 ¥{inputs.down_payment}，贷款 ¥{inputs.financed_amount}
· 首付扣除后资金池余 ¥{inputs.remaining_after}，安全垫 ¥{inputs.effective_cushion}
  → {inputs.remaining_after < inputs.effective_cushion?首付击穿安全垫:首付在安全垫之上}
· {inputs.debt_service_ok?月供 ¥{inputs.mortgage_monthly} 可覆盖:月供 ¥{inputs.mortgage_monthly} 超过月度净流入 ¥{inputs.monthly_net}，债务不可覆盖}
```

---

## 撤回激励文案（§5.1.1，withdraw 输出）

```
✅ 撤回成功：¥{feedback.withdrawn_amount} 冲动申请已取消
· 等于多攒 ¥{feedback.withdrawn_amount}
· 按当前攒钱节奏（月度可投增量约 ¥{feedback.monthly_invest_nominal}），
  {feedback.objective} 进度提前约 {feedback.ahead_months_simple} 个月（简化口径）
  / 真实口径约 {feedback.ahead_months_real} 个月（含通胀/回撤）
· {feedback.estimation_note}
· 规则引擎替未来的你谢谢你 🦞
```

> **字段来源**：全部来自 withdraw 返回的 `feedback.*` 对象，**不是** judge submit 的 `inputs.*`。`feedback.objective` 为 null 时省略目标名。

---

## JSON 字段 → 占位符速查表

| 占位符 | JSON 路径（judge submit 返回） | 说明 |
|---|---|---|
| `{decision.result}` | `decision.result` | 批准/附条件/驳回 |
| `{decision.summary}` | `decision.summary` | 一句话依据 |
| `{inputs.amount}` | `inputs.amount` | 申请金额 |
| `{inputs.category}` | `inputs.category` | 支出类目 |
| `{inputs.planned}` | `inputs.planned` | 是否计划内（布尔） |
| `{inputs.corpus}` | `inputs.corpus` | 资金池余额 |
| `{inputs.remaining_after}` | `inputs.remaining_after` | 扣除后余额 |
| `{inputs.effective_cushion}` | `inputs.effective_cushion` | 安全垫阈值 |
| `{inputs.monthly_net}` | `inputs.monthly_net` | 月度净流入 |
| `{inputs.monthly_invest_nominal}` | `inputs.monthly_invest_nominal` | 月度可投增量（名义） |
| `{inputs.financed}` | `inputs.financed` | 是否融资购房 |
| `{inputs.down_payment}` | `inputs.down_payment` | 首付金额 |
| `{inputs.financed_amount}` | `inputs.financed_amount` | 贷款金额 |
| `{inputs.mortgage_monthly}` | `inputs.mortgage_monthly` | 月供 |
| `{inputs.debt_service_ok}` | `inputs.debt_service_ok` | 月供是否可覆盖 |
| `{cooldown.triggered}` | `cooldown.triggered` | 是否触发冷静期 |
| `{cooldown.threshold}` | `cooldown.threshold` | 冷静期阈值 |
| `{cooldown.days}` | `cooldown.days` | 冷静期天数 |
| `{impact.delay_months_simple}` | `impact.delay_months_simple` | 简化口径延后月数 |
| `{impact.note}` | `impact.note` | 误差披露语 |
| `{impacted_objectives[0].name}` | `impacted_objectives[0].name` | 最相关目标名（数组空时省略整行） |
| `{impacted_objectives[0].delay_months_real}` | `impacted_objectives[0].delay_months_real` | 真实口径延后月数 |
| `{request_id}` | `request_id` | 申请编号（仅冷静期触发时存在） |
| `{expire_at}` | `expire_at` | 到期时间（仅冷静期触发时存在） |
| `{whitelist.fast_track}` | `whitelist.fast_track` | 是否白名单极速 |
| `{whitelist.remaining_annual}` | `whitelist.remaining_annual` | 白名单剩余年度额度 |
| `{alt_months}` | 推导：`ceil(inputs.amount / cooldown.threshold)` | 分期月数（唯一允许推算） |
| `{alt_per_month}` | `cooldown.threshold`（每笔不超阈值） | 分期月额（引用阈值） |

### withdraw 返回字段（撤回激励文案专用）

| 占位符 | JSON 路径（judge withdraw 返回） |
|---|---|
| `{feedback.withdrawn_amount}` | `feedback.withdrawn_amount` |
| `{feedback.monthly_invest_nominal}` | `feedback.monthly_invest_nominal` |
| `{feedback.objective}` | `feedback.objective`（可能为 null） |
| `{feedback.ahead_months_simple}` | `feedback.ahead_months_simple` |
| `{feedback.ahead_months_real}` | `feedback.ahead_months_real` |
| `{feedback.estimation_note}` | `feedback.estimation_note` |
