# CHANGELOG — self-trust

## [0.7.22] - 2026-08-01

### Fix（硬伤扫描修复：P0 数据丢失 + P1 逻辑绕过 + P2 潜在缺陷）
- `modules/governance.py` `reset_contract` 删除先于 `lazy_init` 的 `path.unlink()`（P0）：`lazy_init` 对非法目标返回 `ok=False` 不抛异常，原写法会导致旧契约被删不重建、资金池永久丢失；`write_contract(allow_create)` 已原子替换，删此行即修复。
- `modules/judge.py` `finalize` 对齐 `withdraw`/`expire`（P1）：过期（`today>expire_at`）返回 `already_expired` 阻止终裁；场景 C 终裁维持 `EXPIRED`，避免批准引擎本应自动驳回的申请。
- `modules/import_asset.py` `confirm_import` 加 `contract_sha` 复核（P1）：stage 记下契约摘要、confirm 比对，stage 后若被 `customize` 改动则拒绝确认，防陈旧暂存覆盖 live 编辑（静默数据丢失）。
- `core/formulas.py` `f1_effective_cushion` 未知模式兜底返回 0.0（P2）：避免 `customize --set safety_cushion.mode=bogus` 后全部 `judge`/`report` 崩溃；`customize` 预览/落盘同步拒绝非法模式。
- `modules/reward.py` `unlock_rewards` 审计时间戳改用 `audit_io.now_iso(today)`（P2）：与全链路一致，保 `--today` 逻辑时间回放。
- `modules/import_asset.py` 可疑月净流中位数改取真中位（P2）：偶数列取上下中位均值，仅影响可疑流水提示。
- `experts/_shared/check_py39.sh` 仅跳过**空** `__init__.py`（P2）：非空含 `X|Y` 注解会假通过 3.9 守卫。
- `experts/_shared/check_sync_deps.sh` 无匹配副本时非零退出（P2）：防消费端整体缺失被误判为「一致」。
- 文档/注释漂移（P2）：`SKILL.md` 单测数 363→409；`sync_deps.sh` 注释路径 `claw/tools/`→`claw/experts/_shared/`；`tests/__init__.py`/`core/__init__.py`/`modules/__init__.py` 补 `from __future__ import annotations`（守卫现已检查非空 `__init__.py`）。
- 测试：pytest 409 → 414（+5：finalize 过期护栏、finalize 场景 C→expired、confirm contract_changed 拒绝、customize 非法安全垫模式拒绝、reset 失败还原旧契约），smoke 12/12 不变。

## [0.7.21] - 2026-08-01

### Refactor（渲染层状态映射 zh_status 统一 + 修 final_status 漏英文）
- core/i18n.py 新增 `STATUS_ZH`（5 个状态族 union）与 `zh_status(value)` 渲染层统一映射；SpendStatus / ConfigChangeStatus 经由此接入渲染层（前置防范，目前仅内部落盘）。
- render/renderer.py 接入 `zh_status`，修复 `_render_judge_expire` 将到期申请 `final_status`（RequestStatus）原样吐出、泄漏英文枚举的 bug。
- test_i18n.py 新增 `test_status_zh_covers_all_families` / `test_zh_status_fallback_no_crash`：断言 zh_status 覆盖全部状态族（含 spend/config），未知值回退原值不崩。
- references/rendering.md §0.7 补第 4 条：渲染层任何状态值一律走 `zh_status`，新增状态族须并入 STATUS_ZH 并补覆盖断言。
- 测试：pytest 401 → 403（+2），smoke 12/12 不变。

## [0.7.20] - 2026-08-01

### Refactor（状态枚举集中化 + 去重 + 3.9 守卫）
- 新增 `SpendStatus` / `ConfigChangeStatus` 枚举（core/models.py）+ 对应 `SPEND_STATUS_ZH` / `CONFIG_CHANGE_STATUS_ZH`（core/i18n.py）；替换 judge.py/governance.py 的 `pending_spends` 状态裸串、customize.py 的 `pending_config_changes` 状态裸串（写+比较），与 RequestStatus/ObjectiveStatus 同构；落盘字串不变（向后兼容）。
- 抽取 `customize.py` / `import_asset.py` 重复的 `_token` / `_contract_sha` 到 `core/util.py`（`make_token` / `contract_sha`），单一来源。
- 移除 cli.py 死守卫 `except Exception`（`resolve_data_dir` 实际永不抛异常，原写法会静默吞错并退化审计加密标志）。
- 新增 `test_governance.py` / `test_cli.py` 单测；新增 `claw/experts/_shared/check_py39.sh` 守卫（缺 `from __future__ import annotations` 即报错）；补 i18n.py / test_i18n.py 的 future 导入。
- 测试：pytest 392 → 401（+9），smoke 12/12 不变。

## [0.7.19] - 2026-08-01

### Feature（月净流入口径毛/净显示优化 — phase 1 纯展示层）
- 新增 `monthly_is_gross_estimate` 标记位（RUNTIME 区）+ `monthly_basis()` 迁移推断 + `monthly_net_effective()` 净口径分解（net = 录入 − 负债月供 − 刚性月摊，仅展示不进判定）。
- 展示层：init/report 毛口径加〔毛口径·待校准〕徽标；report 常驻毛口径提示；`monthly_basis=net` 时附净口径分解行（rendering.md §1.5）。
- judge §1.5：仅 B/C/冷静期追毛口径提示行，不改变判定结论；customize 补/删负债·刚性自动翻转标记，预览+落盘返回净口径化后果行（dry-run）。
- 文档同步：rendering.md §1.5/§3/§5、templates/{report,opinion,demo}.md、contract-schema.md。
- scope：严格展示层，判定（F0/F1/F2/judge）仍用原始 monthly_contribution，无行为变化。来源 `e70a1ef`。

### Fixed（Python 3.9 兼容）
- `scripts/render/renderer.py` 补 `from __future__ import annotations`，兼容 pyproject 声明的 `requires-python >=3.9`。来源 `690069e`。

### i18n（用户可见串全量中文化 + 防复发约定）
- `21207ae` 首轮 5 处（月度净流入/生活费基线/安全垫/审计日志/安全垫模式）。
- `5dc579c` 续扫 9 处引擎 message/note（import_asset 的 imported_pending/corpus_status/imported_confirmed/{prior} 枚举、judge 拦截、report 空占位、customize 投资比例/override_log、calibrate 原始投资比例）→ 加 `_STATUS_ZH` 枚举映射。
- `d414db1` 加防复发约定：rendering.md §0.7「引擎消息串语言约定」（全中文、禁露字段名/枚举值、键值映射中文后拼接）+ SKILL 铁律 #7 同步。
- `6aa1bd7` 收尾：STATUS.md i18n 轮次标记占位符补填；templates/report.md 趋势图空占位旧串「暂无 monthly_history 快照」→「暂无月度快照」对齐引擎现状（避免 LLM 按旧串查找漏转述）。
- 全量扫描确认 `scripts/render/renderer.py` 与 `scripts/core/` 无用户可见串英文枚举泄露（i18n 盲区已净）；仅通用词 `token` 保留（非字段名/枚举）。

### 测试
- 新增 `test_monthly_basis.py`(15) + `test_renderer_monthly.py`(9)；全量 363 → 387 通过。

## [0.7.18] - 2026-07-30

### Fix（CI 挂红 + 版本元数据陈旧 — 硬伤扫描 P1 修复）

- **CI 挂红**：`tests.yml` 仅 `pip install pytest`，而 `test_crypto.py`（11 例）依赖 `cryptography` 且无 `importorskip` 守卫 → 官方管道加密测试全挂、badge 误导。本次在 `Install dev dependency` 步显式加 `cryptography`，让静态加密功能在 CI 真被测。
- **版本元数据陈旧**：`pyproject.toml` 的 `version` 滞后在 `0.7.7`（真实 HEAD 已 `[0.7.17]`）。本次对齐到 `0.7.18`（含本次修复）。
- 无引擎逻辑改动；全量测试仍 **363 passed**（装 `cryptography` 后）。

## [0.7.17] - 2026-07-28

### Docs（DESIGN.md 升 v1.1，补三项落地增强的设计落点）

设计文档 `docs/DESIGN.md` 此前为 v1.0 定稿，今天三项增强缺设计层落点，本次补齐并升 v1.1：
- **静态加密**：新增 §10.5（AES-256-GCM opt-in，passphrase/keyfile 双路线，MAGIC 检测，明文向后兼容，可选依赖 cryptography）；§2 schema 增 `crypto` 字段；§10.4 补「落盘健壮性三层加固」（读守卫/写前校验/唯一临时名）；目录与决策总表同步。
- **多币种 Level A+B**：§2 schema 增 `currency` 字段（默认 CNY）；§8.2 扩展项由「预留字段」改为「[0.7.13] 已落地（CNY 透传 / USD 折算）」。
- **骨架**：§8.3 目录树补 `core/crypto.py`。
同步 `.workbuddy` 副本。无代码改动。

## [0.7.16] - 2026-07-28

### Docs（SKILL.md 加密用法段落补全）

静态加密（密码）功能在 `[0.7.14]` 已实装，但 SKILL.md 此前仅在 init 表 / 全局参数 / 退出码 / 依赖四处散点提及，缺一段可直接照用的「密码工作流」。本次在「全局参数」之后新增「静态加密（密码）用法」小节：两条密钥路线（passphrase / key-file）语义、启用命令（`init --encrypt --crypto-mode ...`）、启用后每次命令带 `--pass`/`--key-file`（须置于子命令前）、缺密钥 exit 5、切换状态需 `reset --confirm` + 重 `init`。同步 `.workbuddy` 副本。无代码改动。

## [0.7.15] - 2026-07-28

### Hardening（落盘健壮性三层加固 — 防「写盘 bug 复现」）

**问题**：引擎落盘 `contract.json` 曾出现「两段拼接 JSON（第一段完整、第二段残缺）」，根因是写入中途被打断 / 进程被 kill / 外部同步或编辑器并发抢写（tmp→`os.replace` 之间留窗）。复现风险高；且一旦损坏，重跑命令可能把已修复文件又写花。

**三层加固（`core/contract.py` + `cli.py`）**：
- **Layer 1 读时守卫**：`read_contract` 明文契约若 `json.loads` 抛 `JSONDecodeError`（拼接/截断）→ 抛 `ContractCorruptedError`，消息明确指向 `contract.json.bak.corrupt` 恢复路径，绝不裸抛 `Extra data`。
- **Layer 2 写前校验**：`write_contract` 写入 tmp 后**回读校验**（`_tmp_is_valid`：明文 `json.loads` / 加密 `unseal_json`），通过才 `os.replace` 正式契约；校验失败瞬态重试（最多 3 次），全部失败则抛 `ContractCorruptedError`，**原契约完好保留**，绝不拿坏文件替换好文件。
- **Layer 3 唯一临时名**：tmp 名 = `contract.<pid>.<tid>.<uuid8>.tmp`（用户已落地），规避多进程 tmp 碰撞。
- **CLI 出口**：`main` 将 `_configure_crypto`（读契约探 crypto.enabled）纳入 try，捕获 `ContractCorruptedError` → `error=contract_corrupted` + **退出码 6**（不与 crypto 的 exit 5 混淆）。

**测试**：新增 `scripts/tests/test_contract_integrity.py`（5 例：拼接 JSON / 截断 JSON 触发守卫且消息含 `.bak.corrupt`；tmp 校验失败时保留原好文件无 tmp 残留；成功无 tmp 残留；CLI exit 6）。全量 **363 passed**（358 + 5）。

**行为约束（固化到长期记忆）**：任何命令报 `Extra data` / `request_not_found` → **绝不重跑**，停手上报，由用户按手动修法子处理（留痕 `contract.json.bak.corrupt`）。

## [0.7.14] - 2026-07-28

### Feature（静态加密开关 — 方案 C：passphrase + key-file 双路线，opt-in 默认关）

**问题**：本地账本（资产/负债/消费习惯）明文存 `<home>/.claw/self-trust/`，可能被云同步（OneDrive/iCloud/百度网盘）误带上云；个人完整财务画像泄露风险。

**新增 `core/crypto.py`**（可选依赖 `cryptography`，非加密路径纯标准库零依赖）：
- AES-256-GCM（AEAD，认证加密防篡改）+ `passphrase` → PBKDF2-HMAC-SHA256（20 万轮）派生密钥；
- 两种密钥路线：`passphrase`（用户密码，每次 `--pass`，密钥不落盘）/ `key-file`（自动生成 `<data-dir>/.self-trust.key` 权限 600，无感）；
- 文件格式 `MAGIC(STENC1\n) + 模式字节(P/K) + salt(仅 P) + nonce(12) + ct`；`is_encrypted` 魔数检测；
- 模块级 `session`（`set_session`/`reset_session`）+ `audit_encrypted` 标志，存储层透明加解密；
- `InvalidPassphrase`（GCM tag 校验失败）/ `CryptoUnavailable`（未装 cryptography）错误类型；缺依赖时返回清晰可操作提示。

**存储层透明集成**：
- `contract.py`：`read_contract` 检测魔数→解密；`write_contract` 按 `crypto.enabled` 密封；旧契约读走 `read_contract`（自动解密，修复二次写入 utf-8 解码坑）；
- `audit.py`：`append`/`read_all` 按魔数/标志加解密，`audit/*.jsonl` 整文件加密追加（个人单机场景）；
- `models.py`：Contract 新增 `crypto` 字段（CONFIG 区，引擎只读，默认 `{"enabled": false, "mode": "passphrase", ...}`）。

**CLI/初始化**：
- 全局 `--pass` / `--key-file`（须置于子命令前），环境变量 `SELFTRUST_PASS` / `SELFTRUST_KEY_FILE` 回退；
- `init --encrypt [--crypto-mode passphrase|keyfile]`（默认关）；keyfile 模式自动生成密钥文件并写入 `crypto.key_file`、回执附 ⚠️ 丢失告警；
- `_configure_crypto`：非 init 命令按现有契约 `crypto.enabled` 设置审计加密标志，keyfile 模式自动定位 `<data-dir>/.self-trust.key`；
- `main` 捕获 `CryptoError`（退出码 5：缺密钥/密码错误）。

**文档**：SKILL.md 依赖说明 + 全局参数 + init 命令 + 状态（358 测试）；init.md §4 加密开关全流程；contract-schema.md `crypto` 字段；STATUS.md 同步。

**向后兼容**：无魔数头的旧明文契约/审计日志原样直读；未启用加密时全链路零改动、零依赖。

## [0.7.13] - 2026-07-28

### Feature（多币种支持 — Level A+B）

**Level A：显示币种可配**
- `Contract` 新增 `currency: str = "CNY"` 字段（CONFIG 区，引擎只读）；
- `CURRENCY_SYMBOLS` 映射：CNY→¥ / USD→$ / EUR→€ / GBP→£ / HKD→HK$ / JPY→¥ / SGD→S$ / AUD→A$ / CAD→C$；
- `currency_symbol()` 辅助函数（未知币种回退到 code 本身）；
- `init --currency USD` 可选参数（默认 CNY，小写自动转大写）；
- 向后兼容：旧契约无 `currency` 字段 → `from_dict` 回退默认 CNY。

**Level B：多币种录入（judge --currency / --rate）**
- `judge()` / `submit()` 新增 `currency` + `exchange_rate` 参数；
- 非 CNY 消费：`amount_cny = original_amount * rate`，判定在换算后金额上运行；
- 缺失/无效汇率 → `missing_rate` 错误（exit code 1）；CNY 透传：`original_amount=null`（向后兼容）；
- 落盘记录：`pending_spends`（amount 原始 / amount_base 换算 / currency / exchange_rate / base_currency）、`pending_requests`（同上 + original_amount / original_currency）、`approval_log`（F8 快照：顶层 original_amount / original_currency / exchange_rate / base_currency）。

**文档同步**：`rendering.md` §0.4 多币种渲染规则（双显原始+换算金额，符号取 base_currency）+ 错误表新增 `missing_rate` + init 渲染支持非 ¥ 符号；`interaction.md` §8 多币种消费识别（符号/中文→币种代码，汇率须用户提供不估算）；`contract-schema.md` 三区权限表+字段速查新增 `currency`；`SKILL.md` 命令表 init/judge 标注 `--currency`/`--rate`。

**测试**：新增 `test_currency.py`（18 例，CNY 透传/USD 换算判定一致/缺汇率报错/零负汇率报错/contract.currency 存储/submit 落盘币种信息/冷静期币种信息/审计快照币种信息），343 → 358 全绿。

## [0.7.12] - 2026-07-28

### Docs（交互优化 — 自然语言→引擎命令预处理规则）

**问题**：SKILL.md 命令表定义了引擎接口，但用户自然语言到命令之间有 7 个预处理缺口——request_id 记忆负担（用户不会报哈希）、类目自由文本导致报表碎片化、初始化无引导流程、中文金额无解析规则、planned 标记无推断规则、冷静期不主动提醒、多笔审批无处理策略。

**新增文件**：
- `references/interaction.md` — 7 条交互规则：
  1. **上下文继承**：同会话用上一轮 request_id / 描述特征跑 reminders 匹配 / 渲染时附带记忆锚点 `编号{id}（{category} ¥{amount}）`
  2. **类目模糊映射**：14 组常见口语词→23 标准类目映射表（吃饭→食品、打车→交通…），命中静默归一、未命中轻提示
  3. **引导式初始化**：三步 onboarding（资金池→月结余→目标），缺项只问缺的
  4. **金额自然语言解析**：中文数字/简写→阿拉伯数字（六千→6000、1.2w→12000）
  5. **planned 标记推断**：周期性支出→--planned / 冲动信号→不加 / 不确定→保守不加
  6. **主动冷静期提醒**：会话开场/审批后主动跑 reminders 检查 pending，空时不刷存在感
  7. **多笔审批**：逐笔 judge + 汇总渲染，超 5 笔建议分批

**更新文件**：
- `SKILL.md` — 加载路由表新增 interaction.md 为「用户交互预处理（所有命令）」首行；命令表前加交互预处理提示；第 1 步「解析意图」指向 interaction.md
- `STATUS.md` — references+templates 行追加交互优化记录、下一步追加 #9 已完成项

**不变**：引擎代码（scripts/）零改动，325 测试全绿；interaction.md 为纯文档层预处理规则，不影响 CLI JSON 输出结构。

## [0.7.11] - 2026-07-28

### Docs（输出渲染优化 — 全场景模板 + 统一渲染指南）

**问题**：原渲染指引散落在 SKILL.md（3 条铁律 + 1 行基调）和 templates/opinion.md（仅覆盖 Scene C 驳回），最高频的 Scene A 批准（含冷静期变体）无模板、报表无渲染模板、字段映射缺失、错误输出无渲染规则、withdraw 撤回激励文案引用了错误字段路径（`F5提前月数` 而非 `feedback.ahead_months_simple`）。

**新增文件**：
- `references/rendering.md` — 统一渲染指南（全场景模板选择决策树 + 通用数字格式/误差披露/性质声明规则 + 错误码→用户提示映射表 + 冷静期生命周期渲染 + init/demo/calibrate/reward/log/appeal/customize/reconcile/reset/import 全命令渲染模板 + show vs omit 字段选择清单 + 全命令速查表）
- `templates/report.md` — 记账报表渲染模板（五段式：头部概览/目标进度/趋势图/冷静期挂起/备注提示 + 渲染决策树 + 省略清单 + 字段速查表）

**重写文件**：
- `templates/opinion.md` — 从仅覆盖 Scene C 扩展为全场景：
  - A-1 无冷静期直接放行（最高频）
  - A-2 触发冷静期批准（最常见非平凡场景）
  - A-3 白名单极速放行
  - B 附条件（含分期方案推导规则）
  - C 驳回三段式 + C-融资购房特殊驳回
  - 撤回激励文案（修正字段路径为 `feedback.*`）
  - JSON 字段 → 占位符速查表（judge submit + withdraw 两套）

**更新文件**：
- `SKILL.md` — 加载路由表新增 rendering.md 为渲染权威源、日常小额审批路由从「本文件铁律足够」改为指向 rendering.md §1 + opinion.md A-1/A-2；模板列表新增 report.md；第 3 步「润色」指向 rendering.md
- `STATUS.md` — SKILL.md+references+templates 行追加渲染优化记录、下一步追加 #8 已完成项

**不变**：引擎代码（scripts/）零改动，325 测试全绿不受影响；rendering.md/templates 均为文档层，不影响 CLI JSON 输出结构。

## [0.7.10] - 2026-07-28

### Fixed（第三轮扫描 N1–N5 / R1–R3 修复）
- **N1 安全垫模式大小写一致性**：`formulas.f1_effective_cushion` 已对 `mode` 做 `.lower()`（L5 覆盖），补 judge 路径回归测试确认 preview/customize（`_eff_cushion`）与 judge 行为一致，不再「preview 通过、judge 报错」。
- **N2 reconcile 台账统计口径**：`governance.reconcile` 清空 `pending_spends` 时 `count` 与 `total_actual_cash_out` 均排除 `withdrawn` 项，消除「笔数含撤回、金额不含」错位。
- **N3 归档审计时间对齐**：`calibrate.transition_objective` 审计记录时间由 `datetime.now()` 改为 `audit_io.now_iso(today)`，CLI 补传 `today`，重放可复现；并 `archived` 后 `weight` 归零（R2）。
- **N4 重放时间可复现**：`audit.now_iso` 在 `today` 为显式重放日期（≠ 真实今日）时时间部分固定午夜 `00:00:00`，同一 `today` 审计链秒级可复现；真实运行仍用墙钟。
- **N5 boost 百分比语义集中 + 守卫**：新增 `judge._boost_pct_to_frac`，`invest_boost_pct` 整数百分比（如 15 → 0.15）集中转换；`0<pct<1` 或越界（`>100`）显式报错，杜绝比率误传静默误用。
- **R1 judge 接入 rebalance_override（自动放松生效）**：`judge` 现读取 `contract.rebalance_override` 并生效三效应——`invest_ratio_adj` 调整有效投资比例（收入下跌放松）、`approval_rate_adj` 调整审批门槛（lag 收紧）、`boosts` 对滞后目标加成投资节奏（更快追平）；输出 `optimization_applied` 暴露应用情况。
- **R2 归档权重释放**：`calibrate.transition_objective` 对 `archived` 目标 `weight` 置 0，重新激活时不再用旧权重错配分摊（与 §6.4「权重释放」文档一致）。
- **R3 禁止重复 stage 覆盖**：`import_asset.stage_import` 在已有 `imported_pending` 未确认/取消时拒绝新 stage（返回 `already_staged`），须先 confirm/cancel，避免旧候选被静默覆盖。
- 新增回归测试 `scripts/tests/test_scan3.py`（13 例，覆盖 N1–N5 / R1–R3），测试 312 → 325，全绿。

## [0.7.9] - 2026-07-28

### Fixed（第二份扫描报告中等 M1–M9 / 轻微 L1–L11 修复，来源 `Loomy/self-trust-硬伤扫描报告.md`）
- **M1 审计时间对齐逻辑 today**：新增 `audit.now_iso(today)`，所有审计落盘（`submit`/`withdraw`/`finalize`/`expire` 的 F8/反向记录、`preview`/`apply`/`sweep`/`reconcile`/`reset`/`appeal`/`override`/`claim`/`run_report` 快照）统一用 `datetime.combine(today, datetime.now().time())`，重放场景（`--today`）审计链可复现，不再用真实墙钟导致链条断裂。
- **M2 expire 原子性**：`judge.expire` 先收集全部 `expired_ruling` 审计记录 → 一次性落盘契约（状态迁移）→ 再批量写审计；契约已一致，单条审计追加失败也不会让 request 回退重处理（修复前循环内逐条 append，中途失败会重复处理）。
- **M3 sweep 单条失败隔离**：`customize.sweep_pending_config` 逐条 `_apply_changes`，单条应用失败（如字段已不存在）→ 标记 `failed` 保留在 `pending_config_changes` 供排查、不阻塞其余、不写脏契约；到期生效的 `applied` 项移除。
- **M4 购房首付不超额**：`customize._apply_changes` 的 `record_home_purchase` 在 `corpus < down_payment` 时显式 `raise ValueError`（首付须 ≤ 资金池），不再静默转负污染 F0/F1 后续所有判定；并记运行时 `pending_spends` 台账（引擎可写、不碰配置区 corpus，台账由 reconcile 并入清空）。
- **M5 archived 语义澄清**：`calibrate.transition_objective` archived 注释明确「current_amount 为资金池内标记额度，corpus 不变、资金不消失」（验证过 current_amount 从未加入 corpus，故无「资金消失」，仅解除标记语义）。
- **M6 报表字段名统一**：`report._objective_view` 只暴露 `achieved_ratio`（current/target），删除重复的 `achieve_ratio`（同值仅差一字母），避免 LLM 渲染引用错字段。
- **M7 审计并发文件锁**：`audit._locked_append` 加跨平台文件锁（Windows `msvcrt.locking` / Unix `fcntl.flock`）整文件排他，退化优雅（锁不可用时无锁追加，单进程安全）；`audit.append` 经它落盘，避免多进程写 jsonl 行交错损坏。
- **M8 导入同账户去重改 last-wins**：`import_asset._dedup_balances` 同 `(name,kind)` 余额不同→取**最新出现值覆盖并告警**（不再求和，求和会让同账户余额翻倍污染 corpus；完全重复行仍静默丢弃）。注：此决策覆盖早期 `[0.7.6] H1` 的「求和并告警」口径。
- **M9 token 恒定时间比较**：`customize.apply` 与 `import_asset._get_staging` 的 token 比对改用 `secrets.compare_digest`（防时序攻击推断 token）。
- **L1 零期限月供**：`judge.estimate_mortgage_monthly` 期限 `n<=0` 返回 `0.0`（一次性付清，不再返回全额本金）。
- **L3 目标额须为正**：`cli._parse_objective` 与 `customize._parse_objective` 在 `target_amount<=0` 时 `raise ValueError`（负值会让 f4_lag 达成率变负、语义错乱）。
- **L4 int 保真**：`customize._parse_scalar` 先 `int(s)` 再 `float(s)`（`--set x=3` → int 3 而非 3.0，JSON 序列化 `3` 与 models `int` 一致）。
- **L5 安全垫模式大小写不敏感**：`formulas.f1_effective_cushion` 与 `customize._eff_cushion` 对 `mode` 先 `.strip().lower()`（`Months`→`months` 不再抛错）。
- **L6 deadline 日期对象比较**：`initialize.lazy_init` 解析 `date.fromisoformat(...[:10])` 比较日期对象（非字典序，杜绝 `2036-1-10 < 2036-1-9` 误判），格式非法→拒绝该目标。
- **L7 收入基线用中位数**：`calibrate.calibrate` 在 `monthly_contribution<=0 且 len(series)>=3` 时基线收入改近 3 月**中位数**（不再均值），一次性大额异常不再拉高基线、误判收入下跌。
- **L9 损坏行容忍**：`audit.read_all` 遇 `json.JSONDecodeError` 跳过该行（仅追加日志健壮性优先），不丢失前序已读记录（修复前抛错致全部记录不可读）。
- **L10 reminder_streak 缺省键**：`governance.reconcile` 对 `reconcile` 用 `setdefault("reminder_streak", 0)`，旧契约缺键不 KeyError。
- **L11 CLI 解析器本地化**：`cli.py` 不再从 `modules.customize` 导入 `_parse_liability`/`_parse_rigid`，改为本地重实现（解耦私有符号，重构 customize 不脆断）；`_parse_objective` 同样本地化且带 L3 正数校验。
- **L2 / L8 评估后有意不改**：L2（`debt_service_ok` 当 `monthly_net<=0 且 mortgage_monthly<=0` 分支）经核实该分支实际不可达（有贷款必有 `mortgage_monthly>0`），维持现状；L8（`_set_dotpath` 覆盖非 dict 中间节点）在自定义场景下可接受，暂不加警告（留待后续如需更严格校验再补）。
- 新增回归测试 `scripts/tests/test_ml_regressions.py`（26 例，覆盖 M1/M2/M3/M6/M7/M8/M9/L1/L3/L4/L5/L6/L7/L9/L10/L11），测试 285 → 312，全绿。

## [0.7.8] - 2026-07-28

### Fixed（第二轮硬伤扫描 H1–H7 严重项修复，来源 `Loomy/self-trust-硬伤扫描报告.md`）
- **H1 申诉重审透传融资参数**：`governance.appeal` 重审不再退化为全款非融资判定，改从 entry 取出 `financed_amount/down_payment/mortgage_monthly` 透传给 `judge`，融资购房月供可覆盖性硬约束不再被跳过（修复前可能把本应驳回的融资审批改判通过）。
- **H2 撤回过期校验**：`judge.withdraw` 在状态机转移前检查 `today > expire_at`，过期申请禁止撤回（须走 `expire` 终裁），消除「过期仍 cooling → 可撤回」的逻辑矛盾。
- **H3 多目标权重归一化**：`judge._objective_impacts` 按 `share = amount × weight / total_weight` 分摊，修复前 `share = amount × weight` 未除总权重，多目标时各目标影响相加翻倍、lag 恶化判定过于激进。
- **H4 冷却窗覆盖 ratio/fixed/模式切换**：`customize._is_weakening` 由仅查 `months` 下调，扩展为按「有效安全垫是否下降」判定（覆盖 `safety_cushion.ratio`/`fixed` 下调与 `months→fixed` 等模式切换），不再可被切模式+下调绕过冷却窗。
- **H5 风险提示用修改后契约**：`customize.preview`/`apply` 的 `_risk_warnings` 改传 `_apply_changes` 后的 `new` 契约，数字反映终态（修复前用修改前 `contract` 算，联动改 `living_baseline`/`monthly_contribution` 时提示数字失真）。
- **H6 拒绝同名重复追加**：`customize._apply_changes` 的 `add_objective`/`whitelist_add`/`add_liability`/`add_rigid` 增加同名查重，重复追加抛 `ValueError`（修复前静默 append 导致 `check_whitelist`/`_objective_impacts` 只取首条或重复计算）。
- **H7 覆写闭环 request 状态**：`governance.override` 放行后把 entry 置 `DECIDED` + 记 `decision` + 同步审批台账，杜绝「同笔申请仍 cooling → 可继续 withdraw/finalize、申诉 3 次再 override」的无限放行环。
- 新增测试文件 `scripts/tests/test_scan_hardening.py`，覆盖 H1–H7 回归（含对照：H1 不带融资参数→维持驳回、H2 过期→拒撤回、H4 上调/非护栏修改→不削弱）。测试 268 → 285。

## [0.7.7] - 2026-07-28

### Fixed（硬伤扫描 M1–M6 修复）
- **M1 金额精度**：新增 `parse_money`（落到分、round 2 位）+ `_dedup_balances` 改用**容差比较**（≤0.005），避免浮点亚分差异误判为非重复行；导入金额全程按分落地，杜绝亚分漂移累积。
- **M2 CSV 解析容错**：余额/月供/流水金额接受币种符号（¥ $ ￥）与千分位逗号；流水日期接受 `年-月-日 / 年/月/日 / 年.月.日 / 年-月`（统一归一为 `-`、仅认「年在前」避免美式歧义），非法格式显式报错。
- **M3 rigid 到期月**：CSV 导入解析可选 `due_month`/`due`/`month` 列（1–12）并透传，不再恒为 `None`。
- **M4 审批支出台账**：`judge.submit` 把审批通过的支出记入运行时 `pending_spends`（引擎可写、不碰配置区 `corpus`——§10.3 最小权限硬约束，故不能自动扣 corpus）；`governance.reconcile` 对账时**并入并清空**台账（返回 `pending_spends_cleared` 笔数/合计），消除「审批通过不自动扣 corpus」的静默坑；withdraw/finalize/expire 同步台账状态。
- **M5 冷却窗清理**：`customize.sweep_pending_config` 到期自动生效后**从 `pending_config_changes` 移除**已生效条目（历史沉淀在 override_log），不再无限堆积脏数据。
- **M6 部分负债修正合并**：`confirm_import` 对 `liabilities`/`rigid_annual_expenses` 的修正**按 name 合并**（覆盖同名 + 保留未提及项），不再整表覆盖暂存清单造成数据丢失。
- 测试 255 → 268（M1×3 / M2×3 / M3×1 / M4×4 / M5×1 / M6×1），全绿。

## [0.7.6] - 2026-07-28

### Fixed（硬伤扫描 H1–H3 修复）
- **H1 第三方导入去重合并**：`import_asset.compute_candidates` 新增 `_dedup_balances`，按 `(name, kind)` 去重——完全重复行（余额/月供全同）静默丢弃，同名异额行求和并告警（`warnings`），**不再因 CSV 重复列出同一账户而把资产/负债双倍计入**（修复前：招行×2→corpus 100万、房贷×2→负债 160万）。
- **H2 购房负债去重**：`customize._apply_changes` 的 `record_home_purchase` 分支，已存在「房贷」（手动录入或上次记录）时**更新而非追加**，避免负债/月供翻倍；连续两次记录仍只有一条。
- **H3 融资购房白名单同口径**：`judge.submit` 极速放行年度额度记账由按全款 `amount` 累加改为按**实际现金流出 `actual_cash_out`（首付）**累加，与白名单限额闸门口径一致；非融资路径 `actual_cash_out==amount`，行为不变。修复前：100万房款首付30万却按100万吃年度 cap，3.3 倍吃光额度。
- 测试 247 → 255（H1×4 / H2×3 / H3×1），全绿。

## [0.7.5] - 2026-07-28

### Changed
- **标准类目词汇表再扩（房/车）**：在 [0.7.4] 的 21 项基础上新增 `房产`（不动产购置，与 `居住`=日常房租水电区分）、`车辆`（购车+养车，与 `交通`=日常通勤出行区分），标准类目增至 23 项，归入「大额与保障」组。日常支出类目（`居住`/`交通`）保留不合并，避免把"月供/油费"与"买房/买车"混为一谈；购房首付+房贷仍走专用 `record-home-purchase`，不依赖此标签。词汇表仍推荐清单、非硬约束。

## [0.7.4] - 2026-07-28

### Changed
- **标准类目词汇表再扩（投资理财组）**：在 [0.7.3] 的 16 项基础上新增 `投资 / 理财 / 基金 / 股票 / 黄金` 五个资金去向标签，标准类目增至 21 项。投资机制本身仍由 `invest_ratio` 自动处理、不受影响；这组仅作「买理财/基金/金条等现金流出」的归类标签，与支出/生活品质类目区分。词汇表仍为推荐清单、非硬约束（judge 不强制成员校验，选项 B 待定）。

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
