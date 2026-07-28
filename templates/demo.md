# 三场景模拟演示模板（§7.2，初始化成功后自动附/`记账演示` 重看）

> 用初始化生成的**真实契约参数**测算（引擎输出，禁止心算），但**不落地真实账目**。
> 结尾必附：「这是演示，不影响真实账户；现在可以说『审查：买X花Y』开始真实审批。」

```
📊 三个模拟场景，帮你理解规则引擎怎么工作（数字按你的契约实算）：

① 小额合理消费 —— 奶茶 ¥35.00（合理享受）
   金额 < 冷静期阈值 ¥{threshold} 且不破垫
   → ✅ 直接批准（§4.4 场景 A：计划内享受额度充足）

② 大额非计划消费 —— 新款手机 ¥6,000.00（非计划内）
   金额 > 冷静期阈值 ¥{threshold}
   → ⏳ 触发 {cooldown_days} 天冷静期（第 1 天提醒 + 到期前二次确认，可撤回；
      撤回 = 多攒 ¥6,000.00 ≈ 目标提前约 {F5} 个月）

③ 击穿安全垫大额消费 —— 奢侈品包 ¥30,000.00（非计划内·破垫）
   corpus − 支出 < 安全垫 ¥{effective_cushion}
   → ❌ 驳回 + 替代方案（意见书三段式：契约对照 / 目标延后约 {F5} 个月 /
      分 {N} 月从合理享受额度支取，每月约 ¥{30000/N}）
```

已实装：`python scripts/cli.py demo` 输出真实引擎干跑 JSON，`{...}` 占位由以下字段填充（禁止心算）：
- `{threshold}` ← `engine_params.cooldown_threshold`；`{effective_cushion}` ← `engine_params.judge_cushion`；
- `{cooldown_days}` ← `scenarios[1].cooldown_days`；`{F5}` ← 对应场景的 `delay_months_simple`（用「约」措辞）；
- `{N}` / `{30000/N}` ← `alt_plan_scenario3.months` / `alt_plan_scenario3.per_month`；
- 实际场景金额以 `scenarios[].amount` 为准（契约参数极端时引擎会推导替代金额，文案随引擎输出走）；
- `demo_defaults_used=true` 时必须额外声明「⚠️ 演示数据，非您的真实契约」（notes 已自带）。
