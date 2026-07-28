# 记账报表渲染模板（§6.1）

> 渲染铁律：数字一律原样引用 report JSON 输出，禁止心算；`notes[]` 必须**逐条转述**，不可省略。
> 字段映射见文末速查表。

---

## 渲染结构（五段式）

### ① 头部概览

```
📊 记账报表（{date} · {mode} 模式）
· 资金池 ¥{corpus} / 净资产 ¥{net_assets}
· 月度净流入 ¥{monthly_net} · 生活费基线 ¥{living_baseline}
· 安全垫 ¥{effective_cushion}（垫上余量 ¥{cushion_margin}）
```

> `cushion_alert=true` 时追加红色预警：`⚠️ 安全垫余量不足 1 个月生活费，请控制支出`

### ② 目标进度（直接引用 ASCII，不自绘）

```
── 目标进度 ──
{objectives[].ascii}    ← 逐行引用，每个目标一行
```

> 每目标 ASCII 已由引擎拼好（含进度条 + 达成率 + 时间轴应达 + 颜色标签），**直接引用展示**。
> 颜色含义：绿=超前 / 黄=落后 / 红=lag≥10% 严重落后。
> 无 deadline 目标只展示攒钱占比，不标颜色。

### ③ 趋势图（有数据时展示）

```
── 近 6 月资金流向 ──
{ascii}    ← 引用 report.ascii 中换行后的趋势图部分
```

> `ascii` 字段含进度条 + 趋势图，已拼好。若含「暂无 monthly_history 快照，趋势图待累计」则如实转述，不虚构。
> `snapshot_appended` 非空时追加：「本月首报已自动落一条月度快照（实绩待对账补录）」

### ④ 冷静期挂起（有 pending_cooling 时展示）

```
── 冷静期挂起申请（{pending_cooling.length} 笔）──
· {pending_cooling[0].category} ¥{pending_cooling[0].amount}
  判定：{pending_cooling[0].decision.result} · 到期 {pending_cooling[0].expire_at}
  编号 {pending_cooling[0].request_id}（可撤回/确认/申诉）
· ...（逐笔列出）
```

> `pending_cooling` 为空数组时**整段省略**，不展示「无挂起申请」。
> 融资购房申请追加首付/月供信息：`首付 ¥{down_payment} · 月供 ¥{mortgage_monthly}`

### ⑤ 备注与提示（notes 逐条转述 + mode_transition_hint）

```
── 提示 ──
· {notes[0]}
· {notes[1]}
· ...（逐条列出，不可省略）
```

> `notes` 为空数组时整段省略。
> `mode_transition_hint` 非空时追加为最后一条提示（含 suggest_mode + 真实计数文案）。
> `rebalance_override` 非空时追加：「⚠️ 本月校准临时调整已生效（仅本月有效，原始权重不变）」

---

## 渲染决策树

```
report JSON
├─ cushion_alert=true? → 头部追加红色预警
├─ objectives[] → 逐行引用 ascii（不自绘）
├─ ascii 含趋势图? → 展示 / 含「暂无」→ 如实转述
├─ pending_cooling 非空? → 逐笔列出 / 空 → 省略
├─ notes 非空? → 逐条转述 / 空 → 省略
├─ mode_transition_hint 非空? → 追加为提示
└─ rebalance_override 非空? → 追加临时调整提示
```

## 省略清单（以下字段不向用户展示）

| 字段 | 原因 |
|---|---|
| `formulas_used` | 内部公式编号，用户无需 |
| `ref` | 文档章节引用，内部用 |
| `stub` | 引擎标记，内部用 |
| `snapshot_appended` 内部字段 | 仅告知「已落快照」即可，income/invest 等为 null 不虚构 |
| `objectives[]` 内部字段（weight/lag_streak 等） | 已在 ascii 中呈现，不重复 |

## JSON 字段速查表

| 占位符 | JSON 路径 | 说明 |
|---|---|---|
| `{date}` | `date` | 报表日期 |
| `{mode}` | `mode` | 数据模式 |
| `{corpus}` | `corpus` | 资金池余额 |
| `{net_assets}` | `net_assets` | 净资产 |
| `{monthly_net}` | `monthly_net` | 月度净流入 |
| `{living_baseline}` | `living_baseline` | 生活费基线 |
| `{effective_cushion}` | `effective_cushion` | 安全垫 |
| `{cushion_margin}` | `cushion_margin` | 垫上余量 |
| `{cushion_alert}` | `cushion_alert` | 余量<1月生活费→true |
| `{objectives[].ascii}` | `objectives[].ascii` | 逐目标进度条（已拼好） |
| `{ascii}` | `ascii` | 完整 ASCII（进度条+趋势图） |
| `{pending_cooling[]}` | `pending_cooling[]` | 冷静期挂起列表 |
| `{notes[]}` | `notes[]` | 备注数组（必须逐条转述） |
| `{rebalance_override}` | `rebalance_override` | 校准临时层（非null时提示） |
| `{mode_transition_hint}` | `mode_transition_hint` | 模式切换建议（非null时提示） |
| `{snapshot_appended}` | `snapshot_appended` | 当月首报快照（非null时提示） |
