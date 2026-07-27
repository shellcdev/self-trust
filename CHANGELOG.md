# CHANGELOG — self-trust

## [0.7.3] - 2026-07-28

### Changed
- **扩标准类目词汇表（`models.Contract` 默认 `distribution_rules.allowed_categories`）**：由 5 项 `[食品, 居住, 医疗, 教育, 合理享受]` 扩至 16 项，按「生活必需 / 日常开销 / 生活品质 / 大额与保障 / 兜底」逻辑分组，开箱即覆盖常见个人支出场景。保留原 5 项（含受保护的「合理享受」额度类目）；新增：交通、通讯、服饰、日用、娱乐、旅行、社交、宠物、数码家电、保险、其他。词汇表仍为**推荐清单、非硬约束**（judge 不强制成员校验，见 [0.7.2] 选项 B）；已存在的 contract.json 不会自动回填新类目（仅 fresh-init 生效）。
- 测试 244 → 247：新增 test_models.py 锁定标准类目默认值（防回归）+ 同步将 test_customize 的类目增删夹具由「旅行/宠物」改为标准清单外的「园艺/健身」（因旅行、宠物现已内置，原夹具会退化为 no-op 而误判）。

## [0.7.2] - 2026-07-28

### Added
- **支出类目词汇表专用开关**（`cli.py customize --add-category / --remove-category`，`modules/customize.py`）：原仅能 `--set distribution_rules.allowed_categories=...` 整表替换（且无专用开关）。`allowed_categories` 嵌套于 `distribution_rules`（已在 `FIELD_ZONES` 注册为 CONFIG 护栏字段），故专用开关直接复用现有 §5.4 二次确认校验、**不触发冷却窗**（因不改 `invest_ratio`）；`--add-category` 去重追加、`--remove-category` 移除（缺失报错）。
- **选项 A 落地**：judge 当前**不强制校验** `--category` 是否落在 `allowed_categories` 内（保持自由文本 + 词汇表作推荐清单）。若需「超纲类目直接驳回、须先 `--add-category`」的硬约束（选项 B），仅需给 judge 加一步成员校验，开关已就绪。

### Changed
- 测试 241 → 244：test_customize 新增 3 例（加类目去重追加+立即落盘不进冷却窗、移除、移除缺失报错）。

## [0.7.1] - 2026-07-28

### Fixed
- **§7.3 导入「缺类静默清空」数据丢失隐患（#1）**：`compute_candidates` 现返回 `provided` 标记（按余额行/流水是否实际存在判断来源提供了哪些分类）；`confirm_import` 仅覆盖「来源显式提供」或「人工修正（corrections）」的分类，其余 live 原值保留。修复前一份只含资产行的 `balances.csv` 在 confirm 后会把已录入的房贷、保费等负债/刚性支出静默清空。手动录入路径（`cli import-asset --corpus/--monthly/--liabilities/--rigid`）stage 时同步标记 `provided`，局部修正不再误伤其他分类。测试 238 → 241（新增 3 例：CSV 仅资产保留 live 负债/刚性、CSV 含负债行覆盖、手动 --corpus 仅保留其余）。

## [0.7.0] - 2026-07-28

### Added
- **§7.3 第三方资产导入通道**（`modules/import_asset.py` + `cli.py import-asset` 子命令）：CSV / 手动录入拉取资产候选 → **暂存 RUNTIME 区 `pending_import`**（不立即写 live corpus）→ 人工核对确认（token 防漂移）才落到配置区的 `corpus` / `monthly_contribution` / `liabilities` / `rigid_annual_expenses`；确认后 `corpus_status` 由 `imported_pending` 切换为 `imported_confirmed`，资产池正式生效、审批解锁。
- **数据中立硬约束**：导入待核对（`imported_pending`）锁定**一切**支取审批（judge 入口前置拦截已联动）；`--cancel --token` 放弃导入，仅还原 `corpus_status`（prior_status）并清空 staging，**live 资产原值不受污染**（避免未核实数据污染后续所有审批）；重导入场景 prior_status 正确还原（如 imported_confirmed→再导入→取消仍回 imported_confirmed）。
- **CSV 格式**：`balances.csv`（name,balance,kind[,monthly]，kind∈asset/liability/rigid）自动汇总总资产 / 负债清单 / 刚性年支出；`flows.csv`（date,amount，可选）推算月均净流入；**可疑流水 flagging**（月净流入绝对值 > 3×中位数，提示用户核对重复/错账/币种错配）。
- **手动录入兜底**：无 CSV 时可 `import-asset --corpus X --monthly Y --liabilities "名:余额[:月供[:年利率]]" --rigid "名:金额[:due_month]"` 直接拉取候选（代表第三方工具已核出的数字）；确认时允许 `--corpus/--monthly/--liabilities/--rigid` 修正候选。
- 测试 227 → 238：新增 test_import_asset（CSV 解析/候选推导含可疑流水/暂存不动 live corpus/imported_pending 拦截 judge/确认落盘/确认修正/取消还原不污染/错误 token 拒）。

## [0.6.0] - 2026-07-28

### Added
- **净资产口径决策**（修复 §4.4 line360 口径 bug）：judge 非融资场景 `remaining = 净资产(corpus - 负债)` 替代原 `corpus`，负债真正参与判定（负债为空时 net==corpus，向后兼容）。
- **融资购房模式**：`judge --financed-amount >0` 将大额资产购买拆为「首付(打 liquid) + 房贷(变负债 + 月供)」。判定：① 流动口径 `remaining = corpus - 首付` 是否击穿安全垫；② 月供 ≤ 月度净流入（债务可覆盖性硬约束，否则 C 驳回）；目标 lag 用首付测算；冷静期触发额用首付。月供默认等额本息估算（700K/30y/4% ≈ 3341.91/月），可用 `--financed-term-years` / `--financed-rate` / `--financed-monthly` 覆盖。
- **负债/刚性支出建账**：`customize --add-liability "名:余额[:月供[:年利率]]"` / `--remove-liability 名` / `--add-rigid "名:金额[:due_month]"` / `--remove-rigid 名`，经 §5.4 确认立即落盘（如实上报，影响净资产口径）。
- **记录购房落账**：`customize --record-home-purchase "房价:首付比例[:期限年[:利率]]"`，确认后 `corpus -= 首付` 且 `liabilities` 追加房贷（含月供估算），与 judge 融资评估配套闭环。
- 测试 217 → 227：新增 test_liability（净资产口径对比 / 负债增删+judge 因子 / 刚性增 / 融资购房可行批准 / 首付超流动驳回 / 月供不可覆盖驳回 / 融资冷静期 / 记录购房落账）。

## [0.5.0] - 2026-07-27

### Added
- §5.4 冷却窗（削弱自身修改 1 日冷静窗）：`safety_cushion.months` 下调 / `distribution_rules.invest_ratio` 下调等「削弱自身」的护栏修改，确认后**不立即落盘**，入 `pending_config_changes` 队列、给 **1 个自然日**冷静窗；窗内可无理由撤回（`customize --withdraw --request-id <id> --token <撤回token>`，撤回 token 确认时返回），到期懒惰扫描（`report` 交互时 / `customize --review`）自动生效并写 `override_log event=contract_customize_cooled`；其余修改（含上调护栏、optimization_goal 切换、白名单增删）不属「削弱自身」，仍立即落盘。复用 §5.1 冷静期范式（pending 持久队列 + 到期终裁 + 二次提醒）。
- 运行时态字段 `pending_config_changes` 注册为 `Zone.RUNTIME`（models.FIELD_ZONES），与 `pending_requests` 同位，三区权限不拦。
- `cli.py customize` 新增 `--review`（冷却窗复查：懒惰扫描过期项自动生效 + 列窗内待决 + 二次提醒）、`--withdraw` + `--request-id`（冷却窗撤回）。
- 测试 207 → 217：新增 test_customize_cooldown（削弱→pending 不落盘 / 非削弱→立即 / 窗内撤回 / 过期自动生效+override_log / 过期撤回拒 / bad_token / stale_token 不建 pending / review 列+扫）；test_customize 中 invest_ratio 用例改为上调值以保留「立即落盘+日志」断言（削弱路径移交新文件）。

## [0.4.0] - 2026-07-27

### Added
- 记账自定义（`modules/customize.py` + `cli.py customize` 子命令，§5.4 / §7.1 / §9）：增量覆盖契约配置区参数，不破坏未填值。`--set DOTPATH=VALUE`（支持嵌套如 `distribution_rules.invest_ratio` / `safety_cushion.months` / `optimization_goal` / `mode`）、`--add-objective "名:额:期限"`、`--whitelist-add 名称 --per-tx-cap 元 --annual-cap 元`、`--whitelist-remove 名称`。
- §5.4 二次确认闸门入口闭环：预览（confirm=False）返回 `needs_confirm` + 确认 `token` + 核心护栏字段的**具体数字风险提示**（安全垫月数↓/invest_ratio 归零或变动按当前生活费基线与月净流入算出现金缓冲与每月增值投入变化、optimization_goal 三档语义、目标增删、白名单增删）；确认须带预览 `token`（防漂移/手滑，单次确认不生效），契约变更后旧 token 失效（stale_token）；落盘经 `write_contract(actor="configurator", confirm=True)`，未知字段/审计字段由底层 GuardError 拦截；变更追加 `override_log`（§5.4 步骤4，§10.1 仅追加）。
- 同步收口 §9 三项待实施：`记账模式`（optimization_goal 切换，核心护栏字段→风险提示）、`记账切模式`（mode 切换，非核心→普通确认）、`记账白名单 加/删`（fast_track_whitelist 结构改动，核心护栏字段→风险提示）。
- 测试 191 → 207：新增 test_customize（预览不落盘+token+风险提示 / 无·错 token 拒绝 / 带 token 落盘+override_log / token 契约变更失效 / 白名单增删 / 目标新增 / 未知·审计字段 GuardError / build_changes 校验）。

## [0.3.0] - 2026-07-27

### Added
- §7.2 三场景模拟演示从 stub 改为真实引擎干跑（`modules/initialize.py::demo_scenarios`）：有契约时用真实契约参数（deepcopy 隔离，绝不回写），无契约时用演示专用默认值（纯内存，显式标注「演示数据，非您的真实契约」）；三场景金额首选设计文档 §7.2 表格值（35/6000/30000），与当前契约不匹配时由引擎中间变量（阈值/安全垫/月度净流入）确定性推导替代金额，保证 A/冷静期/C 三类判定真实命中；场景 3 附分期替代方案（N 由阈值推导，每笔≤冷静期阈值）；干跑走 judge 纯函数——不落盘、不入冷静期队列、不写审计（LLM 禁止心算铁律同样适用于演示文案）。
- `cli.py` 新增 `demo` 子命令（`记账演示` 随时重看）；init 成功回执自动附 `demo` 区块（§7.2 交互口径）。
- §3.1 平滑过渡计数器实装（`modules/streaks.py`）：`report_streak` 按连续自然日 +1（同日幂等、断档重计 1），`gap_streak` 按距最近上报日惰性刷新（报则归零）；挂载点：`report.run_report` / `governance.reconcile` 算上报事件，`judge.submit` 仅观察（审批不算上报）；阈值按 §3.1 原文：hybrid 下连续 7 天上报→建议升 ledger、连续 14 天缺报→建议降 conversational；提示为软建议（`mode_transition_hint` 字段 + notes 文案带真实计数），引擎绝不自动改 mode；ledger/conversational 已定态不弹；report 场景先观察后记录（`gap_streak_observed`），避免缺报提示被归零吞掉。字段 report_streak/gap_streak/last_report_date 属运行态区（FIELD_ZONES 既有白名单，引擎可写，不绕 guard）。
- 测试 168 → 191：新增 test_demo（三场景判定类型/数字与 F1/F2/F5 独立复算一致/不落盘不变更契约/无契约默认值/init 附带/CLI 入口）、test_streaks（递增/同日幂等/断档重计/观察累积/7天・14天阈值/仅 hybrid/三挂载点落盘）；smoke_e2e 12/12 保持。

## [0.2.1] - 2026-07-27

### Fixed
- 默认数据目录锚定 home/.claw/self-trust，去除 cwd 依赖：直接 `Path.home() / ".claw" / "self-trust"`（规范 §3 平台基址字面实现，无目录遍历）。账本（contract.json + audit/*.jsonl）因此落在 skill 目录外（删 skill 不毁账本）、`.claw` 备份树内（MA-2 覆盖）；覆盖优先级不变（`--data-dir` > `SELFTRUST_DATA_DIR` > 默认），未新增任何环境变量；删除 `DEFAULT_SUBPATH` 常量；README / references / 测试同步。

## [0.2.0] - 2026-07-27

### Fixed
- 默认数据目录锚定到平台基址 `~/.claw/self-trust`（`Path.home()` 解析），不再依赖 cwd——契约是用户可配置文件，默认路径必须稳定可预测（工程规范 §3）；覆盖优先级不变（`--data-dir` > `SELFTRUST_DATA_DIR` > 默认），未新增任何环境变量；README / SKILL.md / references 同步。

### Added
- `modules/judge.py` 补全（§4.4/§5.1/§7/§7.3）：lag 恶化校验（F4+F7 遍历 objectives，impacted 列表 + A→B 降级 + 严重拖慢→C）；optimization_goal 三档判定边界乘数（wealth×1.2 / objective 非计划×1.3）；imported_pending 前置拦截；submit 编排（冷静期入队落盘 + 白名单年度记账 + 跨年归零 + F8 快照）；withdraw/finalize/expire 状态机生命周期（can_transition 守卫）；§5.1.1 撤回正向激励（F5/F7 双口径估算，无现金流时给相对表述，不硬编码月数）；list_due_reminders 双阶段提醒数据。
- `modules/calibrate.py` 实装（§6.2/§6.4）：lag_streak 连续 2 月缓冲；柔性方案优先（F7 反推 target 下调/deadline 顺延，写 rebalance_override 建议层）；刚性 boost ≤+15pct + 审批收紧；收入下跌自动放松（连续 2 月 ≤基线×0.8 → invest_ratio_adj −10pct，优先于收紧）；次月自动回滚 + 同月幂等；active→overdue 引擎翻转、completed 仅建议、transition_objective 用户确认迁移（confirm 闸门 + 权重释放提示 + 归档留痕）。
- `modules/report.py` 实装（§6.1/§10.2）：双轨进度条（达成 vs 时间轴，绿/黄/红）+ 近6月三层 ASCII 趋势 + 安全垫红线；conversational「估算数据」标注；安全垫逼近红色预警；run_report 当月首报追加 monthly_history 快照（实绩字段留 None 由对账补录，不虚构）。
- `modules/reward.py` 新增（§6.3）：F6 解锁（≥120% → 超额×20% 写 reward_quota）；claim_reward 分次递减、免冷静期但仍过 §4.4 与安全垫校验；reward_status/unlock_rewards；150%/200% 梯度仅留参数（§8.2）。
- `modules/governance.py` 新增：§5.2 申诉（§4.4 重审、request_id 维度计数、换申请归零、满 3 次开人工覆写；覆写须 confirm 知悉 F5/F7 延后测算、消耗计数归零、override_log 留痕）；§7.1.1 记账重置（二次确认 + 仅重写 contract.json + audit 全保留 + 旧契约 sha256 落 override_log）；§3.2 对账（用户拍板 corpus 修正 + 当月实绩快照 + last_reconcile 更新）。
- `core/contract.py`：新增引擎运行态子字段白名单——objectives 内 lag_streak/reward_unlocked/reward_quota/status(仅 active→overdue)、fast_track_whitelist 内 used_annual 引擎可写；条目增删与其余结构（weight/target/caps）仍配置区只读。
- `cli.py`：judge 增 --action submit|withdraw|finalize|expire|reminders 与 --request-id；reconcile/reward/reset/appeal/objective 全接真实实现；全局 --today 支持确定性重放。
- 测试 85 → 165：新增 test_judge_full / test_cooldown / test_report / test_reward / test_reset_appeal，重写 test_calibrate（缓冲/柔性/刚性/放松/回滚/生命周期），扩充 test_contract_guard（运行态子字段边界）；smoke_e2e.py 端到端冒烟 12 项（init→冷静期→撤回→驳回→校准翻转→报表快照→奖励解锁支取→重置保审计）。

## [0.1.0] - 2026-07-27

### Added
- 骨架初建（独立 git 仓库）：目录结构按设计文档 §8.3 落地。
- `core/formulas.py`：F0~F8 全公式纯函数 + doctest（文档示例数字防漂移）。
- `core/models.py`：契约 schema dataclass + 三区权限映射（FIELD_ZONES）+ pending_requests 状态机。
- `core/contract.py`：契约读写 + data-dir 三级解析（--data-dir > SELFTRUST_DATA_DIR > 默认）+ 三区权限强制（engine 写配置区必拒，§5.4 闸门）。
- `core/audit.py`：审计仅追加（audit/*.jsonl）+ F8 快照落盘，无删除接口。
- `modules/initialize.py`：§7.1 懒人模板（重复初始化拒绝/净口径警告/deadline 校验/对账锚点）。
- `modules/judge.py`：§4.4 三场景路由骨架 + 白名单双上限 + 冷静期触发（lag 校验等留 stub）。
- `cli.py`：judge|init|report|reconcile|calibrate|reward|log 七子命令，全 JSON 输出，错误显式返回。
- 测试 85 例全绿（formulas / contract_guard / audit / judge / calibrate）。
- SKILL.md 薄路由 + references 六篇 + templates 两篇（真实占位内容）。
