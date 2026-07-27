# STATUS — self-trust 实现状态

> 真相源在本文件（仓内 dev doc），不在记忆。状态标记：✅ 已实现 / ⚠️ 部分（骨架可跑，业务未完） / 待实施 / ❌ 已废弃。

更新：2026-07-27（核心闭环实装完成）

## 当前阶段：核心闭环（初始化→审批→冷静期→报表→校准→奖励→治理）已通

| 模块 | 状态 | 说明 |
|---|---|---|
| `core/formulas.py` F0~F8 | ✅ | 纯函数 + doctest（文档示例数字），除零/null/超期 clamp 守卫齐 |
| `core/models.py` schema/三区/状态机 | ✅ | dataclass 契约 + FIELD_ZONES + pending_requests 状态机守卫 |
| `core/contract.py` 读写+权限强制 | ✅ | data-dir 三级解析；engine 写配置区必拒；§5.4 闸门；新增运行态子字段白名单（lag_streak/reward_*/used_annual/status active→overdue 引擎可写，其余结构仍只读） |
| `core/audit.py` 仅追加 | ✅ | audit/*.jsonl 仅追加，无删除接口，损坏显式报错 |
| `modules/initialize.py` 懒人模板 | ✅ | §7.1 护栏 1/2/3/4 全实现；演示（§7.2）仍为 stub（低优先） |
| `modules/judge.py` | ✅ | §4.4 三场景 + lag 恶化（F4+F7 impacted/降级/严重拖慢）+ 白名单双上限与跨年重置 + optimization_goal 三档乘数 + imported_pending 拦截 + submit/withdraw/finalize/expire 冷静期生命周期 + list_due_reminders 双阶段提醒数据 + F8 快照 |
| `modules/calibrate.py` | ✅ | §6.2 lag_streak 缓冲（连续 2 月）/ 柔性优先（F7 反推）/ 刚性 boost≤+15pct / 收入下跌放松（−10pct 优先于收紧）/ 次月自动回滚 / 同月幂等；§6.4 active→overdue 引擎翻转、completed 仅建议、transition_objective 用户确认迁移 + 权重释放提示 |
| `modules/report.py` | ✅ | §6.1 双轨进度条（绿/黄/红）+ 近6月 ASCII 趋势 + 安全垫红色预警（§10.2）+ conversational 标注 + monthly_history 当月首报快照（income 等实绩不虚构，由对账补录） |
| `modules/reward.py` | ✅ | §6.3 F6 解锁（120%→超额20%）/ claim 分次递减 / 免冷静期不豁免 §4.4 / reward_log 留痕；150%/200% 梯度留参数不实现（§8.2） |
| `modules/governance.py` | ✅ | §5.2 申诉（request_id 维度计数、换申请归零、满 3 开覆写、覆写须确认延后时长+消耗计数）；§7.1.1 重置（二次确认+audit 保留+sha256 留痕）；§3.2 对账（用户拍板 corpus + 实绩快照） |
| `cli.py` | ✅ | judge(submit/withdraw/finalize/expire/reminders)/init/report/reconcile/calibrate/reward(status/unlock/claim)/reset/appeal(--override)/objective/log 全接真实实现；--data-dir/--today 全局支持；错误显式返回 |
| 冷静期状态机落盘（§5.1） | ✅ | 入队/迁移经 can_transition，跨会话持久不丢单 |
| 申诉/覆写（§5.2） | ✅ | 见 governance |
| 记账重置（§7.1.1） | ✅ | 见 governance |
| 第三方导入（§7.3） | 待实施 | 首版砍掉（§8.3 取舍 #3）；imported_pending 审批拦截已实装 |
| 模拟演示（§7.2） | ⚠️ | demo_scenarios 仍 stub（不阻塞核心闭环） |
| SKILL.md + references + templates | ✅ | 随实装迭代 |
| 测试 | ✅ | 165 通过：formulas / contract_guard（含运行态子字段边界）/ audit / judge / judge_full / cooldown / calibrate / report / reward / reset_appeal；另 smoke_e2e.py 端到端 12/12 |

## 下一步（可选，非阻塞）

1. §7.2 demo_scenarios 用真实契约干跑 judge 三场景（替换 stub）
2. §3.1 平滑过渡提示计数器（report_streak/gap_streak 更新逻辑）
3. §7.3 第三方导入通道（imported_pending→confirmed 流程；拦截已在）
4. SKILL.md / references 按实装后的 CLI 参数表同步措辞
