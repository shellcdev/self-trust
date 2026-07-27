# STATUS — self-trust 实现状态

> 真相源在本文件（仓内 dev doc），不在记忆。状态标记：✅ 已实现 / ⚠️ 部分（骨架可跑，业务未完） / 待实施 / ❌ 已废弃。

更新：2026-07-28（**§7.3 第三方导入**收口：CSV/手动拉取资产候选 → 暂存 RUNTIME 区 `pending_import`（corpus_status=imported_pending，锁定全部审批）→ 人工核对确认（token 防漂移）落 live corpus/负债/刚性/月净流入 → imported_confirmed；可疑流水 flagging；取消还原 prior_status 不污染 live 资产；238 单测）

## 当前阶段：核心闭环（初始化→审批→冷静期→报表→校准→奖励→治理）已通

| 模块 | 状态 | 说明 |
|---|---|---|
| `core/formulas.py` F0~F8 | ✅ | 纯函数 + doctest（文档示例数字），除零/null/超期 clamp 守卫齐 |
| `core/models.py` schema/三区/状态机 | ✅ | dataclass 契约 + FIELD_ZONES + pending_requests 状态机守卫 |
| `core/contract.py` 读写+权限强制 | ✅ | data-dir 三级解析（默认 ✅ 锚定 home/.claw/self-trust：`Path.home()` 规范 §3 平台基址，零 cwd 依赖）；engine 写配置区必拒；§5.4 闸门；新增运行态子字段白名单（lag_streak/reward_*/used_annual/status active→overdue 引擎可写，其余结构仍只读） |
| `core/audit.py` 仅追加 | ✅ | audit/*.jsonl 仅追加，无删除接口，损坏显式报错 |
| `modules/initialize.py` 懒人模板 | ✅ | §7.1 护栏 1/2/3/4 全实现；§7.2 演示已接真实 judge 干跑（见下行） |
| `modules/judge.py` | ✅ | §4.4 三场景 + lag 恶化（F4+F7 impacted/降级/严重拖慢）+ 白名单双上限与跨年重置 + optimization_goal 三档乘数 + imported_pending 拦截 + submit/withdraw/finalize/expire 冷静期生命周期 + list_due_reminders 双阶段提醒数据 + F8 快照 + **净资产口径决策**（remaining 改用 `net_assets`，负债参与判定，修复 §4.4 line360 口径 bug）+ **融资购房模式**（financed_amount>0 拆首付+房贷：流动口径 remaining=corpus-首付、月供可覆盖性硬约束、目标 lag 用首付测算、冷却期触发额用首付） |
| `modules/calibrate.py` | ✅ | §6.2 lag_streak 缓冲（连续 2 月）/ 柔性优先（F7 反推）/ 刚性 boost≤+15pct / 收入下跌放松（−10pct 优先于收紧）/ 次月自动回滚 / 同月幂等；§6.4 active→overdue 引擎翻转、completed 仅建议、transition_objective 用户确认迁移 + 权重释放提示 |
| `modules/report.py` | ✅ | §6.1 双轨进度条（绿/黄/红）+ 近6月 ASCII 趋势 + 安全垫红色预警（§10.2）+ conversational 标注 + monthly_history 当月首报快照（income 等实绩不虚构，由对账补录） |
| `modules/reward.py` | ✅ | §6.3 F6 解锁（120%→超额20%）/ claim 分次递减 / 免冷静期不豁免 §4.4 / reward_log 留痕；150%/200% 梯度留参数不实现（§8.2） |
| `modules/governance.py` | ✅ | §5.2 申诉（request_id 维度计数、换申请归零、满 3 开覆写、覆写须确认延后时长+消耗计数）；§7.1.1 重置（二次确认+audit 保留+sha256 留痕）；§3.2 对账（用户拍板 corpus + 实绩快照） |
| `cli.py` | ✅ | judge(submit/withdraw/finalize/expire/reminders **+ --financed-amount/--financed-term-years/--financed-rate/--financed-monthly**)/init/demo/report/reconcile/calibrate/reward(status/unlock/claim)/reset/appeal(--override)/objective/log/customize(**+ --add-liability/--remove-liability/--add-rigid/--remove-rigid/--record-home-purchase**) 全接真实实现；--data-dir/--today 全局支持；错误显式返回 |
| 冷静期状态机落盘（§5.1） | ✅ | 入队/迁移经 can_transition，跨会话持久不丢单 |
| 申诉/覆写（§5.2） | ✅ | 见 governance |
| 记账重置（§7.1.1） | ✅ | 见 governance |
| 第三方导入（§7.3） | ✅ | `modules/import_asset.py` + `cli.py import-asset`：CSV/手动拉取候选 → 暂存 `pending_import`(imported_pending，锁定审批) → 核对确认(token)落盘(imported_confirmed)；负债/刚性/月净流入一并导入；可疑流水 flag；取消还原不污染 live 资产；`imported_pending` 审批拦截(judge)已联动 |
| 记账自定义（§5.4 / §7.1 / §9） | ✅ | `modules/customize.py` + `cli.py customize` 子命令：增量覆盖配置区（`--set` 嵌套 DOTPATH / `--add-objective` / `--whitelist-add` / `--whitelist-remove` / **`--add-liability "名:余额[:月供[:年利率]]"` / `--remove-liability 名` / `--add-rigid "名:金额[:due_month]"` / `--remove-rigid 名` / `--record-home-purchase "房价:首付比例[:期限年[:利率]]"`**）；预览（needs_confirm + token + 具体数字风险提示）→ 带 token 确认落盘 + 写 override_log；§5.4 二次确认闸门由底层 `write_contract(actor="configurator", confirm=True)` 强制；未知字段/审计字段显式 GuardError。同时解锁「记账模式（optimization_goal 切换）」「记账切模式（mode 切换）」「记账白名单 加/删」（§9 三项待实施已收口）。**负债/房贷建模**：`--add-liability`/`--remove-liability`/`--add-rigid`/`--remove-rigid` 建账（如实上报，影响净资产口径）；`--record-home-purchase` 首付打 liquid(corpus-=首付) + 房贷变负债（含月供估算），经 §5.4 确认立即落盘。**§5.4 冷却窗（可选收紧，已实装）**：`safety_cushion.months` 下调 / `invest_ratio` 下调等「削弱自身」修改，确认后入 `pending_config_changes` 队列、给 1 个自然日冷静窗，窗内可无理由撤回（`--withdraw` + 撤回 token）、到期懒惰扫描（`report`/`--review`）自动生效 + 写 `override_log event=contract_customize_cooled`；非削弱修改（含上调护栏）立即落盘。运行时态字段 `pending_config_changes` 已注册 RUNTIME 区（models.FIELD_ZONES） |
| 模拟演示（§7.2） | ✅ | demo_scenarios 真实干跑：有契约用真实参数（deepcopy 隔离）/ 无契约用演示专用默认值（纯内存）；三场景金额首选 §7.2 表格值、不匹配时由引擎中间变量确定性推导；干跑不落盘不入队不写审计；init 回执自动附 demo，`cli.py demo` 可重看 |
| 平滑过渡计数器（§3.1） | ✅ | modules/streaks.py：report_streak 连续自然日 +1（同日幂等/断档重计）、gap_streak 惰性刷新；挂载：run_report/reconcile 算上报、judge.submit 只观察；阈值 7 天→建议 ledger / 14 天→建议 conversational（仅 hybrid，软建议带真实计数，引擎不自动改 mode） |
| SKILL.md + references + templates | ✅ | 已与实装后 CLI 真实接口对齐（命令表/参数/输出字段/全局参数脚注，2026-07-27） |
| 测试 | ✅ | 238 通过：formulas / contract_guard（含运行态子字段边界）/ audit / judge / judge_full / cooldown / calibrate / report / reward / reset_appeal / demo（§7.2 干跑+隔离）/ streaks（§3.1 递增/清零/阈值/挂载点）/ **customize_cooldown**（削弱→pending不落盘/非削弱→立即/窗内撤回/过期自动生效/过期撤回拒/预览标志）/ **liability**（净资产口径对比/负债增删+judge 因子/刚性增/融资购房 可行批准/首付超流动驳回/月供不可覆盖驳回/融资冷静期/记录购房落账）/ **import_asset**（CSV 解析/候选推导含可疑流水/暂存不动 live corpus/imported_pending 拦截 judge/确认落盘/确认修正/取消还原不污染/错误 token 拒）；另 smoke_e2e.py 端到端 12/12 |

## 下一步（可选，非阻塞）

1. ~~§7.2 demo_scenarios 用真实契约干跑 judge 三场景（替换 stub）~~ ✅ 已完成（2026-07-27：真实干跑 + demo 子命令 + init 回执附带）
2. ~~§3.1 平滑过渡提示计数器（report_streak/gap_streak 更新逻辑）~~ ✅ 已完成（2026-07-27：modules/streaks.py + report/reconcile/judge 挂载 + 软建议输出）
3. ~~§7.3 第三方导入通道（imported_pending→confirmed 流程；拦截已在）~~ ✅ 已完成（2026-07-28：`modules/import_asset.py` + `cli.py import-asset` 子命令，CSV/手动拉取→暂存 pending_import→核对确认落盘；238 单测）
4. ~~记账自定义（§5.4 闸门入口）+ 模式切换/白名单增删~~ ✅ 已完成（2026-07-27：`modules/customize.py` + `cli.py customize` 子命令，预览→带 token 确认落盘 + override_log，207 单测）
5. ~~SKILL.md / references 按实装后的 CLI 参数表同步措辞~~ ✅ 已完成（2026-07-27：SKILL.md 命令表全量重写 + approval/exceptions/report/data-modes/init/contract-schema 六份 references 对齐真实子命令与 --json 输出字段）
6. ~~§5.4 冷却窗（削弱自身修改 1 日冷静窗 + 窗内撤回 + 懒惰过期自动生效）~~ ✅ 已完成（2026-07-27：`pending_config_changes` 运行时态队列 + withdraw_config/sweep_pending_config/review_config + cli `customize --withdraw/--review` + report 懒惰扫描；217 单测）
7. ~~负债/房贷建模~~ ✅ 已完成（2026-07-28：judge 决策口径改净资产(net_assets)修复 §4.4 line360 口径 bug + 融资购房模式(financed_amount 首付+月供可行性) + customize 负债/刚性支出增删 + 记录购房落账；227 单测）
