# approval — 审批热路径（§4.4 / §5.1）

> 适用：审批有分歧、触发冷静期、白名单场景。日常小额直批不需要读本文件。

## 1. judge 调用

```bash
python scripts/cli.py judge --amount <元> --category <类目> [--planned] [--data-dir <dir>]
```

输出 JSON 关键字段：
- `decision.scene`：A（批准）/ B（附条件）/ C（驳回）——§4.4 三场景，全局唯一标准；
- `decision.result` / `decision.summary`：结论与一句话依据；
- `cooldown.triggered` / `cooldown.threshold` / `cooldown.days`：是否入冷静期（F2 阈值，clamp [baseline×0.2, baseline×3]）；
- `whitelist`：白名单双上限判定（per_tx_cap 且 annual_cap，§5.1.2）；
- `inputs.*`：全部中间变量（F0/F1/F3/F3.5）——渲染意见书时原样引用；
- `impact.delay_months_simple`：简化口径延后月数（F5，须标「约」+误差披露）。

## 2. 意见书渲染

驳回/附条件强制三段式（templates/opinion.md）：契约对照 → 目标影响 → 替代方案。
措辞基调：「不是不让你花，是帮你算清代价后选更好的花法」（§5.3）。

## 3. 冷静期告知（§5.1）

`cooldown.triggered=true` 且非白名单极速 → 告知：
- 「申请已入冷静期 N 天，第 1 天与到期前 1 天会提醒，期间可『记账撤回』或『记账申诉』」；
- 撤回给正向激励（§5.1.1）：「撤回 = 多攒 X 元 ≈ 目标提前约 Y 个月」（Y 用引擎 F5 输出，禁止心算）。
- [待实施] pending_requests 入队/提醒调度当前未实装（见 STATUS.md），先口头告知语义。

## 4. 白名单告知（§5.1.2）

- `whitelist.fast_track=true`：免冷静等待，**不豁免 §4.4 判定与安全垫校验**；告知剩余年度额度 `whitelist.remaining_annual`。
- 超单笔/年度上限 → 降级常规审批（走冷静期），明确告知原因（`per_tx_ok` / `annual_ok`）。
