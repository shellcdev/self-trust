# 三场景模拟演示 — 字段速查（templates/demo.md）

> 用初始化生成的**真实契约参数**测算（引擎输出，禁止心算），但**不落地真实账目**。
> 输出**格式一律以 `references/rendering.md` §4 为准**（套 §0.5 骨架）。
> 旧格式示例（§0.5 标准化前）已全部移除，禁止照抄。
> 结尾必附：「这是演示，不影响真实账户；现在可以说『审查：买X花Y』开始真实审批。」

## 字段填充（禁止心算，原样引用引擎 JSON）

- `{threshold}` ← `engine_params.cooldown_threshold`；`{effective_cushion}` ← `engine_params.judge_cushion`
- `{cooldown_days}` ← `scenarios[1].cooldown_days`；`{F5}` ← 对应场景的 `delay_months_simple`（用「约」措辞）
- `{N}` / `{30000/N}` ← `alt_plan_scenario3.months` / `alt_plan_scenario3.per_month`
- 实际场景金额以 `scenarios[].amount` 为准（契约参数极端时引擎会推导替代金额，文案随引擎输出走）
- `demo_defaults_used=true` 时必须额外声明「⚠️ 演示数据，非您的真实契约」（notes 已自带）

> ⚠️ 字段路径说明：demo 与 judge 为**不同命令、输出 schema 不同**，路径自然不同——demo 在输出中包了一层 `engine_params` + `scenarios[]`，故用 `engine_params.cooldown_threshold` / `scenarios[i].cooldown_days`；judge 直接用 `cooldown.threshold` / `cooldown.days`。**此差异是设计使然，非 bug；渲染时以当次命令实际输出的 JSON 键为准，勿跨命令套用。**
