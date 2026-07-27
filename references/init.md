# init — 初始化引导（§7.1 / §7.2 / §7.4）

> 全局参数（--data-dir / --today / JSON 输出）见 SKILL.md。

## 1. 懒人一键模板（§7.1）——已实现

必填仅 3 项，其余固化 balanced 默认值：

```bash
python scripts/cli.py init --corpus <总资产> --monthly <月净流入> \
    --objective "名称:目标额:期限" [--objective ...]   # 1~3 个
```

`--objective` 格式 `名称:目标额:期限`，目标额/期限可省略（无期限目标只写 `名称` 或 `名称:目标额`）。

- `--monthly` 按**净口径**填（税后收入 − 负债月供 − 刚性年支出月摊，公式 F0）；懒得细算可先填毛额，回执会附 ⚠️ 净口径警告。
- 固化默认值（§7.1 表）：living_baseline=auto（monthly×0.5）、safety_cushion=months×6、invest_ratio=0.5、mode=hybrid、optimization_goal=balanced、cooldown_days=3、目标等权 1/N、start_date=当日。

护栏（引擎强制，全部已实现）：
1. **重复初始化拒绝覆盖**：已存在契约 → 返回 `error=exists`，引导 `记账自定义`[待实施] / `记账重置`（`reset --confirm ...`，见 references/exceptions.md §4）；
2. **净口径警告**：未录负债/刚性支出 → warnings 附提示；
3. **deadline 校验**：不晚于当日的目标被驳回（`rejected_objectives` 列出），不生成负周期；
4. **对账锚点**：`reconcile.last_reconcile` = 初始化当日（§3.2 30 天窗口起算）。

回执渲染：转述 warnings 与 rejected_objectives，最后附「已生成默认契约，可随时说『自定义』逐项调」。

## 2. 三场景模拟演示（§7.2）[stub]

初始化成功后自动附演示区块（`记账演示` 可重看）；模板见 templates/demo.md。
当前引擎侧 `demo_scenarios()` 为 stub（返回场景框架，未接真实测算），实装后用真实契约参数跑 F1/F2 + judge 干跑。
务必声明：「这是演示，不影响真实账户」。

## 3. 生活费基线三模式（§7.4）[自定义待实施]

- `auto`（默认）：monthly_contribution × 0.5，随注入额联动；
- `manual`：用户固定额；
- `history3m`：近 3 月均值，无历史回退 auto（引擎 `living_baseline_value()` 已实现取值逻辑）。
