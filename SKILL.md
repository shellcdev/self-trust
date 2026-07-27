---
name: self-trust
description: 个人自律记账/资金池自我治理：初始化契约、支取审批（§4.4 确定性判定）、冷静期、报表校准、审计留痕。触发词：记账/自律/审查。
---

# self-trust（自律记账引擎）

规则引擎是**确定性 Python 代码**，不是 AI。你（LLM）只做三件事：
1. 解析用户自然语言意图 → 映射到下方命令；
2. 调 `scripts/cli.py` 对应子命令（全部输出结构化 JSON）；
3. 把引擎 JSON 润色成意见书/回执（措辞放开，数字锁死）。

## 铁律（不可违反）

1. **禁止心算公式**：F0~F8 一律由引擎计算；任何金额、月数、比例、阈值**必须原样引用引擎 JSON 输出**，不得自行推算、四舍五入改数、或"大概估一下"。
2. **禁止代替引擎判定**：批准/附条件/驳回只认 `decision.result`；不得因用户恳求而改口（§4.2 长期优先原则）。
3. **禁止写配置区**：契约核心参数（安全垫/目标/invest_ratio 等）修改必须走 §5.4 二次确认闸门；引擎/LLM 均无权静默改（§10.3 三区权限）。
4. **误差披露**：简化口径（F5）数字须用「约/大约/估算」措辞，并附「长期目标以真实口径（F7）为准」（§2.0）。
5. **性质声明**：涉及"信托/资产保护/法律"话题时，明确本工具无法律效力（§0）。

## 命令表（§9）

| 用户说 | 引擎命令 | 参考 |
|---|---|---|
| 记账初始化 | `python scripts/cli.py init --corpus <元> --monthly <元> --objective "名:目标额:期限"` | references/init.md |
| 审查：买X花Y / 记账审批 | `python scripts/cli.py judge --amount <元> --category <类目> [--planned]` | references/approval.md |
| 记账申诉 / 记账撤回 | （待实施，见 STATUS.md） | references/exceptions.md |
| 记账奖励 | `python scripts/cli.py reward`（stub） | references/report.md |
| 记账报表 | `python scripts/cli.py report`（stub） | references/report.md |
| 记账对账 | `python scripts/cli.py reconcile`（stub） | references/data-modes.md |
| 记账日志 [类型] | `python scripts/cli.py log --name <approval_log\|appeal_log\|override_log\|reward_log\|monthly_history>` | references/report.md |
| 记账切模式 / 记账自定义 / 记账白名单 / 记账演示 / 记账重置 | 待实施（见 STATUS.md） | 对应 references |

所有命令可加 `--data-dir <path>`（优先级：命令行 > `SELFTRUST_DATA_DIR` > `<workspace>/memory/trust/`）。

## references 加载路由（按需读，别全读）

| 用户动作 | 读 |
|---|---|
| 日常小额审批（最高频） | ——（引擎 JSON 自带判定+文案要素，本文件铁律足够渲染） |
| 审批有分歧/冷静期/白名单 | references/approval.md |
| 申诉/覆写/护栏修改（低频） | references/exceptions.md |
| 初始化/演示 | references/init.md |
| 报表/对账/日志 | references/report.md |
| 切模式/切数据源 | references/data-modes.md |
| schema/权限排障 | references/contract-schema.md |

## 模板

- 意见书（驳回/附条件强制三段式）：templates/opinion.md
- 三场景演示：templates/demo.md

## 状态

当前为**骨架版**：judge 三场景路由可跑，calibrate/report/reconcile/reward 为 stub。实现进度见 STATUS.md（真相源）。
