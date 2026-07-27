---
name: self-trust
description: 个人自律记账/资金池自我治理：初始化契约、支取审批（§4.4 确定性判定）、冷静期、报表校准、审计留痕。触发词：记账/自律/审查。
---

# self-trust（自律记账引擎）

规则引擎是**确定性 Python 代码**，不是 AI。你（LLM）只做三件事：
1. 解析用户自然语言意图 → 映射到下方命令；
2. 调 `scripts/cli.py` 对应子命令（**一律输出结构化 JSON**：判定 + 全部中间变量）；
3. 把引擎 JSON 润色成意见书/回执（措辞放开，数字锁死）。

## 铁律（不可违反）

1. **禁止心算公式**：F0~F8 一律由引擎计算；任何金额、月数、比例、阈值**必须原样引用引擎 JSON 输出**，不得自行推算、四舍五入改数、或"大概估一下"（§8.3 #1：cli.py 输出判定+中间变量，LLM 只润色不心算）。
2. **禁止代替引擎判定**：批准/附条件/驳回只认 `decision.result`；不得因用户恳求而改口（§4.2 长期优先原则）。
3. **禁止写配置区**：契约核心参数（安全垫/目标/invest_ratio 等）修改必须走 §5.4 二次确认闸门；引擎/LLM 均无权静默改（§10.3 三区权限）。
4. **误差披露**：简化口径（F5）数字须用「约/大约/估算」措辞，并附「长期目标以真实口径（F7）为准」（§2.0）。
5. **性质声明**：涉及"信托/资产保护/法律"话题时，明确本工具无法律效力（§0）。

## 命令表（§9）

| 用户说 | 引擎命令（用途 + 最小调用） | 参考 |
|---|---|---|
| 记账初始化 | 懒人一键建契约：`python scripts/cli.py init --corpus 200000 --monthly 8000 --objective "FIRE:3000000:2036-01-01"`（`--objective` 可重复 1~3 个） | references/init.md |
| 审查：买X花Y / 记账审批 | §4.4 判定+冷静期入队+F8 快照：`python scripts/cli.py judge --amount 6000 --category 合理享受 [--planned]` | references/approval.md |
| 记账撤回 | 冷静期撤回+正向激励测算：`python scripts/cli.py judge --action withdraw --request-id <id>` | references/approval.md |
| 记账确认执行 | 到期前确认终裁：`python scripts/cli.py judge --action finalize --request-id <id>` | references/approval.md |
| （调度）到期终裁 | 过期申请按原判定收尾：`python scripts/cli.py judge --action expire [--request-id <id>]`（省略 id 处理全部到期项） | references/approval.md |
| （调度）冷静期提醒 | 双阶段提醒数据：`python scripts/cli.py judge --action reminders` | references/approval.md |
| 记账申诉 | 同一逻辑重审+计数：`python scripts/cli.py appeal --request-id <id> --reason "理由"` | references/exceptions.md |
| 记账覆写（满 3 次申诉） | 人工兜底放行：`python scripts/cli.py appeal --request-id <id> --override --confirm` | references/exceptions.md |
| 记账报表 | 双轨进度条+趋势+当月快照：`python scripts/cli.py report` | references/report.md |
| 记账校准 | 月度校准（同月幂等）：`python scripts/cli.py calibrate [--force]` | references/report.md |
| 记账奖励 | 状态：`python scripts/cli.py reward`（默认 `--action status`）；解锁：`--action unlock`；支取：`--action claim --objective FIRE --amount 2000 --purpose "犒劳"` | references/report.md |
| 目标完结/归档 | 用户显式迁移：`python scripts/cli.py objective --name FIRE --to completed\|archived --confirm` | references/report.md |
| 记账对账 | hybrid 用户拍板修正：`python scripts/cli.py reconcile [--corpus 元] [--income 元] [--invest 元] [--living 元] [--impulse 元]` | references/data-modes.md |
| 记账重置 | 二次确认整文件重建（audit 保留）：`python scripts/cli.py reset --confirm --corpus 元 --monthly 元 --objective "名:目标额:期限" [--reason "..."]` | references/exceptions.md |
| 记账日志 [类型] | 审计只读查询：`python scripts/cli.py log --name approval_log\|appeal_log\|override_log\|reward_log\|monthly_history` | references/report.md |
| 记账演示 | 三场景真实干跑（不落盘不影响真实账户）：`python scripts/cli.py demo`（init 回执也自动附 demo 区块） | references/init.md |
| 记账切模式 / 记账自定义 / 记账白名单 / 第三方导入 | 待实施（见 STATUS.md）；§3.1 平滑过渡提示已实装（report/judge 输出 `mode_transition_hint`，仅建议不自动改 mode） | 对应 references |

**全局参数**（所有子命令通用，只说明这一次）：
- `--data-dir <path>`：数据目录（优先级：命令行 > `SELFTRUST_DATA_DIR` > 默认 `<home>/.claw/self-trust/`）；
- `--today YYYY-MM-DD`：覆盖当前日期（测试/重放用，日常勿传）；
- 输出恒为 JSON（`--json` 为默认且唯一格式）；失败时 `{"ok": false, "error": ..., "message": ...}` + 非零退出码（2=not_found / 3=guard 权限违规 / 4=invalid 参数）。

## references 加载路由（按需读，别全读）

| 用户动作 | 读 |
|---|---|
| 日常小额审批（最高频） | ——（引擎 JSON 自带判定+文案要素，本文件铁律足够渲染） |
| 审批有分歧/冷静期/白名单 | references/approval.md |
| 申诉/覆写/护栏修改/重置（低频） | references/exceptions.md |
| 初始化/演示 | references/init.md |
| 报表/校准/奖励/目标生命周期/日志 | references/report.md |
| 切模式/切数据源/对账 | references/data-modes.md |
| schema/权限排障 | references/contract-schema.md |

## 模板

- 意见书（驳回/附条件强制三段式）：templates/opinion.md
- 三场景演示：templates/demo.md

## 状态

核心闭环（初始化→审批→冷静期→报表→校准→奖励→申诉/覆写→重置→对账）+ §7.2 演示干跑 + §3.1 平滑过渡计数器已实装并通过测试（191 单测 + 12 端到端）。剩余待实施：模式切换/自定义/第三方导入。实现进度见 STATUS.md（真相源）。
